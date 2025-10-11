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

	# ------------- small utils -------------
	def side_tag(self, side, name):
		return name.replace('_c_', f'_{side}_')

	def _ensure_group(self, name, parent=None):
		if cmds.objExists(name):
			return name
		if parent and not cmds.objExists(parent):
			cmds.createNode('transform', n=parent)
		return cmds.createNode('transform', n=name, p=parent) if parent else cmds.createNode('transform', n=name)

	def _strip_trailing_index(self, node_name):
		parts = node_name.split('_')
		if parts and parts[-1].isdigit():
			parts = parts[:-1]
		return '_'.join(parts)

	def _strip_fk_ik(self, node_name):
		# remove occurrences like _fk_ or _ik_ without regex
		name = node_name
		for mid in ['_fk_', '_FK_', '_fK_', '_Fk_', '_ik_', '_IK_', '_iK_', '_Ik_']:
			if mid in name:
				name = name.replace(mid, '_')
		return name

	def _first_existing(self, names):
		for n in names:
			if cmds.objExists(n):
				return n
		return None

	# ------------- build base joints -------------
	def create_joints(self, temp_jnt, mirror=True):
		if not cmds.objExists(temp_jnt):
			cmds.warning("Missing template joint: {0}".format(temp_jnt))
			return [], []

		new_root = cmds.duplicate(temp_jnt, rc=True)[0]
		all_joints = cmds.listRelatives(new_root, ad=True, type='joint') or []
		all_joints.append(new_root)
		all_joints.reverse()

		new_chain = []
		for jnt in all_joints:
			name = jnt.replace("temp", "jnt").replace("0002", "0001")
			name = cmds.rename(jnt, name)
			new_chain.append(name)

		mirrored_chain = []
		if mirror:
			mirrored_chain = cmds.mirrorJoint(new_chain[0], mirrorYZ=True, mirrorBehavior=True, searchReplace=('_l_', '_r_'))

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

	# ------------- duplicate chains (FK / IK) -------------
	def duplicate_chain(self, source_chain, suffix):
		if not source_chain:
			cmds.warning("Empty source chain passed to duplicate_chain.")
			return []

		dup_root = cmds.duplicate(source_chain[0], rc=True)[0]
		all_joints = cmds.listRelatives(dup_root, ad=True, type='joint') or []
		all_joints.append(dup_root)
		all_joints.reverse()

		new_chain = []
		for jnt in all_joints:
			# cleanup name before applying suffix
			base = self._strip_trailing_index(self._strip_fk_ik(jnt))
			new_name = "{0}_{1}_0001".format(base, suffix.lower())
			new_name = cmds.rename(jnt, new_name)
			new_chain.append(new_name)

		return new_chain

	# ------------- FK/IK leg sets -------------
	def create_fk_ik_leg_joints(self, side, joint_chain):
		if not joint_chain:
			return

		region = "ft" if "ft" in joint_chain[0] else "bk"

		fk_chain = self.duplicate_chain(joint_chain, "fk")
		ik_chain = self.duplicate_chain(joint_chain, "ik")

		setattr(self, f"{side}_{region}_leg_fk_joints", fk_chain)
		setattr(self, f"{side}_{region}_leg_ik_joints", ik_chain)

		leg_root = self._ensure_group("grp_legJnts_0001", JOINTS_GRP)
		rig_grp = self._ensure_group(f"grp_{side}_{region}_legJnts_0001", leg_root)

		for root in [joint_chain[0], fk_chain[0], ik_chain[0]]:
			if cmds.listRelatives(root, p=True) != [rig_grp]:
				try:
					cmds.parent(root, rig_grp)
				except:
					pass

	# ------------- FK controls -------------
	def build_fk_setup(self, side, joint_chain):
		if not joint_chain:
			return

		region = "ft" if "ft" in joint_chain[0] else "bk"

		ctrl_root = self._ensure_group("grp_legCtrls_0001", MOVE_ALL_CTRL)
		fk_grp = self._ensure_group(f"grp_{side}_{region}_legFkCtrls_0001", ctrl_root)

		prev_ctrl = None
		for jnt in joint_chain[:-1]:
			ctrl_name = jnt.replace("jnt", "ctrl")
			fk_ctrl = crv_lib.create_cube_curve(ctrl_name)
			cmds.matchTransform(fk_ctrl, jnt)

			AutoRigHelpers.create_control_hierarchy(fk_ctrl, 2)
			zero_grp = fk_ctrl.replace("ctrl", "zero")

			if prev_ctrl is None:
				cmds.parent(zero_grp, fk_grp)
			else:
				# parent child zero under previous ctrl to form FK chain
				cmds.parent(zero_grp, prev_ctrl)

			cmds.orientConstraint(fk_ctrl, jnt, mo=False)
			prev_ctrl = fk_ctrl

	# ------------- scapula joints -------------
	def create_scapula_joint(self, side, temp_joint):
		root = self._ensure_group('grp_scapulaJnts_0001', JOINTS_GRP)
		l_grp = self._ensure_group('grp_l_scapulaJnts_0001', root)
		r_grp = self._ensure_group('grp_r_scapulaJnts_0001', root)

		if not cmds.objExists('jnt_l_scapula_0001'):
			l_scap, r_scap = self.create_joints(temp_joint, mirror=True)

			if l_scap:
				try: cmds.parent(l_scap[0], l_grp)
				except: pass
			if r_scap:
				try: cmds.parent(r_scap[0], r_grp)
				except: pass

			self.l_scapula_joints = l_scap
			self.r_scapula_joints = r_scap

	# ------------- scapula controls -------------
	def create_scapula_ctrls(self, side, joint_chain):
		if not joint_chain:
			cmds.warning("No joints for scapula on side: {0}".format(side))
			return

		ctrl_root = self._ensure_group('grp_scapulaCtrls_0001', MOVE_ALL_CTRL)
		side_grp = self._ensure_group(f'grp_{side}_scapulaCtrls_0001', ctrl_root)

		jnt = joint_chain[0]
		ctrl_name = f'ctrl_{side}_scapula_0001'

		ctrl = crv_lib.create_prism_line(ctrl_name)
		cmds.matchTransform(ctrl, jnt)

		AutoRigHelpers.create_control_hierarchy(ctrl, 2)
		zero_grp = ctrl.replace("ctrl", "zero")
		cmds.parent(zero_grp, side_grp)
		cmds.parentConstraint(ctrl, jnt, mo=False)

		# mirror only the SHAPE for right side
		if side == 'r':
			left_ctrl = ctrl.replace('_r_', '_l_')
			if cmds.objExists(left_ctrl):
				AutoRigHelpers.mirror_curve_shape(left_ctrl, ctrl)

		setattr(self, f"{side}_scapula_ctrl", ctrl)

	# ------------- scapula orient rig bits -------------
	def create_scapula_orient(self, side, joint_chain):
		root = self._ensure_group('grp_scapula_orient_0001', RIG_NODES_LOCAL_GRP)

		for s in ['l', 'r']:
			side_grp = self._ensure_group(f'grp_{s}_scapulaOrient_0001', root)
			offset_grp = self._ensure_group(f'offset_{s}_scapulaOrient_0001', side_grp)

			loc_local = self._first_existing([f'loc_{s}_scapula_local_0001'])
			if not loc_local:
				loc_local = cmds.spaceLocator(n=f'loc_{s}_scapula_local_0001')[0]
				cmds.parent(loc_local, offset_grp)

			loc_world = self._first_existing([f'loc_{s}_scapula_world_0001'])
			if not loc_world:
				loc_world = cmds.spaceLocator(n=f'loc_{s}_scapula_world_0001')[0]
				cmds.parent(loc_world, offset_grp)

			chain = getattr(self, f'{s}_scapula_joints', None)
			if chain:
				cmds.matchTransform(side_grp, chain[0])

	# ------------- wrappers -------------
	def create_scapula_setup(self, side):
		self.create_scapula_joint(side, TEMP_SCAPULA)
		self.create_scapula_ctrls(side, getattr(self, f'{side}_scapula_joints'))
		self.create_scapula_orient(side, getattr(self, f'{side}_scapula_joints'))

	def create_leg_setup(self, side):
		self.create_fk_ik_leg_joints(side, getattr(self, f"{side}_ft_leg_joints"))
		self.create_fk_ik_leg_joints(side, getattr(self, f"{side}_bk_leg_joints"))

		self.build_fk_setup(side, getattr(self, f"{side}_ft_leg_fk_joints"))
		self.build_fk_setup(side, getattr(self, f"{side}_bk_leg_fk_joints"))

	# ------------- entry -------------
	def construct_rig(self):
		self.create_joints(TEMP_FT_LEG_JOINTS, mirror=True)
		self.create_joints(TEMP_BK_LEG_JOINTS, mirror=True)

		for side in ["l", "r"]:
			self.create_scapula_setup(side)
			self.create_leg_setup(side)
