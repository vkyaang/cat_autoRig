import maya.cmds as cmds

class AutoRigHelpers(object):
	
	@classmethod
	def add_attr(cls, node, long_name, attr_type, default_value, min_value=None, max_value=None, keyable=True):
		"""
		Add attribute with optional min/max limits.
		Skips flags if None is passed (to avoid Maya TypeError).
		"""
		args = {
			"longName": long_name,
			"attributeType": attr_type,
			"defaultValue": default_value,
			"keyable": keyable,
		}
		
		# Only include min/max if they exist
		if min_value is not None:
			args["minValue"] = min_value
		if max_value is not None:
			args["maxValue"] = max_value
		
		cmds.addAttr(node, **args)
	
	@classmethod
	def set_attr(cls, node, attr, value, value_type=None):
		if value_type:
			# expect a list that will be unpacked for the command
			cmds.setAttr("{0}.{1}".format(node, attr), *value, type=value_type)
		else:
			cmds.setAttr("{0}.{1}".format(node, attr), value)
	
	@classmethod
	def get_attr(cls, node, attr):
		attr_value = cmds.getAttr("{0}.{1}".format(node, attr))
		
		return attr_value
	
	@classmethod
	def connect_attr(cls, node_a, attr_a, node_b, attr_b, force=False):
		cmds.connectAttr("{0}.{1}".format(node_a, attr_a), "{0}.{1}".format(node_b, attr_b), force=force)
	
	@classmethod
	def lock_hide_attr(cls, node, attrs, lock=True, hide=True, channelBox=False):
		keyable = not hide
		
		for attr in attrs:
			full_name = "{0}.{1}".format(node, attr)
			cmds.setAttr(full_name, lock=lock, keyable=keyable, channelBox=channelBox)
	
	@classmethod
	def create_display_layer(cls, name, members, reference=False):
		display_layer = cmds.createDisplayLayer(name=name, empty=True)
		
		if reference:
			cmds.setAttr("{0}.displayType".format(display_layer), 2)
		
		if members:
			cmds.editDisplayLayerMembers(display_layer, members, noRecurse=True)
		
		return display_layer
	
	@classmethod
	def create_and_assign_lambert_shader(cls, name, shape_node):
		shader = cmds.shadingNode("lambert", name=name, asShader=True)
		shader_sg = cmds.sets(name="{0}SG".format(shader), renderable=True, noSurfaceShader=True, empty=True)
		
		cls.connect_attr(shader, "outColor", shader_sg, "surfaceShader")
		
		cmds.sets([shape_node], e=True, forceElement=shader_sg)
		
		return shader
	
	@classmethod
	def get_shape_from_transform(cls, transform_node):
		return cmds.listRelatives(transform_node, shapes=True, fullPath=True)[0]
	
	@classmethod
	def make_unselectable(cls, transform_node):
		shape_node = cls.get_shape_from_transform(transform_node)
		
		cls.set_attr(shape_node, "overrideEnabled", True)
		cls.set_attr(shape_node, "overrideDisplayType", 2)
	
	@classmethod
	def create_empty_group(cls, name, parent=None):
		group = cmds.createNode('transform', name=name, parent=parent)
		
		return group
	
	@classmethod
	def create_control_hierarchy(cls, ctrl, levels=4):
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
	
	@classmethod
	def get_parent_grp(cls, ctrl):
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
	
	@classmethod
	def mirror_curve_shape(cls, left_ctrl, right_ctrl):
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
