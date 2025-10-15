import maya.cmds as cmds
import maya.mel as mel
import importlib
import auto_rig_helpers
import neck_spine_auto_rig
import curve_library

importlib.reload(auto_rig_helpers)
importlib.reload(curve_library)
importlib.reload(neck_spine_auto_rig)
from auto_rig_helpers import AutoRigHelpers

crv_lib = curve_library.RigCurveLibrary()

class Master(object):
	
	def __init__(self):
		self.control_grp = None
		self.joint_grp = None
		self.rig_nodes_local = None
		self.rig_nodes_world = None
		
		self.move_all_off_ctrl = None
	
	def create_groups(self):
		master_grp = cmds.createNode('transform', n='master')
		
		if cmds.objExists('geometry'):
			cmds.parent('geometry', master_grp)
			
		control_grp = cmds.createNode('transform', n='controls', p=master_grp)
		joint_grp = cmds.createNode('transform', n='joints', p=master_grp)
		rig_nodes_world = cmds.createNode('transform', n='rigNodesWorld', p=master_grp)
		rig_nodes_local = cmds.createNode('transform', n='rigNodesLocal', p=master_grp)
		
		AutoRigHelpers.set_attr(rig_nodes_local, 'visibility', False)
		
		self.rig_nodes_world = rig_nodes_world
		self.rig_nodes_local = rig_nodes_local
		AutoRigHelpers.store(f'master_grp', master_grp)
		AutoRigHelpers.store(f'control_grp', control_grp)
		AutoRigHelpers.store(f'joint_grp', joint_grp)
		AutoRigHelpers.store(f'rig_nodes_world', rig_nodes_world)
		AutoRigHelpers.store(f'rig_nodes_local', rig_nodes_local)
		
	def create_move_all_ctrl(self, control_grp):
		move_all_ctrl = crv_lib.circle(22, 'ctrl_c_move_all_0001')
		move_all_off_ctrl = crv_lib.create_four_arrow_curve('ctrl_c_move_all_0002')
		
		AutoRigHelpers.create_control_hierarchy(move_all_ctrl, 1)
		AutoRigHelpers.create_control_hierarchy(move_all_off_ctrl, 1)
		
		AutoRigHelpers.lock_hide_attr(move_all_ctrl, ['v'])
		AutoRigHelpers.lock_hide_attr(move_all_off_ctrl, ['v'])
		
		move_all_zero = AutoRigHelpers.get_parent_grp(move_all_ctrl)[3]
		move_all_off_zero = AutoRigHelpers.get_parent_grp(move_all_off_ctrl)[3]
		
		cmds.parent(move_all_zero, control_grp)
		cmds.parent(move_all_off_zero, move_all_ctrl)
		
		cmds.scaleConstraint(move_all_off_ctrl, AutoRigHelpers.get('joint_grp'))
		cmds.scaleConstraint(move_all_off_ctrl, AutoRigHelpers.get('rig_nodes_world'))
		
		# # connect scale
		# AutoRigHelpers.add_attr(move_all_ctrl, 'scale_rig', 'float', 1, 0)
		# for grp in [AutoRigHelpers.get()]
		# AutoRigHelpers.connect_attr(move_all_ctrl, 'scale_rig', c)
		self.move_all_off_ctrl = move_all_off_ctrl
		
	def construct_master(self):
		self.create_groups()
		self.create_move_all_ctrl(AutoRigHelpers.get(f'control_grp'))