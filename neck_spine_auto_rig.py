import importlib
import maya.cmds as cmds
import curve_library
import auto_rig_helpers

importlib.reload(curve_library)
importlib.reload(auto_rig_helpers)

from auto_rig_helpers import AutoRigHelpers
crv_lib = curve_library.RigCurveLibrary()

# GLOBAl Variable
MOVE_ALL_CTRL = 'ctrl_c_moveAll_0002'
RIG_NODES_LOCAL_GRP = 'rigNodesLocal'
CONTROLS_GRP = 'controls'
JOINTS_GRP = 'joints'
LOC_NECK_END = 'loc_c_neck_end_0001'
LOC_COG = 'loc_c_cog_0001'

class SpineNeckAutoRig(object):
	
	def __init__(self):
		self.chest_buffer_grp = None
		self.pelvis_ctrl = None
		self.cog_jnt = None
		self.belly_joints = None
		
		self.cog_off_ctrl = None
		self.neck_switch_ctrl = None
		self.neck_tangent_ctrl = None
		self.neck_lower_tangent_ctrl = None
		self.neck_mid_jnt = None
		self.neck_ik_jnt = None
		self.neck_lower_jnt = None
		self.neck_ik_ctrl = None
		self.neck_data_grp = None
		self.neck_non_str_joints = None
		self.neck_str_joints = None
		self.neck_joints = []
		self.neck_joints_grp = None
		self.spine_switch_ctrl = None
		self.spine_data_grp = None
		self.chest_ik_ctrl = None
		self.pelvis_ik_ctrl = None
		self.non_str_joints = None
		self.str_joints = None
		self.spine_mid_jnt = None
		
		self.chest_ik_jnt = None
		self.pelvis_ik_jnt = None
		
		self.spine_bw_joints_grp = None
		self.spine_fw_joints_grp = None
		self.spine_joints_grp = None
		
		self.spine_bw_curve = None
		
		self.non_str_bw_joints = None
		self.str_bw_joints = None
		self.non_str_fw_joints = None
		self.str_fw_joints = None
		
		self.spine_fw_curve = "curve1"
		self.spine_joints = []
		
		self.str_fw_root_jnt = None
		self.str_bw_root_jnt = None
		

		self.neck_curve = "curve2"
		self.tail_curve = 'curve3'
	
	def joint_on_curve(self, cv, name="spine", jntNum=7, span=7, store=True):
		"""
		Create a chain of joints evenly distributed along a curve.
		If `store=True`, automatically saves to self.<name>_joints (e.g. self.spine_joints, self.neck_joints).
		Otherwise returns the joint list.

		Args:
			cv (str): curve name.
			name (str): base name for the joint chain (e.g. "spine", "neck", "tail").
			jntNum (int): number of joints to create.
			span (int): curve rebuild span.
			store (bool): if True, saves to self.<name>_joints automatically.

		Returns:
			list[str]: ordered list of created joint names.
		"""
		# Rebuild curve for even parameterization
		cmds.rebuildCurve(cv, ch=1, rpo=1, rt=0, end=1, kr=0,
						  kcp=0, kep=1, kt=0, s=span, d=3)
		
		joint_chain = []
		for j in range(jntNum + 1):
			idx = str(j + 1).zfill(4)
			jnt_name = f"jnt_c_{name}_{idx}"
			
			# Get position along curve
			param = float(j) / jntNum
			pos = cmds.pointOnCurve(cv, pr=param, p=True)
			joint = cmds.joint(p=pos, rad=1, n=jnt_name)
			joint_chain.append(joint)
		
		# Orient chain properly
		ikh_name = f"ikHnd_c_{name}_0001"
		ikh = cmds.ikHandle(sj=joint_chain[0], ee=joint_chain[-1],
							c=cv, ccv=False, sol='ikSplineSolver',
							pcv=0, n=ikh_name)[0]
		cmds.delete(ikh)
		cmds.makeIdentity(joint_chain, apply=True, t=1, r=1, s=1, n=0, pn=1)
		cmds.joint(joint_chain[0], e=True, oj="xyz", secondaryAxisOrient="yup", ch=True, zso=True)
		
		# Store automatically if desired
		if store:
			setattr(self, f"{name}_joints", joint_chain)
		
		return joint_chain
	
	def duplicate_and_rename_chain(self, root_joint, base):
		"""Duplicate a joint chain from root_joint and rename in strict parent→child order.
		Example: base='jnt_c_spine_str_fw' → jnt_c_spine_str_fw_0001, _0002, _0003..."""
		dup_root = cmds.duplicate(root_joint, rc=True, n=f"{base}_0001")[0]
		
		ordered = []
		index = 1
		current = dup_root
		
		while True:
			new_name = f"{base}_{index:04d}"
			current = cmds.rename(current, new_name)
			ordered.append(current)
			
			children = cmds.listRelatives(current, c=True, type="joint") or []
			if not children:
				break
			current = children[0]
			index += 1
		
		return ordered
	
	def create_curve(self):
		"""Safely create or reuse curves for spine and neck."""
		if not cmds.objExists("crv_c_spineFw_0001"):
			self.spine_fw_curve = cmds.rename(self.spine_fw_curve, "crv_c_spineFw_0001")
		else:
			self.spine_fw_curve = "crv_c_spineFw_0001"
		
		if not cmds.objExists("crv_c_spineBw_0001"):
			self.spine_bw_curve = cmds.duplicate(self.spine_fw_curve, rc=True, name="crv_c_spineBw_0001")[0]
			cmds.reverseCurve(self.spine_bw_curve, ch=False, rpo=True)
		else:
			self.spine_bw_curve = "crv_c_spineBw_0001"
		
		# Spine data group
		if not cmds.objExists("grp_spineData_0001"):
			self.spine_data_grp = AutoRigHelpers.create_empty_group("grp_spineData_0001", parent="rigNodesLocal")
			cmds.parent(self.spine_fw_curve, self.spine_data_grp)
			cmds.parent(self.spine_bw_curve, self.spine_data_grp)
		else:
			self.spine_data_grp = "grp_spineData_0001"
		
		# Neck
		if not cmds.objExists("crv_c_neck_0001"):
			self.neck_curve = cmds.rename(self.neck_curve, "crv_c_neck_0001")
			self.neck_data_grp = AutoRigHelpers.create_empty_group("grp_neckData_0001", parent="rigNodesLocal")
			cmds.parent(self.neck_curve, self.neck_data_grp)
		else:
			self.neck_curve = "crv_c_neck_0001"
		
		return self.spine_fw_curve, self.spine_bw_curve, self.neck_curve
	
	def create_spine_joints(self):
		"""Create and organize spine joint chains (forward/backward, stretch/non-stretch)."""
		# 1️⃣ Create the base spine joints along the curve
		
		self.joint_on_curve(self.spine_fw_curve, jntNum=6)
		
		# 2️⃣ Create main groups
		self.spine_joints_grp = AutoRigHelpers.create_empty_group("grp_spineJnts_0001", parent='joints')
		self.spine_fw_joints_grp = AutoRigHelpers.create_empty_group("grp_spineFw_jnts_0001", parent=self.spine_joints_grp)
		self.spine_bw_joints_grp = AutoRigHelpers.create_empty_group("grp_spineBw_jnts_0001", parent=self.spine_joints_grp)
		
		# 3️⃣ Clear end joint orientation
		end_joint = self.spine_joints[-1]
		for axis in ("X", "Y", "Z"):
			cmds.setAttr(f"{end_joint}.jointOrient{axis}", 0)
		
		# 4️⃣ Parent the original chain under spine_joints_grp
		root_joint = self.spine_joints[0]
		cmds.parent(root_joint, self.spine_joints_grp)
		
		# 5️⃣ Duplicate forward chains
		self.str_fw_joints = self.duplicate_and_rename_chain(root_joint, "jnt_c_spine_str_fw")
		self.non_str_fw_joints = self.duplicate_and_rename_chain(root_joint, "jnt_c_spine_nonStr_fw")
		
		cmds.parent(self.str_fw_joints[0], self.spine_fw_joints_grp)
		cmds.parent(self.non_str_fw_joints[0], self.spine_fw_joints_grp)
		
		# 6️⃣ Duplicate backward chains
		self.str_bw_joints = self.duplicate_and_rename_chain(root_joint, "jnt_c_spine_str_bw")
		self.non_str_bw_joints = self.duplicate_and_rename_chain(root_joint, "jnt_c_spine_nonStr_bw")
		
		# 6️⃣ Duplicate output str and non-str chains
		self.str_joints = self.duplicate_and_rename_chain(root_joint, "jnt_c_spine_str")
		self.non_str_joints = self.duplicate_and_rename_chain(root_joint, "jnt_c_spine_nonStr")
		
		self.str_bw_joints = self.reverse_joint_chain(self.str_bw_joints)
		self.non_str_bw_joints = self.reverse_joint_chain(self.non_str_bw_joints)
		
		cmds.parent(self.str_bw_joints[0], self.spine_bw_joints_grp)
		cmds.parent(self.non_str_bw_joints[0], self.spine_bw_joints_grp)
		
		# toggle visibility
		AutoRigHelpers.set_attr(self.str_joints[0], 'visibility', False)
		AutoRigHelpers.set_attr(self.non_str_joints[0], 'visibility', False)
		AutoRigHelpers.set_attr(self.spine_bw_joints_grp, 'visibility', False)
		AutoRigHelpers.set_attr(self.spine_fw_joints_grp, 'visibility', False)
		
		self.create_curve()
	
	def reverse_joint_chain(self, joint_chain):
		"""
		Reverse-parent a joint chain so the last joint becomes the new root.
		Example:
			Before: jnt_0001 -> jnt_0002 -> ... -> jnt_0008
			After:  jnt_0008 -> jnt_0007 -> ... -> jnt_0001
		"""
		# Unparent all joints first to avoid DAG conflicts
		for jnt in joint_chain:
			try:
				cmds.parent(jnt, world=True)
			except:
				pass

		# Rebuild hierarchy in reverse (child → parent)
		for i in range(len(joint_chain) - 1, 0, -1):
			cmds.parent(joint_chain[i - 1], joint_chain[i])

		# The new root will be the last joint in the original list
		new_root = joint_chain[-1]
		# cmds.parent(new_root, world=True)

		# Return the reversed order (new_root first)
		reversed_chain = list(reversed(joint_chain))
		return reversed_chain

	def create_spine_setup(self):
		
		# create spline ik
		str_fw_root_jnt = self.str_fw_joints[0]
		str_fw_end_jnt = self.str_fw_joints[-1]
		
		str_bw_root_jnt = self.str_bw_joints[0]
		str_bw_end_jnt = self.str_bw_joints[-1]
		
		fw_spine_ik = cmds.ikHandle(sj=str_fw_root_jnt,
									ee=str_fw_end_jnt,
									sol='ikSplineSolver',
									curve=self.spine_fw_curve,
									ccv=False,
									pcv=False,
									name="ikHnd_c_spine_strFw_0001")[0]
		
		bw_spine_ik = cmds.ikHandle(sj=str_bw_root_jnt,
									ee=str_bw_end_jnt,
									sol='ikSplineSolver',
									curve=self.spine_bw_curve,
									ccv=False,
									pcv=False,
									name="ikHnd_c_spine_strBw_0001")[0]
		
		cmds.parent(fw_spine_ik, self.spine_fw_joints_grp)
		cmds.parent(bw_spine_ik, self.spine_bw_joints_grp)
		AutoRigHelpers.set_attr(fw_spine_ik, "visibility", False)
		AutoRigHelpers.set_attr(bw_spine_ik, "visibility", False)
		
		# create driver joints
		pelvis_ik_jnt = cmds.createNode('joint', name='jnt_c_pelvis_ik_0001')
		chest_ik_jnt = cmds.createNode('joint', name='jnt_c_chest_ik_0001')
		spine_mid_jnt = cmds.createNode('joint', name='jnt_c_spineMid_ik_0001')
		

		self.pelvis_ik_jnt = pelvis_ik_jnt
		self.chest_ik_jnt = chest_ik_jnt
		self.spine_mid_jnt = spine_mid_jnt
		
		cmds.matchTransform(pelvis_ik_jnt, str_fw_root_jnt, pos=True, rot=False)
		cmds.matchTransform(chest_ik_jnt, str_fw_end_jnt, pos=True, rot=False)
		
		cons = cmds.pointConstraint(chest_ik_jnt, pelvis_ik_jnt, spine_mid_jnt, mo=False)[0]
		
		spine_mid_jnt_ty = AutoRigHelpers.get_attr(spine_mid_jnt, 'translateY')
		AutoRigHelpers.set_attr(spine_mid_jnt, 'translateY', spine_mid_jnt_ty+1.0)
		
		cmds.delete(cons)
		
		# bind skin
		cmds.skinCluster(
			pelvis_ik_jnt,
			chest_ik_jnt,
			spine_mid_jnt,
			self.spine_fw_curve,
			toSelectedBones=True,
			bindMethod=0,
			skinMethod=0,
			normalizeWeights=1
		)
		
		cmds.skinCluster(
			pelvis_ik_jnt,
			chest_ik_jnt,
			spine_mid_jnt,
			self.spine_bw_curve,
			toSelectedBones=True,
			bindMethod=0,
			skinMethod=0,
			normalizeWeights=1
		)
		
		# constraint non str
		self.constraint_non_str_jnts(self.str_fw_joints, self.non_str_fw_joints)
		self.constraint_non_str_jnts(self.str_bw_joints, self.non_str_bw_joints)
		
		self.create_spine_controllers()
		
		# create twist
		AutoRigHelpers.set_attr(fw_spine_ik, 'dTwistControlEnable', True)
		AutoRigHelpers.set_attr(fw_spine_ik, 'dWorldUpType', 4)
		AutoRigHelpers.set_attr(fw_spine_ik, 'dTwistControlEnable', True)
		AutoRigHelpers.set_attr(fw_spine_ik, 'dForwardAxis', 0)
		
		AutoRigHelpers.set_attr(bw_spine_ik, 'dTwistControlEnable', True)
		AutoRigHelpers.set_attr(bw_spine_ik, 'dWorldUpType', 4)
		AutoRigHelpers.set_attr(bw_spine_ik, 'dTwistControlEnable', True)
		AutoRigHelpers.set_attr(bw_spine_ik, 'dForwardAxis', 1)
		
		# Assign world up objects
		# fw str
		AutoRigHelpers.connect_attr(self.pelvis_ik_ctrl, 'worldMatrix[0]', fw_spine_ik, 'dWorldUpMatrix', True)
		AutoRigHelpers.connect_attr(self.chest_ik_ctrl, 'worldMatrix[0]', fw_spine_ik, 'dWorldUpMatrixEnd', True)
		# bw str
		AutoRigHelpers.connect_attr(self.pelvis_ik_ctrl, 'worldMatrix[0]', bw_spine_ik, 'dWorldUpMatrixEnd', True)
		AutoRigHelpers.connect_attr(self.chest_ik_ctrl, 'worldMatrix[0]', bw_spine_ik, 'dWorldUpMatrix', True)
	
	def constraint_non_str_jnts(self, str_chain, non_str_chain):
		"""
		Constrain a non-stretch joint chain to follow a stretch joint chain.
		- Root: parentConstraint (translation + rotation)
		- Others: orientConstraint (rotation only)
		"""
		if not str_chain or not non_str_chain:
			cmds.warning("Empty joint list passed to constraint_non_str_jnt.")
			return
		
		# ensure equal length
		count = min(len(str_chain), len(non_str_chain))
		
		cmds.parentConstraint(str_chain[0], non_str_chain[0], mo=False)
		
		for i in range(1, count):
			str_jnt = str_chain[i]
			non_str_jnt = non_str_chain[i]
			cmds.orientConstraint(str_jnt, non_str_jnt, mo=False)
	
	
	def create_spine_controllers(self):
		# create groups
		spine_ctrl_grp = cmds.createNode('transform', name='grp_spineCtrls', parent=self.cog_off_ctrl)
		
		# create controls
		pelvis_ik_ctrl = crv_lib.create_cube_curve("ctrl_c_pelvis_ik_0001")
		chest_ik_ctrl = crv_lib.create_cube_curve("ctrl_c_chest_ik_0001")
		spine_mid_ctrl = crv_lib.create_diamond("ctrl_c_spineMid_ik_0001")
		spine_switch_ctrl = crv_lib.create_lollipop_ctrl("ctrl_c_spineSwitch_0001")
		
		# match transform
		cmds.matchTransform(pelvis_ik_ctrl, self.pelvis_ik_jnt)
		cmds.matchTransform(chest_ik_ctrl, self.chest_ik_jnt)
		cmds.matchTransform(spine_mid_ctrl, self.spine_mid_jnt)
		cmds.matchTransform(spine_switch_ctrl, pelvis_ik_ctrl)
		
		AutoRigHelpers.create_control_hierarchy(pelvis_ik_ctrl)
		AutoRigHelpers.create_control_hierarchy(chest_ik_ctrl)
		AutoRigHelpers.create_control_hierarchy(spine_mid_ctrl)
		AutoRigHelpers.create_control_hierarchy(spine_switch_ctrl, 1)
		
		# lock and hide attr
		AutoRigHelpers.lock_hide_attr(pelvis_ik_ctrl, ['sx', 'sy', 'sz', 'v'])
		AutoRigHelpers.lock_hide_attr(chest_ik_ctrl, ['sx', 'sy', 'sz', 'v'])
		AutoRigHelpers.lock_hide_attr(spine_mid_ctrl, ['sx', 'sy', 'sz', 'v'])
		AutoRigHelpers.lock_hide_attr(spine_switch_ctrl, ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v'])
		
		# set switch attr
		AutoRigHelpers.add_attr(spine_switch_ctrl, 'stretch', 'float', 0, 0, 1)
		AutoRigHelpers.add_attr(spine_switch_ctrl, 'stretch_anchor', 'float', 0, 0, 1)
		
		# parent driver joints
		cmds.parent(self.pelvis_ik_jnt, pelvis_ik_ctrl)
		cmds.parent(self.chest_ik_jnt, chest_ik_ctrl)
		cmds.parent(self.spine_mid_jnt, spine_mid_ctrl)
		
		# Get zero and offset
		spine_mid_zero, spine_mid_offset, *_ = AutoRigHelpers.get_parent_grp(spine_mid_ctrl)
		pelvis_ik_zero, *_ = AutoRigHelpers.get_parent_grp(pelvis_ik_ctrl)
		chest_ik_zero, *_ = AutoRigHelpers.get_parent_grp(chest_ik_ctrl)
		spine_switch_zero = AutoRigHelpers.get_parent_grp(spine_switch_ctrl)
		
		# parent zero group
		cmds.parent(pelvis_ik_zero, spine_ctrl_grp)
		cmds.parent(chest_ik_zero, spine_ctrl_grp)
		cmds.parent(spine_mid_zero, spine_ctrl_grp)
		cmds.parent(spine_switch_zero, pelvis_ik_ctrl)
		
		cmds.pointConstraint(self.pelvis_ik_jnt, self.chest_ik_jnt, spine_mid_offset, mo=True)

		# create up group
		spine_mid_up = cmds.createNode('transform', name=spine_mid_zero.replace('zero', 'up'), p=spine_mid_zero)
		AutoRigHelpers.set_attr(spine_mid_up, 'translateX', 10)
		aim_cons = cmds.aimConstraint(self.chest_ik_jnt,
									  spine_mid_offset,
									  mo=True,
									  worldUpType='object',
									  aim=(0,0,1),
									  u=(0,0,1),
									  wuo=spine_mid_up)
		
		# create tangent ctrls
		pelvis_tangent_ctrl = crv_lib.create_arrow_curve('ctrl_pelvis_tangent_0001')
		chest_tangent_ctrl = crv_lib.create_arrow_curve('ctrl_chest_tangent_0001')
		AutoRigHelpers.add_attr(pelvis_tangent_ctrl, 'tangent_length', 'float', 1)
		AutoRigHelpers.add_attr(chest_tangent_ctrl, 'tangent_length', 'float', 1)
		AutoRigHelpers.lock_hide_attr(pelvis_tangent_ctrl, ['tx','ty','tz','sx','sy','sz','v'])
		AutoRigHelpers.lock_hide_attr(chest_tangent_ctrl, ['tx', 'ty', 'tz', 'sx', 'sy', 'sz','v'])
		
		cmds.matchTransform(pelvis_tangent_ctrl, pelvis_ik_ctrl)
		cmds.matchTransform(chest_tangent_ctrl, chest_ik_ctrl)
		AutoRigHelpers.create_control_hierarchy(pelvis_tangent_ctrl, 2)
		AutoRigHelpers.create_control_hierarchy(chest_tangent_ctrl, 2)
		pelvis_tangent_zero = AutoRigHelpers.get_parent_grp(pelvis_tangent_ctrl)[2]
		chest_tangent_zero = AutoRigHelpers.get_parent_grp(chest_tangent_ctrl)[2]
		
		cmds.parent(pelvis_tangent_zero, spine_ctrl_grp)
		cmds.parent(chest_tangent_zero, spine_ctrl_grp)

		cmds.parentConstraint(pelvis_ik_ctrl, AutoRigHelpers.get_parent_grp(pelvis_tangent_ctrl)[3], mo=False)
		cmds.parentConstraint(chest_ik_ctrl, AutoRigHelpers.get_parent_grp(chest_tangent_ctrl)[3], mo=False)
		
		AutoRigHelpers.connect_attr(pelvis_tangent_ctrl, "rotate", self.pelvis_ik_jnt, 'rotate')
		AutoRigHelpers.connect_attr(pelvis_tangent_ctrl, "tangent_length", self.pelvis_ik_jnt, 'sz')
		AutoRigHelpers.connect_attr(chest_tangent_ctrl, "rotate", self.chest_ik_jnt, 'rotate')
		AutoRigHelpers.connect_attr(chest_tangent_ctrl, "tangent_length", self.chest_ik_jnt, 'sz')
		
		# create group under chest
		chest_buffer_grp = cmds.createNode('transform', n=f'grp_c_chestIk_buffer_0001', p=chest_ik_ctrl)
		cmds.pointConstraint(self.spine_joints[-1], chest_buffer_grp, mo=True)
		
		self.pelvis_ik_ctrl = pelvis_ik_ctrl
		self.chest_ik_ctrl = chest_ik_ctrl
		self.spine_switch_ctrl = spine_switch_ctrl
		self.chest_buffer_grp = chest_buffer_grp
	
	@classmethod
	def setup_stretch(cls, name, detail, str_chain, crv, last_jnt=True):
		crv_info_name = f'crvInfo_c_{name}_0001'
		div_norm_name = 'div_c_scaleFixFactor_0001'
		mdl_norm_name = 'mdl_c_scaleFixFactor_0001'
		mdl_name = f'mdl_c_{name}_{detail}_0001'
		
		# check or create scale fix locator
		if cmds.objExists('loc_c_scaleFixFactor_0001'):
			loc_fix_factor = 'loc_c_scaleFixFactor_0001'
		else:
			loc_fix_factor = cmds.spaceLocator(name='loc_c_scaleFixFactor_0001')[0]
			cmds.parent(loc_fix_factor, RIG_NODES_LOCAL_GRP)
			cmds.scaleConstraint(MOVE_ALL_CTRL, loc_fix_factor)
		
		# create nodes
		crv_info = cmds.createNode('curveInfo', name=crv_info_name)
		str_fw_crv_shape = cmds.listRelatives(crv, shapes=True)[0]
		div_fix_factor_norm = cmds.createNode('multiplyDivide', name=div_norm_name)
		mult_fix_factor_norm = cmds.createNode('multiplyDivide', name=mdl_norm_name)
		mult_str = cmds.createNode('multiplyDivide', name=mdl_name)
		
		# set operations
		AutoRigHelpers.set_attr(div_fix_factor_norm, 'operation', 2)  # divide
		AutoRigHelpers.set_attr(mult_str, 'operation', 2)  # divide
		
		# connect attributes
		AutoRigHelpers.connect_attr(str_fw_crv_shape, 'worldSpace[0]', crv_info, 'inputCurve')
		arc_length = AutoRigHelpers.get_attr(crv_info, 'arcLength')
		
		AutoRigHelpers.connect_attr(loc_fix_factor, 'scale', div_fix_factor_norm, 'input1')
		AutoRigHelpers.set_attr(div_fix_factor_norm, 'input2X', 1)
		AutoRigHelpers.connect_attr(div_fix_factor_norm, 'output', mult_fix_factor_norm, 'input2')
		AutoRigHelpers.set_attr(mult_fix_factor_norm, 'input1X', arc_length)
		AutoRigHelpers.connect_attr(mult_fix_factor_norm, 'outputX', mult_str, 'input2X')
		AutoRigHelpers.connect_attr(crv_info, 'arcLength', mult_str, 'input1X')
		
		if last_jnt == True:
			# connect to joints (exclude last)
			for jnt in str_chain[:-1]:
				AutoRigHelpers.connect_attr(mult_str, 'outputX', jnt, 'scaleX')
		else:
			for jnt in str_chain[:-2]:
				AutoRigHelpers.connect_attr(mult_str, 'outputX', jnt, 'scaleX')
		
	
	@classmethod
	def blend_fw_bw(cls, ctrl, name, fw_chain, bw_chain, output_chain):
		bw_chain_rev = list(reversed(bw_chain))
		cons_nodes = []
		
		for fw_jnt, bw_jnt, out_jnt in zip(fw_chain, bw_chain_rev, output_chain):
			cons = cmds.parentConstraint(fw_jnt, bw_jnt, out_jnt, mo=False)[0]
			cons_nodes.append(cons)
			AutoRigHelpers.set_attr(cons, 'interpType', 2)
		
		# create reverse node
		rvs_name = 'rvs_c_{0}_strAnchor_0001'.format(name)
		if cmds.objExists(rvs_name):
			rvs_fw_bw = rvs_name
		else:
			rvs_fw_bw = cmds.createNode('reverse', name=rvs_name)
			AutoRigHelpers.connect_attr(ctrl, 'stretch_anchor', rvs_fw_bw, 'inputX')
			
		for fw_jnt, bw_jnt, cons in zip(fw_chain, bw_chain_rev, cons_nodes):
			AutoRigHelpers.connect_attr(ctrl, 'stretch_anchor', cons, f'{bw_jnt}W1')
			AutoRigHelpers.connect_attr(rvs_fw_bw, 'outputX', cons, f'{fw_jnt}W0')
			
	@classmethod
	def blend_str_nonStr(cls, ctrl, name, str_chain, non_str_chain, output_chain):
		cons_nodes = []
		
		for str_jnt, non_str_jnt, out_jnt in zip(str_chain, non_str_chain, output_chain):
			cons = cmds.parentConstraint(str_jnt, non_str_jnt, out_jnt, mo=False)[0]
			cons_nodes.append(cons)
			AutoRigHelpers.set_attr(cons, 'interpType', 2)
			
		# create reverse node
		rvs_name = 'rvs_c_{0}_stretch_0001'.format(name)
		if cmds.objExists(rvs_name):
			rvs_str = rvs_name
		else:
			rvs_str = cmds.createNode('reverse', name=rvs_name)
			AutoRigHelpers.connect_attr(ctrl, 'stretch', rvs_str, 'inputX')
		
		for str_jnt, non_str_jnt, cons in zip(str_chain, non_str_chain, cons_nodes):
			AutoRigHelpers.connect_attr(ctrl, 'stretch', cons, f'{str_jnt}W0')
			AutoRigHelpers.connect_attr(rvs_str, 'outputX', cons, f'{non_str_jnt}W1')
			
		print(f"Stretch setup complete for str")
	
	def create_neck_joints(self):
		"""Create and organize neck joint chains (forward/backward, stretch/non-stretch)."""
		# 1 Create the base spine joints along the curve
		
		self.joint_on_curve(self.neck_curve, 'neck', 5)
		
		# Create main groups
		self.neck_joints_grp = AutoRigHelpers.create_empty_group("grp_neckJnts_0001", parent='joints')
		
		# create end joint
		neck_end_jnt = cmds.createNode('joint', name='jnt_c_neck_0008')
		self.neck_joints.append(neck_end_jnt)
		cmds.matchTransform(neck_end_jnt, LOC_NECK_END)
		cmds.parent(neck_end_jnt, self.neck_joints[-2])
		cmds.joint(self.neck_joints[-2], e=True, oj='xyz', secondaryAxisOrient='yup', ch=True, zso=True)
		
		# 3 Clear end joint orientation
		end_joint = self.neck_joints[-1]
		for axis in ("X", "Y", "Z"):
			cmds.setAttr(f"{end_joint}.jointOrient{axis}", 0)
		
		# 4 Parent the original chain under spine_joints_grp
		root_joint = self.neck_joints[0]
		cmds.parent(root_joint, self.neck_joints_grp)
		
		# Duplicate output str and non-str chains
		self.neck_str_joints = self.duplicate_and_rename_chain(root_joint, "jnt_c_neck_str")
		self.neck_non_str_joints = self.duplicate_and_rename_chain(root_joint, "jnt_c_neck_nonStr")
		
		# toggle visibility
		AutoRigHelpers.set_attr(self.neck_str_joints[0], 'visibility', False)
		AutoRigHelpers.set_attr(self.neck_non_str_joints[0], 'visibility', False)
	
	def create_neck_setup(self):
		
		# create spline ik
		str_root_jnt = self.neck_str_joints[0]
		str_end_jnt = self.neck_str_joints[-2]
		
		neck_str_ikHnd = cmds.ikHandle(sj=str_root_jnt,
									ee=str_end_jnt,
									sol='ikSplineSolver',
									curve=self.neck_curve,
									ccv=False,
									pcv=False,
									name="ikHnd_c_neck_strFw_0001")[0]
		
		cmds.parent(neck_str_ikHnd, self.neck_joints_grp)
		AutoRigHelpers.set_attr(neck_str_ikHnd, "visibility", False)
		
		# create driver joints
		neck_lower_jnt = cmds.createNode('joint', name='jnt_c_neck_lower_ik_0001')
		neck_ik_jnt = cmds.createNode('joint', name='jnt_c_neck_ik_0001')
		neck_mid_jnt = cmds.createNode('joint', name='jnt_c_neckMid_ik_0001')
		
		self.neck_lower_jnt = neck_lower_jnt
		self.neck_ik_jnt = neck_ik_jnt
		self.neck_mid_jnt = neck_mid_jnt
		
		cmds.matchTransform(neck_lower_jnt, self.chest_ik_ctrl, pos=True, rot=False)
		cmds.matchTransform(neck_ik_jnt, str_end_jnt, pos=True, rot=False)
		
		cons = cmds.pointConstraint(neck_lower_jnt, neck_ik_jnt, neck_mid_jnt, mo=False)[0]
		
		neck_mid_jnt_tz = AutoRigHelpers.get_attr(neck_mid_jnt, 'translateZ')
		AutoRigHelpers.set_attr(neck_mid_jnt, 'translateZ', neck_mid_jnt_tz + 1.4)
		
		cmds.delete(cons)
		
		# bind skin
		cmds.skinCluster(
			neck_lower_jnt,
			neck_ik_jnt,
			neck_mid_jnt,
			self.neck_curve,
			toSelectedBones=True,
			bindMethod=0,
			skinMethod=0,
			normalizeWeights=1
		)
		
		# constraint non str
		self.constraint_non_str_jnts(self.neck_str_joints, self.neck_non_str_joints)
		
		self.create_neck_controllers()

		# create twist
		AutoRigHelpers.set_attr(neck_str_ikHnd, 'dTwistControlEnable', True)
		AutoRigHelpers.set_attr(neck_str_ikHnd, 'dWorldUpType', 4)

		# Assign world up objects
		AutoRigHelpers.connect_attr(self.chest_ik_ctrl, 'worldMatrix[0]', neck_str_ikHnd, 'dWorldUpMatrix', True)
		AutoRigHelpers.connect_attr(self.neck_ik_ctrl, 'worldMatrix[0]', neck_str_ikHnd, 'dWorldUpMatrixEnd', True)
	
	def create_neck_controllers(self):
		# create groups
		neck_ctrl_grp = cmds.createNode('transform', name='grp_neckCtrls', parent=self.cog_off_ctrl)
		cmds.parentConstraint(self.chest_ik_ctrl, neck_ctrl_grp, mo=True)
		
		# create controls
		neck_ik_ctrl = crv_lib.create_cube_curve("ctrl_c_neck_ik_0001")
		neck_mid_ctrl = crv_lib.create_diamond("ctrl_c_neckMid_ik_0001")
		neck_switch_ctrl = crv_lib.create_lollipop_ctrl("ctrl_c_neckSwitch_0001")
		
		# match transform
		cmds.matchTransform(neck_ik_ctrl, self.neck_ik_jnt)
		cmds.matchTransform(neck_mid_ctrl, self.neck_mid_jnt)
		cmds.matchTransform(neck_switch_ctrl, self.chest_ik_ctrl)
		
		AutoRigHelpers.create_control_hierarchy(self.neck_lower_jnt, 2)
		_, _, neck_lower_jnt_zero, neck_lower_jnt_offset = AutoRigHelpers.get_parent_grp(self.neck_lower_jnt)
		AutoRigHelpers.create_control_hierarchy(neck_ik_ctrl)
		AutoRigHelpers.create_control_hierarchy(neck_mid_ctrl)
		AutoRigHelpers.create_control_hierarchy(neck_switch_ctrl, 1)
		
		# lock and hide attr
		AutoRigHelpers.lock_hide_attr(neck_ik_ctrl, ['sx', 'sy', 'sz', 'v'])
		AutoRigHelpers.lock_hide_attr(neck_mid_ctrl, ['sx', 'sy', 'sz', 'v'])
		AutoRigHelpers.lock_hide_attr(neck_switch_ctrl, ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v'])
		
		# set switch attr
		AutoRigHelpers.add_attr(neck_switch_ctrl, 'stretch', 'float', 0, 0, 1)
		
		# # parent driver joints
		# cmds.parent(self.neck_lower_jnt, neck_lower_jnt_offset)
		cmds.parent(self.neck_ik_jnt, neck_ik_ctrl)
		cmds.parent(self.neck_mid_jnt, neck_mid_ctrl)
		
		# Get zero and offset
		neck_mid_zero, neck_mid_offset, *_ = AutoRigHelpers.get_parent_grp(neck_mid_ctrl)
		neck_ik_zero, *_ = AutoRigHelpers.get_parent_grp(neck_ik_ctrl)
		neck_switch_zero = AutoRigHelpers.get_parent_grp(neck_switch_ctrl)
		
		# parent zero group
		cmds.parent(neck_lower_jnt_zero, neck_ctrl_grp)
		cmds.parent(neck_ik_zero, neck_ctrl_grp)
		cmds.parent(neck_mid_zero, neck_ctrl_grp)
		cmds.parent(neck_switch_zero, neck_ctrl_grp)
		
		cmds.pointConstraint(self.chest_ik_jnt, self.neck_ik_jnt, neck_mid_offset, mo=True)
		cmds.pointConstraint(self.spine_joints[-1], neck_lower_jnt_offset, mo=True)
		
		# create up group
		neck_mid_up = cmds.createNode('transform', name=neck_mid_zero.replace('zero', 'up'), p=neck_mid_zero)
		AutoRigHelpers.set_attr(neck_mid_up, 'translateX', 10)
		aim_cons = cmds.aimConstraint(self.neck_ik_jnt,
									  neck_mid_offset,
									  mo=True,
									  worldUpType='object',
									  aim=(0, 0, 1),
									  u=(0, 0, 1),
									  wuo=neck_mid_up)
		
		# create tangent ctrls
		neck_lower_tangent_ctrl = crv_lib.create_arrow_curve('ctrl_neck_tangent_0001')
		neck_tangent_ctrl = crv_lib.create_arrow_curve('ctrl_neck_tangent_0002')
		AutoRigHelpers.add_attr(neck_lower_tangent_ctrl, 'tangent_length', 'float', 1)
		AutoRigHelpers.add_attr(neck_tangent_ctrl, 'tangent_length', 'float', 1)
		AutoRigHelpers.lock_hide_attr(neck_lower_tangent_ctrl, ['tx', 'ty', 'tz', 'sx', 'sy', 'sz', 'v'])
		AutoRigHelpers.lock_hide_attr(neck_tangent_ctrl, ['tx', 'ty', 'tz', 'sx', 'sy', 'sz', 'v'])
		
		cmds.matchTransform(neck_lower_tangent_ctrl, self.chest_ik_ctrl)
		cmds.matchTransform(neck_tangent_ctrl, neck_ik_ctrl)
		AutoRigHelpers.create_control_hierarchy(neck_lower_tangent_ctrl, 2)
		AutoRigHelpers.create_control_hierarchy(neck_tangent_ctrl, 2)
		neck_lower_tangent_zero = AutoRigHelpers.get_parent_grp(neck_lower_tangent_ctrl)[2]
		neck_tangent_zero = AutoRigHelpers.get_parent_grp(neck_tangent_ctrl)[2]
		cmds.parent(neck_lower_tangent_zero, neck_ctrl_grp)
		cmds.parent(neck_tangent_zero, neck_ctrl_grp)
		
		cmds.parentConstraint(self.chest_ik_ctrl, AutoRigHelpers.get_parent_grp(neck_lower_tangent_ctrl)[3], mo=False)
		cmds.parentConstraint(neck_ik_ctrl, AutoRigHelpers.get_parent_grp(neck_tangent_ctrl)[3], mo=False)
		
		AutoRigHelpers.connect_attr(neck_lower_tangent_ctrl, "rotate", self.neck_lower_jnt, 'rotate')
		AutoRigHelpers.connect_attr(neck_lower_tangent_ctrl, "tangent_length", self.neck_lower_jnt, 'sz')
		AutoRigHelpers.connect_attr(neck_tangent_ctrl, "rotate", self.neck_ik_jnt, 'rotate')
		AutoRigHelpers.connect_attr(neck_tangent_ctrl, "tangent_length", self.neck_ik_jnt, 'sz')
		
		# add attr to chest ctrl
		AutoRigHelpers.add_attr(neck_ik_ctrl, 'local_world_rotate', 'float', 0, 0, 1)
		AutoRigHelpers.add_attr(neck_ik_ctrl, 'local_world_translate', 'float', 0, 0, 1)
		
		self.neck_lower_tangent_ctrl = neck_lower_tangent_ctrl
		self.neck_ik_ctrl = neck_ik_ctrl
		self.neck_tangent_ctrl = neck_tangent_ctrl
		self.neck_switch_ctrl = neck_switch_ctrl
	
	def create_cog(self):
		cog_jnt = cmds.createNode('joint', name='jnt_c_cog_0001', parent=JOINTS_GRP)
		
		# create controller
		cog_ctrl = crv_lib.create_cube_curve(name='ctrl_c_cog_0001')
		cog_off_ctrl = crv_lib.create_cube_curve(name='ctrl_c_cog_off_0001')
		# CONSTRAINT
		cmds.parentConstraint(cog_off_ctrl, cog_jnt, mo=False)
		cmds.matchTransform(cog_ctrl, LOC_COG)
		cmds.matchTransform(cog_off_ctrl, LOC_COG)
		
		AutoRigHelpers.create_control_hierarchy(cog_ctrl, 1)
		AutoRigHelpers.create_control_hierarchy(cog_off_ctrl, 1)
		cog_zero = AutoRigHelpers.get_parent_grp(cog_ctrl)[3]
		cog_off_zero = AutoRigHelpers.get_parent_grp(cog_off_ctrl)[3]
		cmds.parent(cog_off_zero, cog_ctrl)
		cmds.parent(cog_zero, MOVE_ALL_CTRL)
		

		self.cog_off_ctrl = cog_off_ctrl
		self.cog_jnt = cog_jnt
		
	def create_belly_setup(self):
		belly_jnt_grp = cmds.createNode('transform', n='grp_c_bellyJnts_0001', parent=JOINTS_GRP)
		belly_ctrl_grp = cmds.createNode('transform', n='grp_c_bellyCtrls_0001', parent=self.cog_off_ctrl)
		belly_joints = []
		
		for i in range(1,4):
			jnt = cmds.createNode('joint', n=f'jnt_c_belly_{i:04d}', parent=belly_jnt_grp)
			belly_joints.append(jnt)
		
		cmds.matchTransform(belly_joints[0], self.spine_joints[2], pos=True, rot=False)
		cmds.matchTransform(belly_joints[1], self.spine_joints[-3], pos=True, rot=False)
		cmds.matchTransform(belly_joints[2], self.spine_joints[-1], pos=True, rot=False)
		
		# create belly end joints
		belly_end_joints = []
		for i in range(3):
			jnt = belly_joints[i]
			end_name = f'jnt_c_belly_end_{i+1:04d}'
			belly_end_jnt = cmds.duplicate(jnt, name=end_name)[0]
			cmds.parent(belly_end_jnt, jnt)
			
			ty = AutoRigHelpers.get_attr(jnt, 'translateY')
			AutoRigHelpers.set_attr(belly_joints[i], 'translateY', ty-0.5)
			AutoRigHelpers.set_attr(belly_end_jnt, 'translateY', -8.5)
			
			belly_end_joints.append(belly_end_jnt)
		
		AutoRigHelpers.set_attr(belly_joints[-1], 'rotateX', -24.5)
		cmds.makeIdentity(belly_joints[-1], a=True)
		AutoRigHelpers.set_attr(belly_end_joints[1], 'translateY', -7.5)
		AutoRigHelpers.set_attr(belly_end_joints[-1], 'translateY', -5.5)
		
		# create controllers
		belly_ctrls = []
		for i in range(3):
			ctrl_name = f'ctrl_c_belly_{i + 1:04d}'
			jnt = belly_joints[i]
			if i < 2:
				belly_ctrl = crv_lib.create_cube_curve(ctrl_name)
				cmds.matchTransform(belly_ctrl, jnt)
				AutoRigHelpers.create_control_hierarchy(belly_ctrl, 2)
				cmds.parent(AutoRigHelpers.get_parent_grp(belly_ctrl)[2], belly_ctrl_grp)
				
				AutoRigHelpers.lock_hide_attr(belly_ctrl, ['sx', 'sy', 'sz', 'v'])
				belly_ctrls.append(belly_ctrl)
				cmds.parentConstraint(belly_ctrl, jnt, mo=False)
				continue
			else:
				belly_ctrl = crv_lib.create_cube_curve(ctrl_name)
				cmds.matchTransform(belly_ctrl, jnt)
				AutoRigHelpers.create_control_hierarchy(belly_ctrl, 2)
				cmds.parent(AutoRigHelpers.get_parent_grp(belly_ctrl)[2], belly_ctrl_grp)
				
				belly_off_ctrl = crv_lib.create_cube_curve('ctrl_c_belly_off_0003')
				cmds.matchTransform(belly_off_ctrl, belly_ctrl)
				AutoRigHelpers.create_control_hierarchy(belly_off_ctrl, 2)
				cmds.parent(AutoRigHelpers.get_parent_grp(belly_off_ctrl)[2], belly_ctrl)
				AutoRigHelpers.lock_hide_attr(belly_ctrl, ['sx', 'sy', 'sz', 'v'])
				AutoRigHelpers.lock_hide_attr(belly_off_ctrl, ['sx', 'sy', 'sz', 'v'])
				cmds.parentConstraint(belly_off_ctrl, jnt, mo=False)
				belly_ctrls.append(belly_ctrl)
				belly_ctrls.append(belly_off_ctrl)
				
		# create target group
		belly_data_grp = cmds.createNode('transform', n='grp_c_bellyData_0001', parent=RIG_NODES_LOCAL_GRP)
		belly01_target_grp = cmds.createNode('transform', n='grp_c_belly01_target_0001', parent=belly_data_grp)
		belly01_up_grp = cmds.createNode('transform', n='grp_c_belly01_up_0001', parent=belly01_target_grp)
		belly02_target_grp = cmds.createNode('transform', n='grp_c_belly02_target_0001', parent=belly_data_grp)
		belly02_up_grp = cmds.createNode('transform', n='grp_c_belly02_up_0001',
													   parent=belly02_target_grp)
		
		# belly 01
		loc_belly01_target = cmds.spaceLocator(n='loc_c_belly01_target_0001')[0]
		cmds.parent(loc_belly01_target, belly01_target_grp)
		loc_belly01_aim = cmds.spaceLocator(n='loc_c_belly01_aim_0001')[0]
		cmds.parent(loc_belly01_aim, belly01_target_grp)
		AutoRigHelpers.set_attr(loc_belly01_aim, 'translateX', 10)
		
		# belly 02
		loc_belly02_target = cmds.spaceLocator(n='loc_c_belly02_target_0001')[0]
		cmds.parent(loc_belly02_target, belly02_target_grp)
		loc_belly02_aim = cmds.spaceLocator(n='loc_c_belly02_aim_0001')[0]
		cmds.parent(loc_belly02_aim, belly02_target_grp)
		AutoRigHelpers.set_attr(loc_belly02_aim, 'translateX', 10)
		
		# match transform
		cmds.matchTransform(belly01_target_grp, belly_joints[0])
		cmds.matchTransform(belly02_target_grp, belly_joints[1])
		
		# constraint
		cmds.parentConstraint(self.spine_joints[2], belly01_target_grp, mo=True)
		belly01_up_cMus_cons = cmds.createNode('cMuscleSmartConstraint', n='cMuscleSmartCons_c_belly01_0001')
		AutoRigHelpers.connect_attr(self.spine_joints[1], 'worldMatrix[0]', belly01_up_cMus_cons, 'constrainData.worldMatrixA')
		AutoRigHelpers.connect_attr(self.spine_joints[3], 'worldMatrix[0]', belly01_up_cMus_cons,
									'constrainData.worldMatrixB')
		AutoRigHelpers.connect_attr(belly01_up_cMus_cons, 'outData.outRotate', belly01_up_grp,'rotate')
		
		# create up01 loc
		loc_belly01_up = cmds.spaceLocator(n='loc_c_belly01_up_0001')[0]
		cmds.parent(loc_belly01_up, belly01_up_grp)
		cmds.matchTransform(loc_belly01_up, belly01_up_grp, pos=True, rot=False)
		cmds.pointConstraint(self.spine_joints[2], belly01_up_grp, mo=True)
		AutoRigHelpers.set_attr(belly01_up_grp, 'inheritsTransform', False)
		
		# aim cons
		cmds.aimConstraint(loc_belly01_aim,
						   loc_belly01_target,
						   aimVector=(1,0,0),
						   upVector=(0,1,0),
						   worldUpType='objectRotation',
						   worldUpVector=(0,1,0),
						   worldUpObject=loc_belly01_up,
						   mo=False)
		
		cmds.parentConstraint(loc_belly01_target, AutoRigHelpers.get_parent_grp(belly_ctrls[0])[3], mo=False)
		
		# belly 02 constraint
		cmds.parentConstraint(self.spine_joints[-3], belly02_target_grp, mo=True)
		belly02_up_cMus_cons = cmds.createNode('cMuscleSmartConstraint', n='cMuscleSmartCons_c_belly02_0001')
		AutoRigHelpers.connect_attr(self.spine_joints[-4], 'worldMatrix[0]', belly02_up_cMus_cons,
									'constrainData.worldMatrixA')
		AutoRigHelpers.connect_attr(self.spine_joints[-2], 'worldMatrix[0]', belly02_up_cMus_cons,
									'constrainData.worldMatrixB')
		AutoRigHelpers.connect_attr(belly02_up_cMus_cons, 'outData.outRotate', belly02_up_grp, 'rotate')
		
		# create up01 loc
		loc_belly02_up = cmds.spaceLocator(n='loc_c_belly02_up_0001')[0]
		cmds.parent(loc_belly02_up, belly02_up_grp)
		cmds.matchTransform(loc_belly02_up, belly02_up_grp, pos=True, rot=False)
		cmds.pointConstraint(self.spine_joints[4], belly02_up_grp, mo=True)
		AutoRigHelpers.set_attr(belly02_up_grp, 'inheritsTransform', False)
		
		# aim cons
		cmds.aimConstraint(loc_belly02_aim,
						   loc_belly02_target,
						   aimVector=(1, 0, 0),
						   upVector=(0, 1, 0),
						   worldUpType='objectRotation',
						   worldUpVector=(0, 1, 0),
						   worldUpObject=loc_belly02_up,
						   mo=False)
		
		cmds.parentConstraint(loc_belly02_target, AutoRigHelpers.get_parent_grp(belly_ctrls[1])[3], mo=False)
		
		# constraint belly03 ctrl
		cmds.pointConstraint(self.neck_joints[0], AutoRigHelpers.get_parent_grp(belly_ctrls[2])[3], mo=True)
		cmds.parent(AutoRigHelpers.get_parent_grp(belly_ctrls[2])[2], self.chest_ik_ctrl)
		
		self.belly_joints = belly_joints
		
		return belly_joints
	
	def setup_head_orient(self):
		head_orient_grp = cmds.createNode('transform', n='grp_c_head_orient_0001', parent=RIG_NODES_LOCAL_GRP)
		offset_orient_grp = cmds.createNode('transform', n='offset_c_head_orient_0001', parent=head_orient_grp)
		loc_head_orient_local = cmds.spaceLocator(n='loc_c_head_local_0001')[0]
		loc_head_orient_world = cmds.spaceLocator(n='loc_c_head_world_0001')[0]
		cmds.parent(loc_head_orient_local, offset_orient_grp)
		cmds.parent(loc_head_orient_world, offset_orient_grp)
		
		cmds.matchTransform(head_orient_grp, self.neck_ik_ctrl)
		cmds.parentConstraint(self.chest_ik_ctrl, offset_orient_grp, mo=False)
		
		translate_cons = cmds.parentConstraint(self.cog_jnt, loc_head_orient_world, mo=True)[0]
		rotate_cons = cmds.orientConstraint(self.chest_ik_ctrl, MOVE_ALL_CTRL, loc_head_orient_local, mo=True)[0]
		
		rmp_local_world_rot = cmds.createNode('reverse', n='rvs_c_head_localWorldRot_0001')
		rmp_local_world_trans = cmds.createNode('reverse', n='rvs_c_head_localWorldTrans_0001')
		
		AutoRigHelpers.connect_attr(self.neck_ik_ctrl, 'local_world_rotate', rotate_cons, f'{MOVE_ALL_CTRL}W1')
		AutoRigHelpers.connect_attr(self.neck_ik_ctrl, 'local_world_rotate', rmp_local_world_rot, 'inputX')
		AutoRigHelpers.connect_attr(rmp_local_world_rot, 'outputX', rotate_cons, f'{self.chest_ik_ctrl}W0')
		AutoRigHelpers.set_attr(rotate_cons, 'interpType', 2)
		
		offset_neck_ik = AutoRigHelpers.get_parent_grp(self.neck_ik_ctrl)[1]
		# constraint neck ctrl
		neck_cons = cmds.parentConstraint(loc_head_orient_local, loc_head_orient_world, offset_neck_ik, mo=True)[0]
		AutoRigHelpers.set_attr(neck_cons, 'interpType', 2)
		AutoRigHelpers.connect_attr(self.neck_ik_ctrl, 'local_world_translate', rmp_local_world_trans, 'inputX')
		AutoRigHelpers.connect_attr(self.neck_ik_ctrl, 'local_world_translate', neck_cons, f'{loc_head_orient_world}W1')
		AutoRigHelpers.connect_attr(rmp_local_world_trans, 'outputX', neck_cons, f'{loc_head_orient_local}W0')
		
	def create_pelvis(self):
		pelvis_grp = cmds.createNode('transform', n='grp_c_pelvisJnts_0001', p=JOINTS_GRP)
		pelvis_jnt = cmds.createNode('joint', n='jnt_c_pelvis_0001')
		cmds.matchTransform(pelvis_jnt, self.pelvis_ik_ctrl, pos=True, rot=False)
		cmds.parent(pelvis_jnt, pelvis_grp)
		
		# create controller
		pelvis_ctrl = crv_lib.create_cube_curve('ctrl_c_pelvis_0001')
		cmds.matchTransform(pelvis_ctrl, pelvis_jnt)
		AutoRigHelpers.create_control_hierarchy(pelvis_ctrl, 2)
		pelvis_zero = AutoRigHelpers.get_parent_grp(pelvis_ctrl)[2]
		cmds.parent(pelvis_zero, self.pelvis_ik_ctrl)
		
		cmds.parentConstraint(pelvis_ctrl, pelvis_jnt, mo=False)
		
		self.pelvis_ctrl = pelvis_ctrl
		
	def create_tail(self):
		tail_joints = self.joint_on_curve(self.tail_curve, 'tail', 8)
		tail_root = tail_joints[0]
		
		# create jnt grp
		tail_jnt_grp = cmds.createNode('transform', n='grp_c_tailJnts_0001', p=JOINTS_GRP)
		cmds.parent(tail_root, tail_jnt_grp)
		
		# clear end joint orientation
		end_joint = tail_joints[-1]
		for axis in ("X", "Y", "Z"):
			cmds.setAttr(f"{end_joint}.jointOrient{axis}", 0)
		
		self.create_tail_ctrl(tail_joints)
		
	def create_tail_ctrl(self, tail_joints, sub_count=2):
		# create ctrl group
		ctrl_root_grp = cmds.createNode('transform', n='grp_c_tailCtrls_0001')
		cmds.parent(ctrl_root_grp, self.pelvis_ctrl)
		
		# create fk controller
		small_driven_groups = []
		small_controls = []
		prev_ctrl = None
		
		for i, jnt in enumerate(tail_joints[:-1]):
			small_ctrl = crv_lib.circle(3, f'ctrl_c_tail_{i+1:04d}')
			cmds.matchTransform(small_ctrl, jnt)
			cmds.parentConstraint(small_ctrl, jnt, mo=False)
			AutoRigHelpers.create_control_hierarchy(small_ctrl, 3)
			_, small_zero, small_offset, small_driven = AutoRigHelpers.get_parent_grp(small_ctrl)
			
			if prev_ctrl is None:
				cmds.parent(small_zero, ctrl_root_grp)
			else:
				cmds.parent(small_zero, prev_ctrl)
			
			prev_ctrl = small_ctrl
			small_controls.append(small_ctrl)
			small_driven_groups.append(small_driven)
			
		self.create_tail_sub_ctrls(tail_joints, ctrl_root_grp, small_driven_groups, small_controls)
	
	
	def create_tail_sub_ctrls(self, tail_joints, root_ctrl_grp, driven_grp, small_ctrl, joints_per_ctrl=3, prefix='ctrl_c_tailDrv'):
		"""
		Create tail sub-controllers along the tail joint chain.
		Each sub-controller drives a fixed number of joints (joints_per_ctrl).
		Example:
			tail_joints = 9, joints_per_ctrl = 3 → controllers at joints [0, 3, 6]
		"""
		# Create control group
		ctrl_grp = cmds.createNode('transform', n='grp_c_tailDrvCtrls_0001', p=root_ctrl_grp)
		
		# Remove the terminal joint
		chain = tail_joints[:-1]
		n = len(chain)
		if n == 0:
			cmds.warning("No tail joints found.")
			return []
		
		# Determine evenly spaced indices — e.g., [0, 3, 6]
		step = max(1, joints_per_ctrl)
		idxs = list(range(0, n, step))
		
		# ⚙️ Clamp last index to avoid duplication of last joint
		if idxs[-1] >= n:
			idxs[-1] = n - 1
		
		sub_ctrls = []
		for i, idx in enumerate(idxs, 1):
			jnt = chain[idx]
			ctrl = crv_lib.create_square_curve(f"{prefix}_{i:04d}", 20)
			cmds.matchTransform(ctrl, jnt)
			
			# Build hierarchy
			AutoRigHelpers.create_control_hierarchy(ctrl, 2)
			_, _, ctrl_zero, ctrl_offset = AutoRigHelpers.get_parent_grp(ctrl)
			cmds.parent(ctrl_zero, ctrl_grp)
			sub_ctrls.append(ctrl)
			
			# Constrain next range of joints to this control
			start_idx = idx
			end_idx = min(idx + step, n)
			segment = driven_grp[start_idx:end_idx]
			ctrl_segment = small_ctrl[start_idx:end_idx]
			print(i)
			print(ctrl_segment)
			
			# connect rotation
			for seg_driven in segment:
				for rot in ['rotateX','rotateY','rotateZ']:
					AutoRigHelpers.connect_attr(ctrl, rot, seg_driven, rot)
			
			if i > 1:  # skip sub ctrl 001
				# parent under small_ctrl at the start joint of its own range
				parent_target_idx = idx-1  # start joint index of this segment
				if parent_target_idx < len(small_ctrl):
					parent_target = small_ctrl[parent_target_idx]
					cmds.parent(ctrl_zero, parent_target)
		
			AutoRigHelpers.lock_hide_attr(ctrl, ['tx', 'ty', 'tz'])
		return sub_ctrls
	
	def construct_rig(self):
		self.create_cog()
		
		# spine
		self.create_spine_joints()
		self.create_spine_setup()
		self.setup_stretch('spine', 'strFw', self.str_fw_joints, self.spine_fw_curve)
		self.setup_stretch('spine', 'strBw', self.str_bw_joints, self.spine_bw_curve)
		self.blend_fw_bw(self.spine_switch_ctrl, 'spine', self.str_fw_joints, self.str_bw_joints, self.str_joints)
		self.blend_fw_bw(self.spine_switch_ctrl, 'spine', self.non_str_fw_joints, self.non_str_bw_joints, self.non_str_joints)
		self.blend_str_nonStr(self.spine_switch_ctrl, 'spine', self.str_joints, self.non_str_joints, self.spine_joints)
		
		# neck
		self.create_neck_joints()
		self.create_neck_setup()
		self.setup_stretch('neck', 'str', self.neck_str_joints, self.neck_curve, False)
		self.blend_str_nonStr(self.neck_switch_ctrl, 'neck', self.neck_str_joints, self.neck_non_str_joints, self.neck_joints)
		
		# create belly
		self.create_belly_setup()
		
		# create pelvis
		self.create_pelvis()
		
		# head orient
		self.setup_head_orient()
		
		# create tail
		self.create_tail()
		
		AutoRigHelpers.lock_and_hide_ctrls()
#
# if __name__ == "__main__":
# 	spine_neck_rig = SpineNeckAutoRig()
# 	spine_neck_rig.construct_rig()

