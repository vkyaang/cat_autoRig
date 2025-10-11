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


class LimbsAutoRig(object):
	def __init__(self):
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
			self.create_leg_setup(side)
