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


# ----------------------------------------

def create_curve_on_joint(input_jnt, up_vector):
	token = input_jnt.split('_')
	side = _side_from_name(input_jnt)
	region = token[2]
	desc = token[3]
	
	children = cmds.listRelatives(input_jnt, c=True, ad=True, type='joint')[::-1]
	joints = [input_jnt] + children
	
	# get joint position
	positions = [ cmds.xform(jnt, q=True, ws=True, t=True) for jnt in joints]
	rotations = [ cmds.xform(jnt, q=True, ws=True, ro=True) for jnt in joints]
	
	pos_mid_1 = get_percent_position(joints[0], joints[1], percent=0.3)
	pos_mid_2 = get_percent_position(joints[-2], joints[-1], percent=0.7)
	positions.insert(1, pos_mid_1)
	positions.insert(len(positions)-1, pos_mid_2)
	
	# create curve
	curve = cmds.curve(n=f'crv_{side}_{region}_{desc}_0001', p=positions, d=2)
	crv_shape = cmds.listRelatives(curve, c=True, type='shape')[0]
	crv_shape = cmds.rename(crv_shape, f'{curve}Shape')
	
	# create up curve
	up_positions = []
	up_locators = []
	# create temp locators
	for jnt in joints:
		loc = cmds.spaceLocator()[0]
		cmds.matchTransform(loc, jnt)
		cmds.move(0, 1, 0, loc, objectSpace=True, r=True)
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
	for i in range(5):
		loc = cmds.spaceLocator(n=f'loc_{side}_{region}_{desc}_{i+1:04d}')[0]

		# create decompose node
		dec_node = cmds.createNode('decomposeMatrix', n=f'dec_{side}_{region}_{desc}_{i+1:04d}')
		# connect uv pin output
		connect_attr(uv_pin, f'outputMatrix[{i}]', dec_node, 'inputMatrix')

		connect_attr(dec_node, 'outputTranslate', loc, 'translate')
		connect_attr(dec_node, 'outputRotate', loc, 'rotate')

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

	print(positions)
	print(up_positions)

create_curve_on_joint('jnt_l_ft_longTriceps_0001_0001', up_vector='x')