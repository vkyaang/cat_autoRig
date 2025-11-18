import maya.cmds as cmds


# ----------------- HELPERS ----------------- #
def add_attr(node, long_name, attr_type, default_value=None, min_value=None, max_value=None, keyable=True,
			 enum_names=None):
	args = {"longName": long_name, "keyable": keyable}
	if attr_type == 'enum':
		if not enum_names:
			raise ValueError("Enum attribute requires 'enum_names' list.")
		args["attributeType"] = 'enum'
		args["enumName"] = ":".join(enum_names)
	else:
		args["attributeType"] = attr_type
		if default_value is not None:
			args["defaultValue"] = default_value
		if min_value is not None:
			args["minValue"] = min_value
		if max_value is not None:
			args["maxValue"] = max_value
	cmds.addAttr(node, **args)


def set_attr(node, attr, value, value_type=None):
	if value_type:
		cmds.setAttr("{0}.{1}".format(node, attr), *value, type=value_type)
	else:
		cmds.setAttr("{0}.{1}".format(node, attr), value)


def get_attr(node, attr):
	return cmds.getAttr("{0}.{1}".format(node, attr))


def connect_attr(node_a, attr_a, node_b, attr_b, force=False):
	cmds.connectAttr("{0}.{1}".format(node_a, attr_a), "{0}.{1}".format(node_b, attr_b), f=force)


def _side_from_name(name):
	try:
		return name.split("_")[1]
	except Exception:
		return None

def get_percent_position(jnt1, jnt2, percent=0.3):
	# Get world positions
	pos1 = cmds.xform(jnt1, q=True, ws=True, t=True)
	pos2 = cmds.xform(jnt2, q=True, ws=True, t=True)
	
	# Compute interpolated position
	result = [
		(1 - percent) * p1 + percent * p2
		for p1, p2 in zip(pos1, pos2)
	]
	
	return result


def circle(radius=1.0, name="circle_crv"):
	circle = cmds.circle(center=(0, 0, 0), normal=(0, 1, 0), radius=radius, name=name)[0]
	cmds.delete(circle, ch=True)
	return  circle


def create_control_hierarchy(ctrl, levels=4):
	"""
	Create a flexible control hierarchy for the given control.

	Args:
		ctrl (str): Name of the control curve transform.
		levels (int): Number of hierarchy levels to create.
			1 = zero
			2 = zero, offset
			3 = zero, offset, driven
			4 = zero, offset, driven, connect (default)

	Returns:
		dict: {level_name: group_name, ...}
	"""
	if not cmds.objExists(ctrl):
		cmds.warning(f"Control {ctrl} does not exist.")
		return {}
	
	# Predefined hierarchy naming
	base_levels = ["zero", "offset", "driven", "connect"]
	if levels < 1:
		cmds.warning("Levels must be at least 1.")
		return {}
	levels = min(levels, len(base_levels))  # Clamp to max supported
	used_levels = base_levels[:levels]
	
	hierarchy = {}
	previous_grp = None
	
	# Extract base naming (e.g. "ctrl_c_head_0001" → "c_head_0001")
	parts = ctrl.split("_")
	base_suffix = "_".join(parts[1:]) if len(parts) > 1 else ctrl
	
	# Build hierarchy
	for lvl in used_levels:
		grp_name = f"{lvl}_{base_suffix}"
		grp = cmds.createNode("transform", name=grp_name)
		cmds.matchTransform(grp, ctrl)
		
		if previous_grp:
			cmds.parent(grp, previous_grp)
		previous_grp = grp
		hierarchy[lvl] = grp
	
	# Parent the control under the last created group
	cmds.parent(ctrl, previous_grp)
	
	return hierarchy


def get_parent_grp(ctrl):
	"""
	Return all possible parent groups of a control:
	zero → offset → driven → connect → ctrl

	This function is safe even if some groups don't exist.
	It will return None for missing groups.

	Returns:
		(zero, offset, driven, connect)
	"""
	if not cmds.objExists(ctrl):
		cmds.warning(f"Control '{ctrl}' does not exist.")
		return None, None, None, None
	
	zero = offset = driven = connect = None
	
	try:
		connect = cmds.listRelatives(ctrl, parent=True, type="transform")
		if connect:
			connect = connect[0]
			driven = cmds.listRelatives(connect, parent=True, type="transform")
			if driven:
				driven = driven[0]
				offset = cmds.listRelatives(driven, parent=True, type="transform")
				if offset:
					offset = offset[0]
					zero = cmds.listRelatives(offset, parent=True, type="transform")
					if zero:
						zero = zero[0]
	except Exception as e:
		cmds.warning(f"Error getting parent hierarchy for {ctrl}: {e}")
	
	return zero, offset, driven, connect


def mirror_curve_shape(left_ctrl, right_ctrl):
	"""
	Mirror only the NURBS curve shape from left_ctrl → right_ctrl.
	Does NOT touch transforms or hierarchy.
	"""
	if not cmds.objExists(left_ctrl) or not cmds.objExists(right_ctrl):
		cmds.warning(f"❌ Missing controls: {left_ctrl}, {right_ctrl}")
		return
	
	shapes_l = cmds.listRelatives(left_ctrl, shapes=True, type='nurbsCurve', fullPath=True) or []
	shapes_r = cmds.listRelatives(right_ctrl, shapes=True, type='nurbsCurve', fullPath=True) or []
	
	if not shapes_l or not shapes_r:
		cmds.warning(f"⚠️ Missing shapes on {left_ctrl} or {right_ctrl}")
		return
	
	for shape_l, shape_r in zip(shapes_l, shapes_r):
		cvs_l = cmds.ls(f"{shape_l}.cv[*]", flatten=True)
		cvs_r = cmds.ls(f"{shape_r}.cv[*]", flatten=True)
		
		if len(cvs_l) != len(cvs_r):
			cmds.warning(f"⚠️ CV count mismatch: {shape_l} vs {shape_r}")
			continue
		
		for i, cv_l in enumerate(cvs_l):
			pos = cmds.xform(cv_l, q=True, ws=True, t=True)
			pos[0] *= -1  # Mirror X only
			cmds.xform(cvs_r[i], ws=True, t=pos)

# ----------------------------------------

def create_curve_on_joint(input_jnt, side):
	token = input_jnt.split('_')
	ori_side = _side_from_name(input_jnt)
	region = token[2]
	desc = token[3]
	
	# create parent group
	parent_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_{desc}_muscleData_0001')
	curve_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_{desc}_curves_0001', p=parent_grp)
	
	input_jnt = input_jnt.replace('_l_', f'_{side}_')
	
	children = cmds.listRelatives(input_jnt, c=True, ad=True, type='joint')[::-1]
	joints = [input_jnt] + children
	
	# get joint position
	positions = [ cmds.xform(jnt, q=True, ws=True, t=True) for jnt in joints]
	
	pos_mid_1 = get_percent_position(joints[0], joints[1], percent=0.3)
	pos_mid_2 = get_percent_position(joints[-2], joints[-1], percent=0.7)
	positions.insert(1, pos_mid_1)
	positions.insert(len(positions)-1, pos_mid_2)
	
	# create curve
	curve = cmds.curve(n=f'crv_{side}_{region}_{desc}_0001', p=positions, d=2)
	crv_shape = cmds.listRelatives(curve, c=True, type='shape')[0]
	crv_shape = cmds.rename(crv_shape, f'{curve}Shape')
	cmds.parent(curve, curve_grp)
	
	# create up curve
	up_positions = []
	up_locators = []
	# create temp locators
	for jnt in joints:
		loc = cmds.spaceLocator()[0]
		cmds.matchTransform(loc, jnt)
		if side == 'l':
			cmds.move(0, 1, 0, loc, objectSpace=True, r=True)
		else:
			cmds.move(0, -1, 0, loc, objectSpace=True, r=True)
		up_pose = cmds.xform(loc, q=True, ws=True, t=True)
		up_positions.append(up_pose)
		up_locators.append(loc)

	up_pos_mid_1 = get_percent_position(up_locators[0], up_locators[1], percent=0.3)
	up_pos_mid_2 = get_percent_position(up_locators[-2], up_locators[-1], percent=0.7)
	up_positions.insert(1, up_pos_mid_1)
	up_positions.insert(len(up_positions) - 1, up_pos_mid_2)
	
	cmds.delete(loc for loc in up_locators)
	
	up_curve = cmds.curve(n=f'crv_{side}_{region}_{desc}_up_0001', p=up_positions, d=2)
	up_crv_shape = cmds.listRelatives(up_curve, c=True, type='shape')[0]
	up_crv_shape = cmds.rename(up_crv_shape, f'{up_curve}Shape')
	cmds.parent(up_curve, curve_grp)
	
	# create uvpin
	uv_pin = cmds.createNode('uvPin', n=f'uvPin_{side}_{region}_{desc}_0001')
	connect_attr(f'{crv_shape}', 'worldSpace[0]', uv_pin, 'deformedGeometry')
	connect_attr(f'{up_crv_shape}', 'worldSpace[0]', uv_pin, 'railCurve')
	set_attr(uv_pin, 'normalOverride', 1)
	set_attr(uv_pin, 'normalizedIsoParms', 0)
	set_attr(uv_pin, 'normalAxis', 1)
	set_attr(uv_pin, 'tangentAxis', 0)

	# create output locators
	locators = []
	loc_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_{desc}_data_0001', p=parent_grp)
	
	for i in range(5):
		loc = cmds.spaceLocator(n=f'loc_{side}_{region}_{desc}_{i+1:04d}')[0]
		cmds.parent(loc, loc_grp)

		# create decompose node
		dec_node = cmds.createNode('decomposeMatrix', n=f'dec_{side}_{region}_{desc}_{i+1:04d}')
		# connect uv pin output
		connect_attr(uv_pin, f'outputMatrix[{i}]', dec_node, 'inputMatrix')

		connect_attr(dec_node, 'outputTranslate', loc, 'translate')
		connect_attr(dec_node, 'outputRotate', loc, 'rotate')

		locators.append(loc)

		# set uvpin uv coorinates
		if i == 0:
			set_attr(uv_pin, f'coordinate[{i}].coordinateU', 0)
			continue
		elif i == 1:
			set_attr(uv_pin, f'coordinate[{i}].coordinateU', 0.5)
			continue
		elif i == 2:
			set_attr(uv_pin, f'coordinate[{i}].coordinateU', 1.5)
			continue
		elif i == 3:
			set_attr(uv_pin, f'coordinate[{i}].coordinateU', 2.5)
			continue
		elif i == 4:
			set_attr(uv_pin, f'coordinate[{i}].coordinateU', 3)
		
	return joints, locators, curve, up_curve, parent_grp

def create_muscle_jnt_controllers(input_jnt, side):
	"""
	create three controllers for main joints
	"""
	input_jnt = input_jnt.replace('_l_', f'_{side}_')
	joints, locators, curve, up_curve, parent_grp = create_curve_on_joint(input_jnt, side)
	tokens = input_jnt.split('_')
	region = tokens[2]
	desc = tokens[3]
	
	# create control group
	ctrl_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_{desc}_ctrls_0001', p=parent_grp)
	# create controllers
	label_map = {0: 'start', 2: 'mid', 4: 'end'}
	last_jnt = None
	
	ctrl_joints = []
	ctrls = []
	connect_grps = []
	driven_grps = []
	
	for i, loc in enumerate(locators):
		jnt = None
		if i in label_map:
			label = label_map[i]
			# create controller
			ctrl_name = f'ctrl_{side}_{region}_{desc}_{label}_0001'
			ctrl = circle(name=ctrl_name)
			cmds.matchTransform(ctrl, loc)
			
			# create joint
			jnt_name = f'jnt_{side}_{region}_{desc}_{label}_0001'
			jnt = cmds.createNode('joint', n=jnt_name)
			cmds.matchTransform(jnt, ctrl)
			cmds.makeIdentity(jnt, apply=True, t=False, r=True, s=False, n=False)
			cmds.parent(jnt, ctrl)
			
			# create hierarchy
			create_control_hierarchy(ctrl)
			zero, offset, driven, connect = get_parent_grp(ctrl)
			cmds.parent(zero, ctrl_grp)
			
			last_jnt = jnt
			
			ctrl_joints.append(jnt)
			ctrls.append(ctrl)
			connect_grps.append(connect)
			driven_grps.append(driven)
			
			# create tangent joint
			if i == 0:
				tan_label = 'start'  # use previous label
				tan_name = f'jnt_{side}_{region}_{desc}_{tan_label}Tan_0001'
				tan_jnt = cmds.createNode('joint', n=tan_name)
				cmds.matchTransform(tan_jnt, locators[1])
				cmds.makeIdentity(tan_jnt, apply=True, t=False, r=True, s=False, n=False)
				cmds.parent(tan_jnt, last_jnt)
				ctrl_joints.append(tan_jnt)
			
				# add tangent attr to ctrl
				add_attr(ctrl, 'tangent', 'float', 0)
				# connect to tangent joint
				adl_node = cmds.createNode('addDoubleLinear', n=f'adl_{side}_{region}_{desc}_{tan_label}Tangent_0001')
				connect_attr(ctrl, 'tangent', adl_node, 'input1')
				set_attr(adl_node, 'input2', 2)
				connect_attr(adl_node, 'output', tan_jnt, 'translateX')
		
			elif i == 4:
				tan_label = 'end'  # use previous label
				tan_name = f'jnt_{side}_{region}_{desc}_{tan_label}Tan_0001'
				tan_jnt = cmds.createNode('joint', n=tan_name)
				cmds.matchTransform(tan_jnt, locators[-2])
				cmds.makeIdentity(tan_jnt, apply=True, t=False, r=True, s=False, n=False)
				cmds.parent(tan_jnt, last_jnt)
				cmds.joint(last_jnt, e=True,
						   oj='xyz',  # Orientation order: xzy, xyz, yzx, etc.
						   secondaryAxisOrient='yup',  # Direction for secondary axis
						   ch=True,  # Preserve children
						   zso=True)  # Zero scale orientation
				ctrl_joints.append(tan_jnt)
				# add tangent attr to ctrl
				add_attr(ctrl, 'tangent', 'float', 0)
				# connect to tangent joint
				adl_node = cmds.createNode('addDoubleLinear', n=f'adl_{side}_{region}_{desc}_{tan_label}Tangent_0001')
				connect_attr(ctrl, 'tangent', adl_node, 'input1')
				set_attr(adl_node, 'input2', 2)
				connect_attr(adl_node, 'output', tan_jnt, 'translateX')
	
	ctrl_joints[-1], ctrl_joints[-2] = ctrl_joints[-2], ctrl_joints[-1]
	
	# bind skin to curve
	crv_skin = cmds.skinCluster(ctrl_joints, curve)[0]
	up_crv_skin = cmds.skinCluster(ctrl_joints, up_curve)[0]
	
	# assign weights
	for i, joint in enumerate(ctrl_joints):
		cv = f"{curve}.cv[{i}]"
		up_cv = f"{up_curve}.cv[{i}]"
		cmds.skinPercent(crv_skin, cv, transformValue=[(joint, 1.0)])
		cmds.skinPercent(up_crv_skin, up_cv, transformValue=[(joint, 1.0)])
	
	# create aim constraint from mid
	# start
	start_aim_cons = cmds.aimConstraint(ctrls[1],
								  connect_grps[0],
								  aimVector=(1, 0, 0),
								  upVector=(1, 0, 0),
								  wut='None',
								  mo=True)[0]
	# end
	end_aim_cons = cmds.aimConstraint(ctrls[1],
										connect_grps[-1],
										aimVector=(-1, 0, 0),
										upVector=(1, 0, 0),
										wut='None',
										mo=True)[0]
	
	# --------------------- create driver locators
	driver_locators = []
	loc_connects = []
	loc_drivens = []
	loc_offsets = []
	
	driver_loc_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_{desc}_driverLoc_0001', p=parent_grp)
	for name in ['start', 'end']:
		loc = cmds.spaceLocator(n=f'loc_{side}_{region}_{desc}_{name}Pos_0001')[0]
		if name == 'start':
			cmds.matchTransform(loc, ctrls[0])
			
		else:
			cmds.matchTransform(loc, ctrls[-1])
			
		
		create_control_hierarchy(loc)
		loc_zero, loc_offset, loc_driven, loc_connect = get_parent_grp(loc)
		cmds.parent(loc_zero, driver_loc_grp)
		
		loc_drivens.append(loc_driven)
		loc_connects.append(loc_connect)
		loc_offsets.append(loc_offset)
		driver_locators.append(loc)
	
	# constraint mid controller
	par = cmds.parentConstraint(driver_locators[0], driver_locators[1], connect_grps[1], mo=True)[0]
	set_attr(par, 'interpType', 2)
	
	cmds.aimConstraint(driver_locators[0],
					   driver_locators[-1],
					   aimVector=(-1, 0, 0),
					   upVector=(1, 0, 0),
					   wut='None',
					   mo=True)
	cmds.aimConstraint(driver_locators[-1],
					   driver_locators[0],
					   aimVector=(1, 0, 0),
					   upVector=(1, 0, 0),
					   wut='None',
					   mo=True)
	
	# connect driven locator and control
	for attr in ['translate', 'rotate']:
		for axis in 'XYZ':
			connect_attr(loc_drivens[0], f'{attr}{axis}', driven_grps[0], f'{attr}{axis}')
			connect_attr(loc_drivens[-1], f'{attr}{axis}', driven_grps[-1], f'{attr}{axis}')
		
	cmds.parentConstraint(joints[0], loc_drivens[0], mo=True)
	cmds.parentConstraint(joints[-1], loc_drivens[-1], mo=True)
	
	return loc_drivens
	
def create_muscle_set_up(input_jnt, constraint_jnt_1, constraint_jnt_2):
	for side in ['l', 'r']:
		loc_drivens = create_muscle_jnt_controllers(input_jnt, side)
		
		# locator driven groups
		loc_start = loc_drivens[0]
		loc_end = loc_drivens[-1]
		
		# constraint driver locators driven group
		jnt1 = constraint_jnt_1.replace('_l_', f'_{side}_')
		jnt2 = constraint_jnt_2.replace('_l_', f'_{side}_')
		
		cmds.parentConstraint(jnt1, loc_start, mo=True)
		cmds.parentConstraint(jnt2, loc_end, mo=True)
		
create_muscle_set_up('jnt_l_ft_longTriceps_0001_0001', 'inSkel_l_ft_upperlegTwist_0001', 'inSkel_l_ft_kneeTwist_0001')