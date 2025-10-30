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


def _push_index_from_name(push_jnt):
	try:
		return push_jnt.split("_")[-1]
	except Exception:
		return "0001"


def _ensure_node(name, type_name):
	if cmds.objExists(name):
		return name
	return cmds.createNode(type_name, n=name)


def _lr_mirror(name):
	if "_l_" in name:
		return name.replace("_l_", "_r_", 1)
	elif "_r_" in name:
		return name.replace("_r_", "_l_", 1)
	return name


# ----------------- SETUP ----------------- #

def create_push_setup(input_joint, cons_joint1, cons_joint2, name, region, axis, offset_axis, offset_val):
	if not cmds.objExists(input_joint):
		cmds.warning("Input joint does not exist.")
		return
	
	parts = input_joint.split('_')
	if len(parts) < 4:
		cmds.warning("Input joint name does not match expected token pattern.")
		return
	
	for side in ["l", "r"]:
		joint = input_joint.replace("_l_", f"_{side}_").replace("_r_", f"_{side}_")
		c1 = cons_joint1.replace("_l_", f"_{side}_").replace("_r_", f"_{side}_")
		c2 = cons_joint2.replace("_l_", f"_{side}_").replace("_r_", f"_{side}_")
		
		if not cmds.objExists(joint):
			cmds.warning("Input joint missing for side {}: {}".format(side, joint))
			continue
		
		existing = cmds.ls(f"jnt_{side}_{region}_{name}_push_*", type="joint") or []
		next_idx = len(existing) + 1
		idx = f"{next_idx:04d}"
		
		jnt_name = f'jnt_{side}_{region}_{name}_push_{idx}'
		zero_name = jnt_name.replace('jnt', 'zero')
		offset_name = jnt_name.replace('jnt', 'offset')
		skel_name = jnt_name.replace('jnt', 'skel')
		
		zero = cmds.createNode('transform', name=zero_name)
		offset = cmds.createNode('transform', name=offset_name, p=zero)
		jnt = cmds.createNode('joint', name=jnt_name, p=offset)
		
		cmds.matchTransform(zero, joint)
		cmds.parent(zero, joint)
		
		if cmds.objExists(c1) and cmds.objExists(c2):
			ori_cons = cmds.orientConstraint(c1, c2, zero, mo=False)[0]
			set_attr(ori_cons, 'interpType', 2)
		
		if side == 'l':
			set_attr(offset, offset_axis, get_attr(offset, offset_axis) - offset_val)
		else:
			set_attr(offset, offset_axis, get_attr(offset, offset_axis) + offset_val)
		
		skel_input_parent = joint.replace('jnt', 'skel')
		if not cmds.objExists(skel_input_parent):
			cmds.warning("Skel parent '{}' does not exist; creating under world.".format(skel_input_parent))
			skel_input_parent = None
		
		skel_jnt = cmds.createNode('joint', name=skel_name, p=skel_input_parent)
		cmds.matchTransform(skel_jnt, jnt)
		
		cmds.pointConstraint(jnt, skel_jnt, mo=False)
		cmds.orientConstraint(jnt, skel_jnt, mo=False)
		connect_attr(jnt, 'scale', skel_jnt, 'scale')
		
		print(f"Created {jnt_name}")
	return


# ----------------- ADD POSE ----------------- #

def use_pose_attr(input_jnt):
	attr_i = 1
	pose_attr_name = f'pose{attr_i:02d}'
	while cmds.objExists(f"{input_jnt}.{pose_attr_name}"):
		attr_i += 1
		pose_attr_name = f'pose{attr_i:02d}'
	if not cmds.attributeQuery(pose_attr_name, n=input_jnt, exists=True):
		cmds.addAttr(input_jnt, ln=pose_attr_name, at='float', min=0, max=1, dv=0, k=True)
	return pose_attr_name


def add_pose_to_push(push_jnt, input_jnt, name, region, axis, start_val, end_val, rmp_pos_val, pose_attr=True):
	if not cmds.objExists(push_jnt) or not cmds.objExists(input_jnt):
		return
	
	side = _side_from_name(push_jnt)
	push_idx = _push_index_from_name(push_jnt)
	offset_grp = push_jnt.replace('jnt_', 'offset_')
	if not cmds.objExists(offset_grp):
		return
	
	# count existing poses
	if pose_attr:
		# count real remap nodes when pose mode ON
		rmp_pat = f'rmp_{side}_{region}_{name}_pushPose_{push_idx}_*'
		existing_rmps = cmds.ls(rmp_pat, type='remapValue') or []
		local_i = len(existing_rmps) + 1
	else:
		# pose_attr OFF → count existing locators instead (fake remap count)
		fake_locs = cmds.ls(f"loc_{side}_{region}_{name}_pushPose_{push_idx}_*", type="transform") or []
		local_i = len(fake_locs) + 1
	
	pose_number = local_i  # track pose index even if no rmp
	
	loc_name = f"loc_{side}_{region}_{name}_pushPose_{push_idx}_{pose_number:04d}"
	loc = cmds.spaceLocator(name=loc_name)[0]
	cmds.matchTransform(loc, offset_grp)
	cmds.parent(loc, offset_grp)
	
	# -------------------------
	# Pose Attribute path
	# -------------------------
	if pose_attr:
		rmp_name = f'rmp_{side}_{region}_{name}_pushPose_{push_idx}_{pose_number:04d}'
		rmp_node = cmds.createNode('remapValue', n=rmp_name)
		connect_attr(input_jnt, axis, rmp_node, 'inputValue', True)
		set_attr(rmp_node, 'inputMin', start_val)
		set_attr(rmp_node, 'inputMax', end_val)
		
		# remap chain logic stays SAME
		if pose_number > 1:
			prev_rmp = f'rmp_{side}_{region}_{name}_pushPose_{push_idx}_{(pose_number - 1):04d}'
			if cmds.objExists(prev_rmp):
				set_attr(prev_rmp, "value[1].value_Position", rmp_pos_val)
				set_attr(prev_rmp, "value[1].value_FloatValue", 1)
				set_attr(prev_rmp, "value[1].value_Interp", 1)
				set_attr(prev_rmp, "value[2].value_Position", 1)
				set_attr(prev_rmp, "value[2].value_FloatValue", 0)
		
		# Create pose attribute and drive with remap
		pose_attr_name = use_pose_attr(input_jnt)
		connect_attr(rmp_node, 'outValue', input_jnt, pose_attr_name, True)
	else:
		#  No Remap Path
		rmp_node = None
		pose_attr_name = None
		# no remap
		pass
	
	# MultiplyDivide nodes
	mdT = cmds.createNode('multiplyDivide',
						  n=f'mult_{side}_{region}_{name}_pushPose_trans_{push_idx}_{pose_number:04d}')
	mdR = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_{name}_pushPose_rot_{push_idx}_{pose_number:04d}')
	mdS = cmds.createNode('multiplyDivide',
						  n=f'mult_{side}_{region}_{name}_pushPose_scale_{push_idx}_{pose_number:04d}')
	set_attr(mdS, 'operation', 3)
	
	# If using pose attr connect attr
	if pose_attr:
		for ax in 'XYZ':
			connect_attr(input_jnt, pose_attr_name, mdT, f'input2{ax}', True)
			connect_attr(input_jnt, pose_attr_name, mdR, f'input2{ax}', True)
			connect_attr(input_jnt, pose_attr_name, mdS, f'input2{ax}', True)
	
	# loc drives
	connect_attr(loc, 'translate', mdT, 'input1', True)
	connect_attr(loc, 'rotate', mdR, 'input1', True)
	connect_attr(loc, 'scale', mdS, 'input1', True)
	
	# PMA for translate / rotate
	for attr, md in (('translate', mdT), ('rotate', mdR)):
		pma_name = f'pma_{side}_{region}_{name}_pushPose_{attr}_{push_idx}'
		if not cmds.objExists(pma_name):
			pma_node = cmds.createNode('plusMinusAverage', n=pma_name)
			connect_attr(pma_node, 'output3D', push_jnt, attr, True)
		else:
			pma_node = pma_name
		connect_attr(md, 'output', pma_node, f'input3D[{pose_number - 1}]', True)
	
	# Scale chain
	scale_base = f"mult_{side}_{region}_{name}_pushPose_scaleOutput_{push_idx}"
	if pose_number <= 2:
		out = f"{scale_base}_0001"
		if not cmds.objExists(out):
			out = cmds.createNode("multiplyDivide", n=out)
			connect_attr(out, "output", push_jnt, "scale", True)
		connect_attr(mdS, "output", out, "input1" if pose_number == 1 else "input2", True)
	else:
		prev = f"{scale_base}_{(pose_number - 2):04d}"
		out = f"{scale_base}_{(pose_number - 1):04d}"
		if not cmds.objExists(prev):
			prev = cmds.createNode("multiplyDivide", n=prev)
			if pose_number == 3 and not cmds.listConnections(f"{push_jnt}.scale", s=True, d=False):
				connect_attr(prev, "output", push_jnt, "scale", True)
		if not cmds.objExists(out):
			out = cmds.createNode("multiplyDivide", n=out)
		connect_attr(prev, "output", out, "input1", True)
		connect_attr(mdS, "output", out, "input2", True)
		connect_attr(out, "output", push_jnt, "scale", True)
	
	cmds.inViewMessage(amg=f"Pose added to {push_jnt} (pose_attr={pose_attr})", pos="midCenter", fade=True)


# ----------------- AUTO ADD ----------------- #

def auto_add_pose(push_jnt, input_jnt, name, region, axis, start_val, end_val, rmp1, rmp2, pose_attr=True):
	total = end_val - start_val
	one_third = start_val + total * (1.0 / 3.0)
	two_third = start_val + total * (2.0 / 3.0)
	
	add_pose_both_sides(push_jnt, input_jnt, name, region, axis, start_val, two_third, rmp1, pose_attr)
	add_pose_both_sides(push_jnt, input_jnt, name, region, axis, one_third, end_val, rmp2, pose_attr)
	add_pose_both_sides(push_jnt, input_jnt, name, region, axis, two_third, end_val, 1.0, pose_attr)
	
	side = _side_from_name(push_jnt)
	push_idx = _push_index_from_name(push_jnt)
	mid_rmp = cmds.ls(f"rmp_{side}_{region}_{name}_pushPose_{push_idx}_0002", type="remapValue")
	
	if mid_rmp:
		mid_rmp = mid_rmp[0]
		cmds.setAttr(f"{mid_rmp}.value[1].value_Position", rmp2)
	
	cmds.inViewMessage(amg="<hl>Auto poses added (mid rmp preserved)</hl>", pos="midCenter", fade=True)


# ----------------- BOTH SIDES ----------------- #

def add_pose_both_sides(push_jnt, input_jnt, name, region, axis, start_val, end_val, rmp_pos_val, pose_attr=True):
	add_pose_to_push(push_jnt, input_jnt, name, region, axis, start_val, end_val, rmp_pos_val, pose_attr)
	
	mirror_push = _lr_mirror(push_jnt)
	mirror_input = _lr_mirror(input_jnt)
	if mirror_push != push_jnt and cmds.objExists(mirror_push) and cmds.objExists(mirror_input):
		add_pose_to_push(mirror_push, mirror_input, name, region, axis, start_val, end_val, rmp_pos_val, pose_attr)


# ----------------- UI ----------------- #

def push_pose_ui():
	if cmds.window("pushJointUI", exists=True):
		cmds.deleteUI("pushJointUI")
	
	cmds.window("pushJointUI", title="Push Joint Builder", widthHeight=(440, 600))
	cmds.columnLayout(adj=True, columnAlign="center")
	
	cmds.text(label="Push Joint Setup (no pose)", h=28, bgc=[0.22, 0.22, 0.22])
	cmds.separator(h=6)
	
	input_joint_field = cmds.textFieldGrp(label="Input Joint:", text='jnt_l_bk_kneeTwist_0001', cw2=(140, 260))
	cons_joint1_field = cmds.textFieldGrp(label="Constraint Joint 1:", text='jnt_l_bk_upperlegTwist_0005',
										  cw2=(140, 260))
	cons_joint2_field = cmds.textFieldGrp(label="Constraint Joint 2:", text='jnt_l_bk_kneeTwist_0001', cw2=(140, 260))
	name_field = cmds.textFieldGrp(label="Name:", cw2=(140, 260))
	region_field = cmds.textFieldGrp(label="Region:", cw2=(140, 260))
	axis_field = cmds.optionMenuGrp(label="Driving Axis:", cw2=(140, 180))
	for ax in ['rotateX', 'rotateY', 'rotateZ', 'translateX', 'translateY', 'translateZ']:
		cmds.menuItem(label=ax)
	offset_axis_field = cmds.optionMenuGrp(label="Offset Axis:", cw2=(140, 180))
	for ax in ['translateX', 'translateY', 'translateZ']:
		cmds.menuItem(label=ax)
	offset_val_field = cmds.floatFieldGrp(label="Offset Value:", value1=1.3, cw2=(140, 100))
	
	cmds.separator(h=10)
	
	cmds.text(label="Add Pose to Existing Push Joint", h=28, bgc=[0.22, 0.22, 0.22])
	cmds.separator(h=6)
	
	push_jnt_field = cmds.textFieldGrp(label="Push Joint (target):", cw2=(140, 260))
	input_for_pose = cmds.textFieldGrp(label="Input Joint (driver):", text='jnt_l_bk_kneeTwist_0001', cw2=(140, 260))
	start_val_field = cmds.floatFieldGrp(label="Pose Start:", value1=0.0, cw2=(140, 100))
	end_val_field = cmds.floatFieldGrp(label="Pose End:", value1=90.0, cw2=(140, 100))
	pos_val_field = cmds.floatFieldGrp(label="Remap Pos Value:", value1=0.5, cw2=(140, 100))
	auto_rmp1_field = cmds.floatFieldGrp(label="Auto RMP 1 (wide):", value1=0.5, cw2=(140, 100))
	auto_rmp2_field = cmds.floatFieldGrp(label="Auto RMP 2 (mid):", value1=0.5, cw2=(140, 100))
	
	global use_pose_attr_checkbox
	use_pose_attr_checkbox = cmds.checkBox(label="Use Pose Attribute", value=True)
	
	name_for_pose_field = name_field
	region_for_pose_field = region_field
	
	def on_setup(*_):
		create_push_setup(
			cmds.textFieldGrp(input_joint_field, q=True, text=True),
			cmds.textFieldGrp(cons_joint1_field, q=True, text=True),
			cmds.textFieldGrp(cons_joint2_field, q=True, text=True),
			cmds.textFieldGrp(name_field, q=True, text=True),
			cmds.textFieldGrp(region_field, q=True, text=True),
			cmds.optionMenuGrp(axis_field, q=True, v=True),
			cmds.optionMenuGrp(offset_axis_field, q=True, v=True),
			cmds.floatFieldGrp(offset_val_field, q=True, value1=True),
		)
	
	def on_add_pose(*_):
		pose_flag = cmds.checkBox(use_pose_attr_checkbox, q=True, value=True)
		add_pose_both_sides(
			cmds.textFieldGrp(push_jnt_field, q=True, text=True),
			cmds.textFieldGrp(input_for_pose, q=True, text=True),
			cmds.textFieldGrp(name_for_pose_field, q=True, text=True),
			cmds.textFieldGrp(region_for_pose_field, q=True, text=True),
			cmds.optionMenuGrp(axis_field, q=True, v=True),
			cmds.floatFieldGrp(start_val_field, q=True, value1=True),
			cmds.floatFieldGrp(end_val_field, q=True, value1=True),
			cmds.floatFieldGrp(pos_val_field, q=True, value1=True),
			pose_flag
		)
	
	cmds.button(label="Create Push Setup (no pose)", h=40, bgc=[0.30, 0.55, 0.30], c=on_setup)
	cmds.separator(h=8)
	cmds.button(label="Add Pose To Push Joint (L & R)", h=40, bgc=[0.30, 0.35, 0.70], c=on_add_pose)
	cmds.separator(h=10)
	
	def on_auto_pose(*_):
		pose_flag = cmds.checkBox(use_pose_attr_checkbox, q=True, value=True)
		auto_add_pose(
			cmds.textFieldGrp(push_jnt_field, q=True, text=True),
			cmds.textFieldGrp(input_for_pose, q=True, text=True),
			cmds.textFieldGrp(name_for_pose_field, q=True, text=True),
			cmds.textFieldGrp(region_for_pose_field, q=True, text=True),
			cmds.optionMenuGrp(axis_field, q=True, v=True),
			cmds.floatFieldGrp(start_val_field, q=True, value1=True),
			cmds.floatFieldGrp(end_val_field, q=True, value1=True),
			cmds.floatFieldGrp(auto_rmp1_field, q=True, value1=True),
			cmds.floatFieldGrp(auto_rmp2_field, q=True, value1=True),
			pose_flag
		)
	
	cmds.button(label="AUTO Add 3 Split Poses", h=40, bgc=[0.65, 0.45, 0.20], c=on_auto_pose)
	cmds.separator(h=10)
	
	cmds.showWindow("pushJointUI")


push_pose_ui()
