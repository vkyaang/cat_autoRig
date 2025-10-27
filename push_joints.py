import maya.cmds as cmds

# -----------------HELPERS---------- #
def add_attr(node, long_name, attr_type, default_value=None, min_value=None, max_value=None, keyable=True,
			 enum_names=None):
	"""
	Add attribute with optional min/max limits or enum values.
	Example:
		AutoRigHelpers.add_attr(ctrl, 'stretch', 'float', 0, 0, 1)
		AutoRigHelpers.add_attr(ctrl, 'space', 'enum', enum_names=['World', 'Local', 'Chest'])
	"""
	args = {
		"longName": long_name,
		"keyable": keyable,
	}
	
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
		# expect a list that will be unpacked for the command
		cmds.setAttr("{0}.{1}".format(node, attr), *value, type=value_type)
	else:
		cmds.setAttr("{0}.{1}".format(node, attr), value)

def get_attr(node, attr):
	attr_value = cmds.getAttr("{0}.{1}".format(node, attr))
	
	return attr_value

def connect_attr(node_a, attr_a, node_b, attr_b, force=False):
	cmds.connectAttr("{0}.{1}".format(node_a, attr_a), "{0}.{1}".format(node_b, attr_b), force=force)
	
# -----------------HELPERS----------


# ----------------- setup

def add_pose(name, region, side, offset_grp, input_jnt, push_jnt, axis, start_val, end_val):
	"""
	add pose:
		1) create ref locator
		2) add pose attr
		3) create remapValue node (only initialize values if node was newly created)
	"""
	i = 1

	loc_name = f'loc_{side}_{region}_{name}_pushPose_{i:04d}'
	pose_attr_name = f'pose{i:02d}'
	
	trans_mult_name = n = f'mult_{side}_{region}_{name}_pushPose_trans_{i:04d}'
	rot_mult_name = n = f'mult_{side}_{region}_{name}_pushPose_rot_{i:04d}'
	scale_mult_name = n = f'mult_{side}_{region}_{name}_pushPose_scale_{i:04d}'
	pma_input = f'input3D[{i - 1}]'
	
	while cmds.objExists(f"{input_jnt}.{pose_attr_name}"):
		i += 1
		pose_attr_name = f'pose_{i:02d}'
		loc_name = f'loc_{side}_{region}_{name}_pushPose_{i:04d}'
		trans_mult_name = f'mult_{side}_{region}_{name}_pushPose_trans_{i:04d}'
		rot_mult_name = f'mult_{side}_{region}_{name}_pushPose_rot_{i:04d}'
		scale_mult_name = f'mult_{side}_{region}_{name}_pushPose_scale_{i:04d}'
		pma_input = f'input3D[{i-1}]'
		mult_input = f'input{i}'
	
	# --- create pose locator ---
	loc = cmds.spaceLocator(name=loc_name)[0]
	cmds.matchTransform(loc, offset_grp)
	cmds.parent(loc, offset_grp)
	
	# --- add pose attr to input joint ---
	cmds.addAttr(input_jnt, ln=pose_attr_name, at='float', min=0, max=1, dv=0, k=True)
	
	# --- create or reuse remapValue node ---
	rmp_name = f'rmp_{side}_{region}_{name}_pushPose_0001'
	is_new = cmds.objExists(rmp_name)
	
	rmp_node = cmds.createNode('remapValue', n=rmp_name)
	
	# --- connect joint's axis to remap input ---
	cmds.connectAttr(f"{input_jnt}.{axis}", f"{rmp_node}.inputValue", f=True)
	cmds.setAttr(f"{rmp_node}.inputMin", start_val)
	cmds.setAttr(f"{rmp_node}.inputMax", end_val)
	
	# connect remap out value to pose attr
	connect_attr(rmp_node, 'outValue', input_jnt, pose_attr_name)
	
	# # --- only initialize defaults if node is new ---
	# if is_new:
	# 	print(f"New remap node created: {rmp_node}")
	# 	cmds.setAttr(f"{rmp_node}.value[1].value_FloatValue", 0)
	# 	cmds.setAttr(f"{rmp_node}.value[2].value_Interp", 1)
	# 	cmds.setAttr(f"{rmp_node}.value[2].value_FloatValue", 1)
	# 	cmds.setAttr(f"{rmp_node}.value[2].value_Position", 0.5)

	# connect ref locators value
	trans_mult = cmds.createNode('multiplyDivide', n=trans_mult_name)
	rot_mult = cmds.createNode('multiplyDivide', n=rot_mult_name)
	scale_mult = cmds.createNode('multiplyDivide', n=scale_mult_name)
	set_attr(scale_mult, 'operation', 3)
	

	for i in ['X', 'Y', 'Z']:
		connect_attr(input_jnt, pose_attr_name, trans_mult, f'input2{i}')
		connect_attr(input_jnt, pose_attr_name, rot_mult, f'input2{i}')
		connect_attr(input_jnt, pose_attr_name, scale_mult, f'input2{i}')
		
	# connect translate
	connect_attr(loc, 'translate', trans_mult, 'input1')
	connect_attr(loc, 'rotate', rot_mult, 'input1')
	connect_attr(loc, 'scale', scale_mult, 'input1')
	
	# create plus minus average node for trans and rot
	for attr in ['translate', 'rotate', 'scale']:
		pma_name = f'pma_{side}_{region}_{name}_pushPose_{attr}Output_0001'
		
		if not cmds.objExists(pma_name):
			pma_node = cmds.createNode('plusMinusAverage', n=pma_name)
			connect_attr(pma_node, 'output3D', push_jnt, f'{attr}')
		else:
			pma_node = pma_name
		
		if attr == 'translate':
			connect_attr(trans_mult, 'output', pma_node, pma_input)
		elif attr == 'rotate':
			connect_attr(rot_mult, 'output', pma_node, pma_input)
		
	# --- connect output mult scale ---
	pose_num = int(''.join([c for c in pose_attr_name if c.isdigit()]))
	output_mult_scale_name = f'mult_{side}_{region}_{name}_pushPose_scaleOutput_0001'
	existing_output_mults = cmds.ls(f'mult_{side}_{region}_{name}_pushPose_scaleOutput_*', type='multiplyDivide') or []
	total_existing = len(existing_output_mults)
	
	# === CASE 1: For the first two poses (pose01, pose02) ===
	if pose_num <= 2:
		# create only one output mult node (if not already)
		if not cmds.objExists(output_mult_scale_name):
			output_mult_scale_node = cmds.createNode('multiplyDivide', n=output_mult_scale_name)
			connect_attr(output_mult_scale_node, 'output', push_jnt, 'scale', force=True)
		else:
			output_mult_scale_node = output_mult_scale_name
		
		# connect both pose01 and pose02 scale_mult outputs to input1/input2
		if pose_num == 1:
			connect_attr(scale_mult, 'output', output_mult_scale_node, 'input1', force=True)
		else:
			connect_attr(scale_mult, 'output', output_mult_scale_node, 'input2', force=True)
	
	# === CASE 2: For pose03 and higher ===
	else:
		prev_index = pose_num - 2
		prev_mult = f'mult_{side}_{region}_{name}_pushPose_scaleOutput_{prev_index:04d}'
		this_mult = f'mult_{side}_{region}_{name}_pushPose_scaleOutput_{pose_num - 1:04d}'
		
		# create new output node if not exists
		if not cmds.objExists(this_mult):
			this_mult = cmds.createNode('multiplyDivide', n=this_mult)
		
		# chain previous output into new one
		connect_attr(prev_mult, 'output', this_mult, 'input1', force=True)
		connect_attr(scale_mult, 'output', this_mult, 'input2', force=True)
		connect_attr(this_mult, 'output', push_jnt, 'scale', force=True)


def create_push_joints(input_joint, cons_joint1, cons_joint2, name, region, axis, offset_axis, offset_val, start_val, end_val):
	
	input_parts = input_joint.split('_')
	cons_jnt01_parts = cons_joint1.split('_')
	cons_jnt02_parts = cons_joint2.split('_')
	
	for side in ['l', 'r']:
		# define input joints
		new_input_parts = input_parts[:]
		new_cons01_parts = cons_jnt01_parts[:]
		new_cons02_parts = cons_jnt02_parts[:]
		
		new_input_parts[1] = side
		new_cons01_parts[1] = side
		new_cons02_parts[1] = side
		
		joint = "_".join(new_input_parts)
		cons_joint1 = "_".join(new_cons01_parts)
		cons_joint2 = "_".join(new_cons02_parts)
		
		skel_jnt = joint.replace('jnt', 'skel')
		
		# create push joints
		jnt_zero_name = f'zero_{side}_{region}_{name}_push_0001'
		jnt_offset_name = f'offset_{side}_{region}_{name}_push_0001'
		jnt_name = f'jnt_{side}_{region}_{name}_push_0001'
		skel_jnt_name = jnt_name.replace('jnt', 'skel')

		if not cmds.objExists(jnt_zero_name):
			# create zero group
			zero = cmds.createNode('transform', name=jnt_zero_name)
			offset = cmds.createNode('transform', name=jnt_offset_name, p=zero)
			jnt = cmds.createNode('joint', name=jnt_name, p=offset)
			
			# create skeleton push joint
			skel_jnt = cmds.createNode('joint', name=skel_jnt_name, p=skel_jnt)
			# connect joint to skeleton joint
			attrs = ['translate', 'rotate', 'scale']
			for a in attrs:
				cmds.connectAttr(f'{jnt}.{a}', f'{skel_jnt}.{a}')

			# match transform to joint
			cmds.matchTransform(zero, joint)
			cmds.parent(zero, joint)
			
			# create orient contraint
			ori_cons = cmds.orientConstraint(cons_joint1, cons_joint2, zero, mo=False)[0]
			set_attr(ori_cons, 'interpType', 2)
			# move offset group
			if side == 'l':
				set_attr(offset, offset_axis, get_attr(offset, offset_axis) + offset_val*-1)
			elif side == 'r':
				set_attr(offset, offset_axis, get_attr(offset, offset_axis) + offset_val)
			
			add_pose(name, region, side, offset, joint, jnt, axis, start_val, end_val)

		else:
			add_pose(name, region, side, jnt_offset_name, joint, jnt_name, axis, start_val, end_val)


# ======================================
# ==========  BUILD THE UI  ============
# ======================================

def push_pose_ui():
	if cmds.window("pushPoseUI", exists=True):
		cmds.deleteUI("pushPoseUI")
	
	cmds.window("pushPoseUI", title="Push Pose Rig Builder", widthHeight=(420, 500))
	cmds.columnLayout(adj=True, columnAlign="center")
	
	cmds.text(label="Push Pose Setup", h=30, bgc=[0.2, 0.2, 0.2])
	cmds.separator(h=8)
	
	input_joint_field = cmds.textFieldGrp(label="Input Joint:", cw2=(120, 280))
	cons_joint1_field = cmds.textFieldGrp(label="Constraint Joint 1:", cw2=(120, 280))
	cons_joint2_field = cmds.textFieldGrp(label="Constraint Joint 2:", cw2=(120, 280))
	name_field = cmds.textFieldGrp(label="Name:", cw2=(120, 280))
	region_field = cmds.textFieldGrp(label="Region:", cw2=(120, 280))
	axis_field = cmds.optionMenuGrp(label="Driving Axis:", cw2=(120, 180))
	for ax in ['rotateX', 'rotateY', 'rotateZ', 'translateX', 'translateY', 'translateZ']:
		cmds.menuItem(label=ax)
	offset_axis_field = cmds.optionMenuGrp(label="Offset Axis:", cw2=(120, 180))
	for ax in ['translateX', 'translateY', 'translateZ']:
		cmds.menuItem(label=ax)
	offset_val_field = cmds.floatFieldGrp(label="Offset Value:", value1=1.3, cw2=(120, 100))
	start_val_field = cmds.floatFieldGrp(label="Start Value:", value1=0.0, cw2=(120, 100))
	end_val_field = cmds.floatFieldGrp(label="End Value:", value1=90.0, cw2=(120, 100))
	
	cmds.separator(h=10)
	
	def build_push_pose(*_):
		input_joint = cmds.textFieldGrp(input_joint_field, q=True, text=True)
		cons_joint1 = cmds.textFieldGrp(cons_joint1_field, q=True, text=True)
		cons_joint2 = cmds.textFieldGrp(cons_joint2_field, q=True, text=True)
		name = cmds.textFieldGrp(name_field, q=True, text=True)
		region = cmds.textFieldGrp(region_field, q=True, text=True)
		axis = cmds.optionMenuGrp(axis_field, q=True, v=True)
		offset_axis = cmds.optionMenuGrp(offset_axis_field, q=True, v=True)
		offset_val = cmds.floatFieldGrp(offset_val_field, q=True, value1=True)
		start_val = cmds.floatFieldGrp(start_val_field, q=True, value1=True)
		end_val = cmds.floatFieldGrp(end_val_field, q=True, value1=True)
		
		create_push_joints(input_joint, cons_joint1, cons_joint2, name, region, axis, offset_axis, offset_val, start_val, end_val)
		cmds.inViewMessage(amg=f"✅ Push pose created for <hl>{name}</hl>", pos="midCenter", fade=True)
	
	cmds.button(label="Create Push Pose", h=40, bgc=[0.3, 0.5, 0.3], command=build_push_pose)
	cmds.separator(h=10)
	cmds.showWindow("pushPoseUI")


# Run it:
push_pose_ui()