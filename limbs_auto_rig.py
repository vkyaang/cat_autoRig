import maya.cmds as cmds
import importlib
import auto_rig_helpers
import curve_library

importlib.reload(auto_rig_helpers)
importlib.reload(curve_library)
from auto_rig_helpers import AutoRigHelpers
crv_lib = curve_library.RigCurveLibrary()

MOVE_ALL_CTRL = 'ctrl_c_moveAll_0002'
COG_OFF_CTRL = 'ctrl_cog_off_0001'
RIG_NODES_LOCAL_GRP = 'rigNodesLocal'
CONTROLS_GRP = 'controls'
JOINTS_GRP = 'joints'

TEMP_FT_LEG_JOINTS = 'temp_l_ft_upperLeg_0001'
TEMP_BK_LEG_JOINTS = 'temp_l_bk_upperLeg_0001'
TEMP_SCAPULA = 'temp_l_scapula_0001'


class LimbsAutoRig(object):
	def __init__(self):
		self.r_scapula_ctrl = None
		self.l_scapula_ctrl = None
		self.r_scapula_joints = None
		self.l_scapula_joints = None
		self.l_ft_leg_joints = []
		self.r_ft_leg_joints = []
		self.l_bk_leg_joints = []
		self.r_bk_leg_joints = []
		self.l_ft_leg_fk_joints = []
		self.r_ft_leg_fk_joints = []
		self.l_ft_leg_ik_joints = []
		self.r_ft_leg_ik_joints = []
		self.l_bk_leg_fk_joints = []
		self.r_bk_leg_fk_joints = []
		self.l_bk_leg_ik_joints = []
		self.r_bk_leg_ik_joints = []

	def side_tag(self, side, name):
		return name.replace('_c_', f'_{side}_')

	def create_joints(self, temp_jnt, mirror=True):
		if not cmds.objExists(temp_jnt):
			cmds.warning(f"Missing template joint: {temp_jnt}")
			return [], []

		new_root = cmds.duplicate(temp_jnt, rc=True)[0]
		all_joints = cmds.listRelatives(new_root, ad=True, type='joint') or []
		all_joints.append(new_root)
		all_joints.reverse()

		new_chain = []
		for jnt in all_joints:
			new_name = jnt.replace("temp", "jnt").replace("0002", "0001")
			new_name = cmds.rename(jnt, new_name)
			new_chain.append(new_name)

		mirrored_chain = []
		if mirror:
			mirrored_chain = cmds.mirrorJoint(
				new_chain[0],
				mirrorYZ=True,
				mirrorBehavior=True,
				searchReplace=('_l_', '_r_')
			)

		self.auto_store_chains(temp_jnt, new_chain, mirrored_chain)
		return new_chain, mirrored_chain

	def auto_store_chains(self, temp_name, left_chain, right_chain):
		if "ft" in temp_name:
			self.l_ft_leg_joints = left_chain
			self.r_ft_leg_joints = right_chain
		elif "bk" in temp_name:
			self.l_bk_leg_joints = left_chain
			self.r_bk_leg_joints = right_chain
		elif "scapula" in temp_name:
			self.l_scapula_joints = left_chain
			self.r_scapula_joints = right_chain
	
	def duplicate_chain(self, source_chain, suffix):
		"""
		Duplicate an existing joint chain and rename with lowercase suffix.
		Example:
			jnt_l_ft_upperLeg_0001 → jnt_l_ft_upperLeg_fk_0001
			jnt_l_ft_lowerLeg_0003 → jnt_l_ft_lowerLeg_fk_0001
		"""
		if not source_chain:
			cmds.warning("⚠️ Empty source chain passed to duplicate_chain.")
			return []
		
		# Duplicate full hierarchy
		dup_root = cmds.duplicate(source_chain[0], rc=True)[0]
		all_joints = cmds.listRelatives(dup_root, ad=True, type='joint') or []
		all_joints.append(dup_root)
		all_joints.reverse()  # parent → child
		
		new_chain = []
		for jnt in all_joints:
			# remove any old fk/ik label
			if "_fk_" in jnt:
				jnt = jnt.replace("_fk_", "_")
			if "_ik_" in jnt:
				jnt = jnt.replace("_ik_", "_")
			
			# find last underscore for numeric part
			if "_" in jnt:
				parts = jnt.split("_")
				if parts[-1].isdigit():
					# remove the numeric part and rebuild
					base_name = "_".join(parts[:-1])
				else:
					base_name = jnt
			else:
				base_name = jnt
			
			# append new suffix and reset index to _0001
			new_name = f"{base_name}_{suffix.lower()}_0001"
			new_name = cmds.rename(jnt, new_name)
			new_chain.append(new_name)
		
		print(f"✅ Duplicated {suffix.lower()} chain: {new_chain}")
		return new_chain
	
	def create_fk_ik_leg_joints(self, side, joint_chain):
		if not joint_chain:
			cmds.warning(f"Empty chain for {side} side.")
			return

		region = "ft" if "ft" in joint_chain[0] else "bk"

		fk_chain = self.duplicate_chain(joint_chain, "fK")
		ik_chain = self.duplicate_chain(joint_chain, "iK")
		
		
		attr_fk = f"{side}_{region}_leg_fk_joints"
		attr_ik = f"{side}_{region}_leg_ik_joints"
		setattr(self, attr_fk, fk_chain)
		setattr(self, attr_ik, ik_chain)

		# Create main leg joint group once
		if not cmds.objExists("grp_legJnts_0001"):
			cmds.createNode("transform", n="grp_legJnts_0001", p=JOINTS_GRP)

		# Create side-region group (like grp_l_ft_legJnts_0001)
		rig_grp = f"grp_{side}_{region}_legJnts_0001"
		if not cmds.objExists(rig_grp):
			cmds.createNode("transform", n=rig_grp, p="grp_legJnts_0001")

		cmds.parent(joint_chain[0], rig_grp)
		cmds.parent(fk_chain[0], rig_grp)
		cmds.parent(ik_chain[0], rig_grp)
	
	def build_fk_setup(self, side, joint_chain):
		region = "ft" if "ft" in joint_chain[0] else "bk"
		
		# main FK group
		if not cmds.objExists("grp_legCtrls_0001"):
			cmds.createNode("transform", n="grp_legCtrls_0001", p=MOVE_ALL_CTRL)
		
		fk_grp = f"grp_{side}_{region}_legFkCtrls_0001"
		if not cmds.objExists(fk_grp):
			cmds.createNode("transform", n=fk_grp, p="grp_legCtrls_0001")
		
		prev_ctrl = None
		for jnt in joint_chain[:-1]:
			ctrl_name = jnt.replace("jnt", "ctrl")
			fk_ctrl = crv_lib.create_cube_curve(ctrl_name)
			cmds.matchTransform(fk_ctrl, jnt)
			
			# create hierarchy (zero → offset → ctrl)
			AutoRigHelpers.create_control_hierarchy(fk_ctrl, 2)
			
			# get zero and offset groups by name
			zero_grp = fk_ctrl.replace("ctrl", "zero")
			offset_grp = fk_ctrl.replace("ctrl", "offset")
			
			# parent properly
			if prev_ctrl is None:
				cmds.parent(zero_grp, fk_grp)
			else:
				cmds.parent(zero_grp, prev_ctrl)
			
			# constraint (rotation only for FK)
			cmds.orientConstraint(fk_ctrl, jnt, mo=False)
			
			prev_ctrl = fk_ctrl
	
	def create_scapula_joint(self, side, temp_joint):
		# === Main scapula group (root under joints) ===
		scapula_root_grp = 'grp_scapulaJnts_0001'
		if not cmds.objExists(scapula_root_grp):
			cmds.createNode('transform', n=scapula_root_grp, p=JOINTS_GRP)
		
		# === Create both side subgroups ===
		side_grps = {}
		for s in ['l', 'r']:
			side_grp = f'grp_{s}_scapulaJnts_0001'
			if not cmds.objExists(side_grp):
				side_grp = cmds.createNode('transform', n=side_grp, p=scapula_root_grp)
			side_grps[s] = side_grp
		
		# === Only build once (on left); mirroring handles right ===
		if not cmds.objExists('jnt_l_scapula_0001'):
			l_scapula_joints, r_scapula_joints = self.create_joints(temp_joint, mirror=True)
			
			# Parent cleanly
			if l_scapula_joints and cmds.objExists(side_grps['l']):
				cmds.parent(l_scapula_joints[0], side_grps['l'])
			if r_scapula_joints and cmds.objExists(side_grps['r']):
				cmds.parent(r_scapula_joints[0], side_grps['r'])
			
			# Store for later access
			self.l_scapula_joints = l_scapula_joints
			self.r_scapula_joints = r_scapula_joints
			
		else:
			print("Scapula joints already exist — skipping creation.")
	
	def create_scapula_ctrls(self, side, joint_chain):
		# MAIN group
		scapula_ctrl_grp = 'grp_scapulaCtrls_0001'
		if not cmds.objExists(scapula_ctrl_grp):
			cmds.createNode('transform', n='grp_scapulaCtrls_0001', p=MOVE_ALL_CTRL)
		
		# Side groups
		side_grps = {}
		for s in ['l', 'r']:
			side_grp = f'grp_{s}_scapulaCtrls_0001'
			if not cmds.objExists(side_grp):
				side_grp = cmds.createNode('transform', n=side_grp, p=scapula_ctrl_grp)
			side_grps[s] = side_grp
		
		# Create single scapula controller for this side
		if not joint_chain:
			cmds.warning(f"⚠️ No joints found for scapula on side '{side}'")
			return
		
		jnt = joint_chain[0]  # scapula joint is usually single
		ctrl_name = f'ctrl_{side}_scapula_0001'
		
		ctrl = crv_lib.create_prism_line(ctrl_name)
		cmds.matchTransform(ctrl, jnt)
		
		# create hierarchy (zero → offset → ctrl)
		AutoRigHelpers.create_control_hierarchy(ctrl, 2)
		zero_grp = ctrl.replace("ctrl", "zero")
		cmds.parent(zero_grp, side_grps[side])
		
		cmds.parentConstraint(ctrl, jnt, mo=False)
		
		print(f"✅ Created scapula control: {ctrl}")
		
		# ⚙️ Mirror only the SHAPE if this is the right side
		if side == 'r':
			left_ctrl = ctrl.replace('_r_', '_l_')
			if cmds.objExists(left_ctrl):
				AutoRigHelpers.mirror_curve_shape(left_ctrl, ctrl)
				print(f"🔁 Mirrored shape from {left_ctrl} → {ctrl}")
			else:
				cmds.warning(f"⚠️ Left control not found for shape mirror: {left_ctrl}")
		
		# 🔹 Store controller reference for this side
		setattr(self, f"{side}_scapula_ctrl", ctrl)
	
	def create_scapula_orient(self, side, joint_chain):
		orient_grp = 'grp_scapula_orient_0001'
		if not cmds.objExists(orient_grp):
			cmds.createNode('transform', n=orient_grp, p=RIG_NODES_LOCAL_GRP)
		
		side_grps = {}
		loc_locals = []
		
		for s in ['l', 'r']:
			side_grp = f'grp_{s}_scapulaOrient_0001'
			offset_grp = f'offset_{s}_scapulaOrient_0001'
			loc_local_name = f'loc_{s}_scapula_local_0001'
			loc_world_name = f'loc_{s}_scapula_world_0001'
			
			# ensure groups exist
			if not cmds.objExists(side_grp):
				side_grp = cmds.createNode('transform', n=side_grp, p=orient_grp)
			if not cmds.objExists(offset_grp):
				offset_grp = cmds.createNode('transform', n=offset_grp, p=side_grp)
			
			# ensure locators exist
			if not cmds.objExists(loc_local_name):
				loc_local = cmds.spaceLocator(n=loc_local_name)[0]
				cmds.parent(loc_local, offset_grp)
			else:
				loc_local = loc_local_name
			
			if not cmds.objExists(loc_world_name):
				loc_world = cmds.spaceLocator(n=loc_world_name)[0]
				cmds.parent(loc_world, offset_grp)
			else:
				loc_world = loc_world_name
			
			# match transform for alignment
			if getattr(self, f'{s}_scapula_joints', None):
				cmds.matchTransform(side_grp, getattr(self, f'{s}_scapula_joints')[0])
			
			# ✅ Always append the locator name
			loc_locals.append(loc_local)
			side_grps[s] = side_grp
		
		print(f'✅ Stored local locators: {loc_locals}')
		# self.loc_scapula_locals = loc_locals
	
	def create_scapula_setup(self, side):
		self.create_scapula_joint(side, TEMP_SCAPULA)
		self.create_scapula_ctrls(side, getattr(self, f'{side}_scapula_joints'))
		self.create_scapula_orient(side, getattr(self, f'{side}_scapula_joints'))
	
	def create_leg_setup(self, side):
		# create joints
		self.create_fk_ik_leg_joints(side, getattr(self, f"{side}_ft_leg_joints"))
		self.create_fk_ik_leg_joints(side, getattr(self, f"{side}_bk_leg_joints"))
		
		# create fk setup
		self.build_fk_setup(side, getattr(self, f"{side}_ft_leg_fk_joints"))
		self.build_fk_setup(side, getattr(self, f"{side}_bk_leg_fk_joints"))

	def construct_rig(self):
		self.create_joints(TEMP_FT_LEG_JOINTS, mirror=True)
		self.create_joints(TEMP_BK_LEG_JOINTS, mirror=True)
		
		for side in ["l", "r"]:
			# create scapula
			self.create_scapula_setup(side)
			self.create_leg_setup(side)
