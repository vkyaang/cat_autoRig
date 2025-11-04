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


ft_upperleg_jnt = 'jnt_l_ft_upperlegTwist_0001'

# 1. rz=120, 2. rz=-50, 3. ry=90 4. ry=-40

# ft_upperleg_dict = [
# 	{'rotateZ': 0}, # default 0
# 	{'rotateZ': 60}, # forward in-btw 1
# 	{'rotateZ': 120}, # forward end 2
# 	{'rotateZ': -50}, # backward 3
# 	{'rotateY': 45}, # right in-btw 4
# 	{'rotateY': 90}, # right end 5
# 	{'rotateY': -40}, # left 6
# ]

ft_upperleg_dict = [
	{'rotateZ': 0}, # default 0
	{'rotateZ': 120}, # forward end 1
	{'rotateZ': -60}, # backward 2
	{'rotateY': 90}, # right end 3
	{'rotateY': -40}, # left 4
]

bk_upperleg_dict = [
	{'rotateZ': 0},
	{'rotateZ': -120},
	{'rotateZ': 60},
	{'rotateY': 90},
	{'rotateY': -40},
]

def create_rbf(jnt, side, desc, values):
	"""
	create rbf weight driver
	"""
	# create rbf weight driver
	part = jnt.split('_')[3]
	region = jnt.split('_')[2]
	# side = _side_from_name(jnt)
	index = _push_index_from_name(jnt)
	
	# for side in ['l', 'r']:
	jnt = f'jnt_{side}_{region}_{part}_{index}'
	rbf_name = f'rbf_{side}_{region}_{desc}_0001'
	rbf_node = cmds.createNode('weightDriver', n=rbf_name)
	rbf_transform = cmds.listRelatives(rbf_node, parent=True)[0]
	cmds.rename(rbf_transform, rbf_name)
	
	# connect driver jnt
	connect_attr(jnt, 'worldMatrix[0]', rbf_node, 'driverList[0].driverInput')
	set_attr(rbf_node, 'type', 1)
	set_attr(rbf_node, 'allowNegativeWeights', 0)
	
	# get matrix
	for i, pose_dict in enumerate(values):
		for attr, value in pose_dict.items():
			print(i, value, attr)
			# local matrix
			set_attr(jnt, attr, value) # set to rotation
			matrix = get_attr(jnt, 'worldMatrix[0]')
			cmds.setAttr( f'{rbf_node}.driverList[0].pose[{i}]poseMatrix', matrix, type='matrix')
			
			# parent matrix
			parent_matrix = get_attr(jnt, 'parentMatrix[0]')
			cmds.setAttr(f'{rbf_node}.driverList[0].pose[{i}].poseParentMatrix', parent_matrix, type='matrix')
			
			# pose mode
			cmds.setAttr(f'{rbf_node}.driverList[0].pose[{i}]poseMode', 1)
			
			# set rotate to 0
			set_attr(jnt, attr, 0)

	return rbf_node

# connect to pose
def connect_pose_loc(loc, side):
	"""
	connect to pose nodes
	"""
	part = loc.split('_')[3]
	region = loc.split('_')[2]
	# side = _side_from_name(loc)
	index = loc.split('_')[-2]
	
	nodes = []
	
	pose_num = len(cmds.ls(f'loc_{side}_{region}_{part}_pushPose_{index}_*', type='transform'))
	
	for val in ['trans', 'rot', 'scale']:
		for i in range(1, pose_num+1):
			print(i)
			node = f"mult_{side}_{region}_{part}_pushPose_{val}_{index}_000{i}"
			nodes.append(node)
	
	# return nodes, int(index)
	return nodes, int(pose_num)

def rbf_setup(jnt, desc, values, loc):
	for side in ['l', 'r']:
		rbf_node = create_rbf(jnt, side, desc, values)
		pose_nodes, index = connect_pose_loc(loc, side)
		
		for node in pose_nodes:
			# find 0001 / 0002 from node name
			suffix = node.split('_')[-1]
			pose_index = int(suffix)
			
			for attr in 'XYZ':
				connect_attr(rbf_node, f'output[{pose_index}]', node, f'input2{attr}')
	
	
rbf_setup('jnt_l_ft_upperlegTwist_0001', 'upperleg', ft_upperleg_dict, 'loc_l_ft_upperleg_pushPose_0001_0001')
# rbf_setup('jnt_l_bk_upperlegTwist_0001', 'upperleg', bk_upperleg_dict)
	
