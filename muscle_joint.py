import maya.cmds as cmds
import maya.mel as mel


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
	
def create_display_layer(name, members, reference=False):
	display_layer = cmds.createDisplayLayer(name=name, empty=True)
	
	if reference:
		cmds.setAttr("{0}.displayType".format(display_layer), 2)
	
	if members:
		cmds.editDisplayLayerMembers(display_layer, members, noRecurse=True)
	
	return display_layer


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

# ---------------------------------------- main

def create_curve_on_joint(input_jnt, side, jnt_num, offset):
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
			cmds.move(0, offset, 0, loc, objectSpace=True, r=True)
		else:
			cmds.move(0, -offset, 0, loc, objectSpace=True, r=True)
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
	set_attr(uv_pin, 'normalAxis', 1)
	set_attr(uv_pin, 'tangentAxis', 0)
	
	#create bind joints
	bind_joints = []
	jnt_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_{desc}_joints_0001', p=parent_grp)

	for i in range(jnt_num):
		jnt = cmds.createNode('joint', n=f'jnt_{side}_{region}_{desc}_bind_{i + 1:04d}')
		cmds.parent(jnt, jnt_grp)

		# create decompose node
		dec_node = cmds.createNode('decomposeMatrix', n=f'dec_{side}_{region}_{desc}_{i + 1:04d}')
		# connect uv pin output
		connect_attr(uv_pin, f'outputMatrix[{i}]', dec_node, 'inputMatrix')

		connect_attr(dec_node, 'outputTranslate', jnt, 'translate')
		connect_attr(dec_node, 'outputRotate', jnt, 'rotate')

		bind_joints.append(jnt)

		# set uvpin uv coorinates
		# evenly spaced UVs based on joint number
		for i in range(jnt_num):
			u = float(i) / (jnt_num - 1)  # value between 0 and 1
			set_attr(uv_pin, f'coordinate[{i}].coordinateU', u)

	
	return joints, positions, curve, up_curve, parent_grp, bind_joints

def create_muscle_jnt_controllers(input_jnt, side, jnt_num, parent, offset):
	"""
	create three controllers for main joints
	"""
	input_jnt = input_jnt.replace('_l_', f'_{side}_')
	joints, positions, curve, up_curve, parent_grp, bind_joints = create_curve_on_joint(input_jnt, side, jnt_num, offset)
	tokens = input_jnt.split('_')
	region = tokens[2]
	desc = tokens[3]
	
	# create control group
	ctrl_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_{desc}_ctrls_0001', p=parent_grp)
	cmds.scaleConstraint(parent, ctrl_grp)
	
	# create controllers
	label_map = {0: 'start', 1: 'mid', 2: 'end'}
	last_jnt = None
	
	ctrl_joints = []
	ctrls = []
	connect_grps = []
	driven_grps = []
	
	for i, pos in enumerate(joints):
		jnt = None
		if i in label_map:
			label = label_map[i]
			# create controller
			ctrl_name = f'ctrl_{side}_{region}_{desc}_{label}_0001'
			ctrl = circle(name=ctrl_name)
			
			# change color
			if side == 'l':
				set_attr(f'{ctrl}Shape', 'overrideEnabled', 1)
				set_attr(f'{ctrl}Shape', 'overrideColor', 18)
			else:
				set_attr(f'{ctrl}Shape', 'overrideEnabled', 1)
				set_attr(f'{ctrl}Shape', 'overrideColor', 20)
				
			set_attr(ctrl, 'rotateZ', 90)
			cmds.makeIdentity(ctrl, apply=True, t=False, r=True, s=False, n=False)
			cmds.matchTransform(ctrl, pos)
			
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
				
				# get pos
				cmds.xform(tan_jnt, ws=True, t=positions[1])
				cmds.makeIdentity(tan_jnt, apply=True, t=False, r=True, s=False, n=False)
				cmds.parent(tan_jnt, last_jnt)
				cmds.joint(last_jnt, e=True,
						   oj='xzy',  # Orientation order: xzy, xyz, yzx, etc.
						   secondaryAxisOrient='ydown',  # Direction for secondary axis
						   ch=True,  # Preserve children
						   zso=True)  # Zero scale orientation
				# clear joint orient
				for attr in 'XYZ':
					set_attr(tan_jnt, f'jointOrient{attr}', 0)
				
				# add tangent attr to ctrl
				add_attr(ctrl, 'tangent', 'float', 0)
				# connect to tangent joint
				adl_node = cmds.createNode('plusMinusAverage', n=f'pma_{side}_{region}_{desc}_{tan_label}Tangent_0001')
				connect_attr(ctrl, 'tangent', adl_node, 'input1D[0]')
				tx = get_attr(tan_jnt, 'translateX')
				set_attr(adl_node, 'input1D[1]', tx)
				connect_attr(adl_node, 'output1D', tan_jnt, 'translateX')

				ctrl_joints.append(tan_jnt)
				
				continue
			elif i == 2:
				tan_label = 'end'  # use previous label
				tan_name = f'jnt_{side}_{region}_{desc}_{tan_label}Tan_0001'
				tan_jnt = cmds.createNode('joint', n=tan_name)
				
				cmds.xform(tan_jnt, ws=True, t=positions[-2])
				cmds.makeIdentity(tan_jnt, apply=True, t=False, r=True, s=False, n=False)
				cmds.parent(tan_jnt, last_jnt)
				cmds.joint(last_jnt, e=True,
						   oj='xzy',  # Orientation order: xzy, xyz, yzx, etc.
						   secondaryAxisOrient='ydown',  # Direction for secondary axis
						   ch=True,  # Preserve children
						   zso=True)  # Zero scale orientation
				# clear joint orient
				for attr in 'XYZ':
					set_attr(tan_jnt, f'jointOrient{attr}', 0)
					
				ctrl_joints.append(tan_jnt)
				# add tangent attr to ctrl
				add_attr(ctrl, 'tangent', 'float', 0)
				# connect to tangent joint
				adl_node = cmds.createNode('plusMinusAverage', n=f'pma_{side}_{region}_{desc}_{tan_label}Tangent_0001')
				connect_attr(ctrl, 'tangent', adl_node, 'input1D[0]')
				tx = get_attr(tan_jnt, 'translateX')
				set_attr(adl_node, 'input1D[1]', tx)
				connect_attr(adl_node, 'output1D', tan_jnt, 'translateX')
	
	ctrl_joints[-1], ctrl_joints[-2] = ctrl_joints[-2], ctrl_joints[-1]
	
	#vis off
	for jnt in ctrl_joints:
		set_attr(jnt, 'visibility', 0)
		
	# bind skin to curve
	crv_skin = cmds.skinCluster(ctrl_joints, curve)[0]
	up_crv_skin = cmds.skinCluster(ctrl_joints, up_curve)[0]
	
	# assign weights
	for i, joint in enumerate(ctrl_joints):
		cv = f"{curve}.cv[{i}]"
		up_cv = f"{up_curve}.cv[{i}]"
		cmds.skinPercent(crv_skin, cv, transformValue=[(joint, 1.0)])
		cmds.skinPercent(up_crv_skin, up_cv, transformValue=[(joint, 1.0)])
	
	# jiggle deformer
	do_jiggle_deformer(ctrls[1], curve, up_curve)
	
	# create aim constraint from mid
	# start
	if side == 'l':
		aim_x = 1
	else:
		aim_x = -1

	start_aim_cons = cmds.aimConstraint(ctrls[1],
								  connect_grps[0],
								  aimVector=(aim_x, 0, 0),
								  upVector=(0, 1, 0),
								  wut='None',
								  mo=True)[0]
	# end
	end_aim_cons = cmds.aimConstraint(ctrls[1],
										connect_grps[-1],
										aimVector=(-aim_x, 0, 0),
										upVector=(0, 1, 0),
										wut='None',
										mo=True)[0]
	
	# --------------------- create driver locators
	driver_locators = []
	loc_connects = []
	loc_drivens = []
	loc_offsets = []
	
	driver_loc_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_{desc}_driverLoc_0001', p=parent_grp)
	cmds.scaleConstraint(parent, driver_loc_grp)
	
	for name in ['start', 'end']:
		pos = cmds.spaceLocator(n=f'loc_{side}_{region}_{desc}_{name}Pos_0001')[0]
		# set_attr(pos, 'visibility', 0)
		if name == 'start':
			cmds.matchTransform(pos, ctrls[0])
			
		else:
			cmds.matchTransform(pos, ctrls[-1])
			
		
		create_control_hierarchy(pos)
		loc_zero, loc_offset, loc_driven, loc_connect = get_parent_grp(pos)
		cmds.parent(loc_zero, driver_loc_grp)
		
		loc_drivens.append(loc_driven)
		loc_connects.append(loc_connect)
		loc_offsets.append(loc_offset)
		driver_locators.append(pos)
	
	# constraint mid controller
	par = cmds.parentConstraint(driver_locators[0], driver_locators[1], driven_grps[1], mo=True)[0]
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
	
	
	mid_push_setup(ctrls, bind_joints[1:-1], side, region, desc, f'{curve}Shape', driver_locators)
	
	return loc_drivens, curve, up_curve


def mid_push_setup(ctrls, bind_joints, side, region, desc, curve_shape, drive_locators):
	"""
	add volumeYZ, push middle controller
	"""
	ctrl = ctrls[1]
	
	# create curve info
	crv_info = cmds.createNode('curveInfo', n=f'crvInfo_{side}_{region}_{desc}_0001')
	connect_attr(curve_shape, 'worldSpace[0]', crv_info, 'inputCurve')
	arc_length = get_attr(crv_info, 'arcLength')
	
	# normalize global scale
	scale_fix_mdl = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{desc}_scaleFixFactor_0001')
	set_attr(scale_fix_mdl, 'input1X', arc_length)
	connect_attr('jnt_ROOT', 'scale', scale_fix_mdl, 'input2')
	
	# create norm mult node
	base_mult = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{desc}_norm_0001')
	set_attr(base_mult, 'operation', 2)
	connect_attr(crv_info, 'arcLength', base_mult, 'input2X')
	connect_attr(scale_fix_mdl, 'outputX', base_mult, 'input1X')
	
	# create volume mult node
	vol_mult = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{desc}_volume_0001')
	set_attr(vol_mult, 'operation', 3)
	
	# create attributes
	add_attr(ctrl, 'VOLUME', 'enum', enum_names=['-------'])
	for axis in 'YZ':
		cmds.addAttr(ctrl, ln=f'com_volume{axis}', attributeType='float', keyable=True, dv=1)
		cmds.addAttr(ctrl, ln=f'str_volume{axis}', attributeType='float', keyable=True, dv=1)
		connect_attr(base_mult, f'outputX', vol_mult, f'input1{axis}')
		
		# create condition node for com and str
		cond = cmds.createNode('condition', n=f'cond_{side}_{region}_{desc}_vol{axis}_0001')
		set_attr(cond, 'operation', 2)
		set_attr(cond, 'secondTerm', 1)
		connect_attr(base_mult, f'outputX', cond, f'firstTerm')
		connect_attr(ctrl, f'com_volume{axis}', cond, f'colorIfTrueR')
		connect_attr(ctrl, f'str_volume{axis}', cond, f'colorIfFalseR')
		
		connect_attr(cond, f'outColorR', vol_mult, f'input2{axis}')
		
		for jnt in bind_joints:
			connect_attr(vol_mult, f'output{axis}', jnt, f'scale{axis}')
	
	
	# ------- push middle controller
	# connect matrix, find distance btw
	start_pos_grps = list(get_parent_grp(drive_locators[0]))
	start_pos_grps.append(drive_locators[0])
	end_pos_grps = list(get_parent_grp(drive_locators[-1]))
	end_pos_grps.append(drive_locators[-1])
	mid_ctrl_grp = list(get_parent_grp(ctrl))
	
	start_matrix = cmds.createNode('multMatrix', n=f'multMatrix_{side}_{region}_{desc}_startPos_0001')
	end_matrix = cmds.createNode('multMatrix', n=f'multMatrix_{side}_{region}_{desc}_endPos_0001')
	mid_matrix = cmds.createNode('multMatrix', n=f'multMatrix_{side}_{region}_{desc}_midPos_0001')
	
	# add attr
	add_attr(ctrl, 'AUTO', 'enum', enum_names=['-------'])
	add_attr(ctrl, 'auto_push', 'float', 1, 0, 1)
	cmds.addAttr(ctrl, ln='auto_push_direction', at='double3', keyable=True)
	for axis in 'XYZ':
		cmds.addAttr(ctrl, ln=f'auto_push_{axis}', at='double', dv=0, parent='auto_push_direction', k=True)

	add_attr(ctrl, 'auto_push_strength', 'float', 1)
	
	for i, groups in enumerate([start_pos_grps[::-1], end_pos_grps[::-1]]):
		for index, grp in enumerate(groups):
			if i == 0:
				connect_attr(grp, 'matrix', start_matrix, f'matrixIn[{index}]')
			else:
				connect_attr(grp, 'matrix', end_matrix, f'matrixIn[{index}]')
	
	temp_mid_ctrl_grps = mid_ctrl_grp[:-1]
	for i, grp in enumerate(temp_mid_ctrl_grps[::-1]):
		connect_attr(grp, 'matrix', mid_matrix, f'matrixIn[{i}]')
		
	# create distance between
	dis_btw_start = cmds.createNode('distanceBetween', n=f'disBtw_{side}_{region}_{desc}_start_0001')
	connect_attr(start_matrix, 'matrixSum', dis_btw_start, 'inMatrix1')
	connect_attr(mid_matrix, 'matrixSum', dis_btw_start, 'inMatrix2')
	
	dis_btw_end = cmds.createNode('distanceBetween', n=f'disBtw_{side}_{region}_{desc}_end_0001')
	connect_attr(end_matrix, 'matrixSum', dis_btw_end, 'inMatrix1')
	connect_attr(mid_matrix, 'matrixSum', dis_btw_end, 'inMatrix2')
	
	pma_dis = cmds.createNode('plusMinusAverage', n=f'pma_{side}_{region}_{desc}_dist_0001')
	connect_attr(dis_btw_start, 'distance', pma_dis, 'input1D[0]')
	connect_attr(dis_btw_end, 'distance', pma_dis, 'input1D[1]')
	
	# create mult push
	mid_norm = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{desc}_midPushNorm_0001')
	set_attr(mid_norm, 'operation', 2)
	mid_dis = get_attr(pma_dis, 'output1D')
	connect_attr(pma_dis, 'output1D', mid_norm, 'input2X')
	set_attr(mid_norm, 'input1X', mid_dis)
	
	# create condition
	mid_cond = cmds.createNode('condition', n=f'cond_{side}_{region}_{desc}_midPush_0001')
	set_attr(mid_cond, 'operation', 2)
	set_attr(mid_cond, 'secondTerm', 1)
	connect_attr(mid_norm, f'outputX', mid_cond, f'firstTerm')
	
	# adl norm
	pma_norm = cmds.createNode('plusMinusAverage', n=f'pma_{side}_{region}_{desc}_midNorm_0001')
	connect_attr(mid_norm, 'outputX', pma_norm, 'input1D[0]')
	set_attr(pma_norm, 'input1D[1]', 1)
	set_attr(pma_norm, 'operation', 2)
	set_attr(mid_cond, 'colorIfFalseR', 0)
	connect_attr(pma_norm, f'output1D', mid_cond, f'colorIfTrueR')
	
	# create strength mult
	mid_strength_mult = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{desc}_strPush_0001')
	connect_attr(ctrl, 'auto_push_strength', mid_strength_mult, 'input1X')
	connect_attr(mid_cond, 'outColorR', mid_strength_mult, 'input2X')
	# create auto-push mult
	auto_mult = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{desc}_autoPush_0001')
	connect_attr(ctrl, 'auto_push', auto_mult, 'input1X')
	connect_attr(mid_strength_mult, 'outputX', auto_mult, 'input2X')
	
	# create push mult
	mid_push_mult = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{desc}_midPush_0001')
	connect_attr(ctrl, 'auto_push_direction', mid_push_mult, 'input1')
	for axis in 'XYZ':
		connect_attr(auto_mult, 'outputX', mid_push_mult, f'input2{axis}')
	connect_attr(mid_push_mult, 'output', mid_ctrl_grp[-1], 'translate')
	

def do_jiggle_deformer(ctrl, curve, up_curve):
	# add attr to ctrl
	add_attr(ctrl, 'JIGGLE', 'enum', enum_names=['-------'])
	add_attr(ctrl, 'envelope', 'float', 0, 0, 1)
	add_attr(ctrl, 'stiffness', 'float', 0.5, 0, 1)
	add_attr(ctrl, 'damping', 'float', 0.1, 0, 1)
	add_attr(ctrl, 'directionBias', 'float', 0, -1, 1)
	add_attr(ctrl, 'weight', 'float', 1, -1, 1)
	
	for crv in [curve, up_curve]:
		crv_point = cmds.select(f'{crv}.cv[2]')
		mel.eval('doJiggle 1 { "0.5", "0.5", "1", "0", "0", "default", "" };')
		jiggle = cmds.ls(cmds.listHistory(crv), type='geometryFilter')[0]
	
		# connect to jiggle deformer
		connect_attr(ctrl, 'envelope', jiggle, 'envelope')
		connect_attr(ctrl, 'stiffness', jiggle, 'stiffness')
		connect_attr(ctrl, 'damping', jiggle, 'damping')
		connect_attr(ctrl, 'directionBias', jiggle, 'directionBias')
		connect_attr(ctrl, 'weight', jiggle, 'jiggleWeight')
		
	cmds.select(clear=True)
	
	
def mirror_attr_value():
	"""
	Get left keyable attribute values and mirror to right side.
	Special case:
	- auto_push_direction (double3): multiply XYZ by -1
	- auto_push_X / Y / Z: multiply value by -1
	"""
	ctrls = cmds.ls('ctrl_l_*_mid_*', type='transform') or []

	skip_prefixes = ("translate", "rotate", "scale")
	skip_exact    = {"visibility"}

	for l_ctrl in ctrls:
		# build right ctrl name
		r_ctrl = l_ctrl.replace('ctrl_l_', 'ctrl_r_')
		if not cmds.objExists(r_ctrl):
			cmds.warning("Right control not found for {} → {}".format(l_ctrl, r_ctrl))
			continue

		attrs = cmds.listAttr(l_ctrl, k=True) or []

		for attr in attrs:
			# skip TRS + vis
			if any(attr.startswith(p) for p in skip_prefixes):
				continue
			if attr in skip_exact:
				continue

			# make sure right side has the same attr
			if not cmds.attributeQuery(attr, node=r_ctrl, exists=True):
				continue

			l_plug = "{}.{}".format(l_ctrl, attr)
			r_plug = "{}.{}".format(r_ctrl, attr)

			try:
				val = cmds.getAttr(l_plug)
			except Exception:
				continue

			# ------------- special cases: auto-push position -------------
			if attr == "auto_push_direction":
				# val is like [(x, y, z)]
				if isinstance(val, (list, tuple)) and val:
					x, y, z = val[0]
					# multiply all components by -1
					cmds.setAttr(r_plug, -x, -y, -z, type="double3")
				continue

			if attr in ("auto_push_X", "auto_push_Y", "auto_push_Z"):
				# scalar float (sometimes comes back as [x])
				if isinstance(val, (list, tuple)):
					val = val[0]
				cmds.setAttr(r_plug, -val)
				continue

			# ------------- default: just copy the value -------------
			if isinstance(val, (list, tuple)) and len(val) == 1:
				val = val[0]

			try:
				cmds.setAttr(r_plug, val)
			except Exception:
				# handle strings etc.
				if isinstance(val, str):
					try:
						cmds.setAttr(r_plug, val, type="string")
					except Exception:
						pass
				else:
					pass

	

def create_muscle_set_up(input_jnt, constraint_jnt_1, constraint_jnt_2, mirror, uniform=True, jnt_num=5, offset=0.5):
	if mirror:
		sides = ['l', 'r']
	else:
		sides = ['l']
	
	for side in sides:
		loc_drivens, curve, up_curve = create_muscle_jnt_controllers(input_jnt, side, jnt_num, parent=constraint_jnt_1, offset=offset)
		
		# locator driven groups
		loc_start = loc_drivens[0]
		loc_end = loc_drivens[-1]
		
		# constraint driver locators driven group
		jnt1 = constraint_jnt_1.replace('_l_', f'_{side}_')
		jnt2 = constraint_jnt_2.replace('_l_', f'_{side}_')
		
		cons1 = cmds.parentConstraint(jnt1, loc_start, mo=True)[0]
		cons2 = cmds.parentConstraint(jnt2, loc_end, mo=True)[0]
		set_attr(cons1, 'interpType', 2)
		set_attr(cons2, 'interpType', 2)
		
		if uniform:
			for crv in [curve, up_curve]:
				cmds.rebuildCurve(crv,
								  rebuildType=0,  # Uniform
								  keepRange=0,  # 0 to 1
								  keepEndPoints=True,  # Keep ends
								  keepTangents=False,
								  spans=10,
								  degree=2,
								  keepControlPoints=False,
								  replaceOriginal=True,
								  ch=True
								  )


# ----------------- UI ----------------- #

def _muscle_load_selected_into(field_name):
	"""
	Utility: load first selected joint into a textFieldButtonGrp.
	"""
	sel = cmds.ls(sl=True, type="joint")
	if not sel:
		cmds.warning("Please select a joint first.")
		return
	cmds.textFieldButtonGrp(field_name, e=True, text=sel[0])


def _run_muscle_setup_from_ui(*_):
	"""
	Read values from UI and call create_muscle_set_up.
	"""
	# Query fields
	input_jnt = cmds.textFieldButtonGrp("muscle_input_jnt_tfb", q=True, text=True)
	con_jnt_1 = cmds.textFieldButtonGrp("muscle_con1_jnt_tfb", q=True, text=True)
	con_jnt_2 = cmds.textFieldButtonGrp("muscle_con2_jnt_tfb", q=True, text=True)
	
	mirror = cmds.checkBox("muscle_mirror_cb", q=True, value=True)
	uniform = cmds.checkBox("muscle_uniform_cb", q=True, value=True)
	jnt_num = cmds.intField("muscle_jntnum_if", q=True, value=True)
	offset = cmds.floatField("muscle_offset_if", q=True, value=True)
	
	# Basic validation
	if not input_jnt or not cmds.objExists(input_jnt):
		cmds.warning("Input long muscle joint is invalid or does not exist.")
		return
	if not con_jnt_1 or not cmds.objExists(con_jnt_1):
		cmds.warning("Constraint Joint 1 is invalid or does not exist.")
		return
	if not con_jnt_2 or not cmds.objExists(con_jnt_2):
		cmds.warning("Constraint Joint 2 is invalid or does not exist.")
		return
	if jnt_num < 3:
		cmds.warning("jnt_num should be at least 3.")
		return
	
	# Run your main function
	create_muscle_set_up(
		input_jnt=input_jnt,
		constraint_jnt_1=con_jnt_1,
		constraint_jnt_2=con_jnt_2,
		mirror=mirror,
		uniform=uniform,
		jnt_num=jnt_num,
		offset=offset
	)


def create_muscle_setup_ui():
	"""
	Compact, cleaner window layout (no sliders).
	"""
	win_name = "muscleSetupUI_win"
	if cmds.window(win_name, exists=True):
		cmds.deleteUI(win_name)
	
	win = cmds.window(
		win_name,
		title="Muscle Setup",
		sizeable=True,
		widthHeight=(320, 260),
		minimizeButton=True,
		maximizeButton=False
	)
	
	main_col = cmds.columnLayout(adj=True, rs=6, co=("both", 8))
	
	cmds.text(l="Muscle Setup", al="center", h=20)
	cmds.separator(h=6, style="in")
	
	# ---------- Input joints ----------
	cmds.frameLayout(
		label="Joints",
		collapsable=False,
		borderVisible=True,
		mw=4,
		mh=4
	)
	cmds.columnLayout(adj=True, rs=4)
	
	cmds.textFieldButtonGrp(
		"muscle_input_jnt_tfb",
		label="Input muscle:",
		buttonLabel="<< Sel",
		text="jnt_l_ft_longTriceps_0001_0001",
		buttonCommand=lambda *_: _muscle_load_selected_into("muscle_input_jnt_tfb"),
		columnWidth=[(1, 90), (2, 170), (3, 50)]
	)
	
	cmds.textFieldButtonGrp(
		"muscle_con1_jnt_tfb",
		label="Constraint 1:",
		buttonLabel="<< Sel",
		text="jnt_l_ft_upperlegTwist_0001",
		buttonCommand=lambda *_: _muscle_load_selected_into("muscle_con1_jnt_tfb"),
		columnWidth=[(1, 90), (2, 170), (3, 50)]
	)
	
	cmds.textFieldButtonGrp(
		"muscle_con2_jnt_tfb",
		label="Constraint 2:",
		buttonLabel="<< Sel",
		text="jnt_l_ft_kneeTwist_0001",
		buttonCommand=lambda *_: _muscle_load_selected_into("muscle_con2_jnt_tfb"),
		columnWidth=[(1, 90), (2, 170), (3, 50)]
	)
	
	cmds.rowColumnLayout(nc=2, cw=[(1, 120), (2, 80)])
	cmds.text(l="Up Curve Offset:")
	cmds.floatField("muscle_offset_if", value=0.3, pre=2)
	
	cmds.setParent(main_col)
	cmds.separator(h=4, style="none")
	
	# ---------- Options ----------
	cmds.frameLayout(
		label="Options",
		collapsable=False,
		borderVisible=True,
		mw=4,
		mh=4
	)
	
	cmds.rowColumnLayout(nc=2, cw=[(1, 120), (2, 130)])
	cmds.text(l="Mirror L/R:")
	cmds.checkBox("muscle_mirror_cb", l="", value=True)
	cmds.text(l="Uniform rebuild:")
	cmds.checkBox("muscle_uniform_cb", l="", value=True)
	cmds.setParent("..")
	
	cmds.rowColumnLayout(nc=2, cw=[(1, 120), (2, 80)])
	cmds.text(l="Bind joint count:")
	cmds.intField("muscle_jntnum_if", value=5, minValue=3)
	cmds.setParent(main_col)
	
	cmds.separator(h=8, style="none")
	
	# ---------- Button ----------
	cmds.button(
		l="Create Muscle Setup",
		h=32,
		c=_run_muscle_setup_from_ui
	)
	
	cmds.separator(h=4, style="none")
	
	cmds.button(
		l="Mirror Mid Ctrl Attributes",
		h=28,
		c=lambda *_: mirror_attr_value()
	)
	
	cmds.separator(h=4, style="none")
	
	cmds.showWindow(win)

create_muscle_setup_ui()

# create_muscle_set_up('jnt_l_ft_longTriceps_0001_0001',
# 					 'jnt_l_ft_upperlegTwist_0001',
# 					 'jnt_l_ft_kneeTwist_0001',
# 					 uniform=True,
# 					 jnt_num=5,
# 					 mirror=False)