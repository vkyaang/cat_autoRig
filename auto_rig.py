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

class SpineNeckAutoRig(object):
	
	def __init__(self):
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
	
	def joint_on_curve(self, cv, name="spine", jntNum=7, span=7):
		# Rebuild curve (optional, for even parameterization)
		cmds.rebuildCurve(cv, ch=1, rpo=1, rt=0, end=1, kr=0,
						  kcp=0, kep=1, kt=0, s=span, d=3)
		
		for j in range(jntNum + 1):
			idx = str(j + 1).zfill(4)
			jnt_name = 'jnt' + '_c_' + name + "_" + idx
			
			# Get point along curve using parameter
			param = float(j) / jntNum
			pos = cmds.pointOnCurve(cv, pr=param, p=True)  # world position
			
			spine_joint = cmds.joint(p=pos, rad=1, n=jnt_name)
			self.spine_joints.append(spine_joint)
		
		# Build spline IK
		spine_ikh = cmds.ikHandle(
			sj=self.spine_joints[0],
			ee=self.spine_joints[-1],
			c=cv,
			ccv=False,
			sol='ikSplineSolver',
			pcv=0,
			n='spine_ikHandle'
		)[0]
		
		# Cleanup
		cmds.delete(spine_ikh)
		cmds.makeIdentity(self.spine_joints, apply=True, t=1, r=1, s=1, n=0, pn=1)
		cmds.joint(self.spine_joints[0], e=True, oj="xyz", secondaryAxisOrient="yup", ch=True, zso=True)
	
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
		self.spine_fw_curve = cmds.rename(self.spine_fw_curve, "crv_c_spineFw_0001")
		self.spine_bw_curve = cmds.duplicate(self.spine_fw_curve, rc=True, name="crv_c_spineBw_0001")
		
		self.spine_data_grp = AutoRigHelpers.create_empty_group("grp_spineData_0001", parent="rigNodesLocal")
		self.spine_fw_curve = cmds.parent(self.spine_fw_curve, self.spine_data_grp)[0]
		self.spine_bw_curve = cmds.parent(self.spine_bw_curve, self.spine_data_grp)[0]
		
		cmds.reverseCurve(self.spine_bw_curve, ch=False, rpo=True)
		
		return self.spine_fw_curve, self.spine_bw_curve
		
	def create_spine_joints(self):
		"""Create and organize spine joint chains (forward/backward, stretch/non-stretch)."""
		# 1️⃣ Create the base spine joints along the curve
		
		self.joint_on_curve(self.spine_fw_curve)
		
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
		AutoRigHelpers.set_attr(spine_mid_jnt, 'translateY', spine_mid_jnt_ty+0.8)
		
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
		AutoRigHelpers.set_attr(bw_spine_ik, 'dWorldUpType', 4)
		AutoRigHelpers.set_attr(fw_spine_ik, 'dForwardAxis', 1)
		
		# Assign world up objects
		# fw str
		AutoRigHelpers.connect_attr(self.pelvis_ik_ctrl, 'worldMatrix[0]', fw_spine_ik, 'dWorldUpMatrix', True)
		AutoRigHelpers.connect_attr(self.chest_ik_jnt, 'worldMatrix[0]', fw_spine_ik, 'dWorldUpMatrixEnd', True)
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
		spine_ctrl_grp = cmds.createNode('transform', name='grp_spineCtrls', parent=MOVE_ALL_CTRL)
		
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
		print(pelvis_tangent_zero)
		cmds.parent(pelvis_tangent_zero, spine_ctrl_grp)
		cmds.parent(chest_tangent_zero, spine_ctrl_grp)

		cmds.parentConstraint(pelvis_ik_ctrl, AutoRigHelpers.get_parent_grp(pelvis_tangent_ctrl)[3], mo=False)
		cmds.parentConstraint(chest_ik_ctrl, AutoRigHelpers.get_parent_grp(chest_tangent_ctrl)[3], mo=False)
		
		AutoRigHelpers.connect_attr(pelvis_tangent_ctrl, "rotate", self.pelvis_ik_jnt, 'rotate')
		AutoRigHelpers.connect_attr(pelvis_tangent_ctrl, "tangent_length", self.pelvis_ik_jnt, 'sz')
		AutoRigHelpers.connect_attr(chest_tangent_ctrl, "rotate", self.chest_ik_jnt, 'rotate')
		AutoRigHelpers.connect_attr(chest_tangent_ctrl, "tangent_length", self.chest_ik_jnt, 'sz')
		
		self.pelvis_ik_ctrl = pelvis_ik_ctrl
		self.chest_ik_ctrl = chest_ik_ctrl
		self.spine_switch_ctrl = spine_switch_ctrl
	
	@classmethod
	def setup_stretch(cls, name, detail, str_chain, crv):
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
		
		# connect to joints (exclude last)
		for jnt in str_chain[:-1]:
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
		# 1️⃣ Create the base spine joints along the curve
		
		self.joint_on_curve(self.neck_curve, 'neck', 6)
		
		# 2️⃣ Create main groups
		self.neck_joints_grp = AutoRigHelpers.create_empty_group("grp_neckJnts_0001", parent='joints')
		
		# 3️⃣ Clear end joint orientation
		end_joint = self.neck_joints[-1]
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
	def construct_rig(self):
		# spine
		self.create_spine_joints()
		self.create_spine_setup()
		self.setup_stretch('spine', 'strFw', self.str_fw_joints, self.spine_fw_curve)
		self.setup_stretch('spine', 'strBw', self.str_bw_joints, self.spine_bw_curve)
		self.blend_fw_bw(self.spine_switch_ctrl, 'spine', self.str_fw_joints, self.str_bw_joints, self.str_joints)
		self.blend_fw_bw(self.spine_switch_ctrl, 'spine', self.non_str_fw_joints, self.non_str_bw_joints, self.non_str_joints)
		self.blend_str_nonStr(self.spine_switch_ctrl, 'spine', self.str_joints, self.non_str_joints, self.spine_joints)
#
# if __name__ == "__main__":
# 	spine_neck_rig = SpineNeckAutoRig()
# 	spine_neck_rig.construct_rig()

