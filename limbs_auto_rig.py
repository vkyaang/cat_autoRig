import maya.cmds as cmds
import maya.mel as mel
import importlib
import auto_rig_helpers
import curve_library

importlib.reload(auto_rig_helpers)
importlib.reload(curve_library)
from auto_rig_helpers import AutoRigHelpers
crv_lib = curve_library.RigCurveLibrary()

MOVE_ALL_CTRL = 'ctrl_c_moveAll_0002'
RIG_NODES_LOCAL_GRP = 'rigNodesLocal'
JOINTS_GRP = 'joints'

TEMP_JOINTS = {
    "ft": "temp_l_ft_upperLeg_0001",
    "bk": "temp_l_bk_upperLeg_0001",
    "scapula": "temp_l_scapula_0001"
}

PIVOT_TEMP_JOINTS = {
    "ft": [
        "temp_l_ft_heelPivot_0001",
        "temp_l_ft_footOutPivot_0001",
        "temp_l_ft_toeRvs_0001"
    ],
    "bk": [
        "temp_l_bk_heelPivot_0001",
        "temp_l_bk_footOutPivot_0001",
        "temp_l_bk_toeRvs_0001"
    ]
}


class LimbsAutoRig(object):
    def __init__(self):
        pass
    
    # ======================
    # Utility Functions
    # ======================
    def _get_leg_data(self, side, region):
        """
        Return a dictionary of all important IK/FK leg controls and groups
        for quick local variable access in other functions.
        Example:
            ctrls = self._get_leg_ctrls('l', 'ft')
            cmds.parentConstraint(ctrls['foot'], ctrls['toe'])
        """
        return {
            # IK Controls
            "foot": self.get(f"{side}_{region}_footIk_ctrl"),
            "heel": self.get(f"{side}_{region}_heelPivotIk_ctrl"),
            "toePivot": self.get(f"{side}_{region}_toePivotIk_ctrl"),
            "footOut": self.get(f"{side}_{region}_footOutPivotIk_ctrl"),
            "footIn": self.get(f"{side}_{region}_footInnPivotIk_ctrl"),
            "ball": self.get(f"{side}_{region}_ball_ctrl"),
            "toe": self.get(f"{side}_{region}_toe_ctrl"),
            "pv": self.get(f"{side}_{region}_kneePvIk_ctrl"),
            "upperleg": self.get(f"{side}_{region}_upperlegIk_ctrl"),
            "legRoll": self.get(f"{side}_{region}_legRoll_ctrl"),
            
            # IK Helper Groups
            "legRollAimGrp": self.get(f"{side}_{region}_leg_roll_aim_grp"),
            "legRollOffset": self.get(f"{side}_{region}_legRoll_offset"),
            "ankleRollGrp": self.get(f"{side}_{region}_ankle_roll_grp"),
            
            # Optional Joints (if stored)
            "legIkJnts": self.get(f"{side}_{region}_leg_ik_joints"),
            "legFkJnts": self.get(f"{side}_{region}_leg_fk_joints"),
            "legRollJnts": self.get(f"{side}_{region}_legRollAim_joints"),
            
            # group
            "leg_joints_grp": self.get(f"grp_{side}_{region}_legJnts")
        }
    
    
    def ensure_group(self, name, parent=None):
        """Create or return group"""
        if cmds.objExists(name):
            return name
        if parent and not cmds.objExists(parent):
            cmds.createNode("transform", n=parent)
        return cmds.createNode("transform", n=name, p=parent) if parent else cmds.createNode("transform", n=name)

    def _store(self, name, value):
        """Convenience for self variable assignment"""
        setattr(self, name, value)
        return value
    
    def _ordered_chain(self, root):
        """Return full joint chain (root → leaf)."""
        chain = cmds.listRelatives(root, ad=True, type='joint') or []
        chain.append(root)
        chain.reverse()
        return chain
    
    def _rename_chain_temp_to_jnt(self, chain):
        """Rename temp joints → jnt, _0002 → _0001."""
        out = []
        for j in chain:
            new_name = j.replace("temp", "jnt").replace("0002", "0001")
            out.append(cmds.rename(j, new_name))
        return out

    def _strip_index(self, name):
        parts = name.split("_")
        if parts and parts[-1].isdigit():
            parts = parts[:-1]
        return "_".join(parts)

    def _duplicate_chain_with_suffix(self, source_chain, suffix):
        """Duplicate chain and rename with _fk_/_ik_ while keeping anatomy terms"""
        if not source_chain:
            cmds.warning("Empty source chain to duplicate.")
            return []

        dup_root = cmds.duplicate(source_chain[0], rc=True)[0]
        all_joints = cmds.listRelatives(dup_root, ad=True, type='joint') or []
        all_joints.append(dup_root)
        all_joints.reverse()  # root → leaf

        new_chain = []
        for jnt in all_joints:
            base = self._strip_index(jnt)
            new_name = f"{base}_{suffix.lower()}_0001"
            try:
                new_chain.append(cmds.rename(jnt, new_name))
            except:
                new_chain.append(jnt)
        return new_chain
    
    def get(self, name, default=None, warn=True):
        """Safely retrieve a stored self variable by name."""
        if hasattr(self, name):
            return getattr(self, name)
        else:
            if warn:
                cmds.warning(f"[Rig] Missing attribute: self.{name}")
            return default
    
    # ======================
    # Base Joints
    # ======================
    def create_base_joints(self, region):
        """Duplicate temp chain → rename cleanly → mirror → store"""
        temp = TEMP_JOINTS.get(region)
        if not cmds.objExists(temp):
            cmds.warning(f"Missing template joint: {temp}")
            return

        new_root = cmds.duplicate(temp, rc=True)[0]
        all_joints = cmds.listRelatives(new_root, ad=True, type='joint') or []
        all_joints.append(new_root)
        all_joints.reverse()

        new_chain = []
        for jnt in all_joints:
            name = jnt.replace("temp", "jnt").replace("0002", "0001")
            new_chain.append(cmds.rename(jnt, name))

        mirrored_chain = cmds.mirrorJoint(
            new_chain[0],
            mirrorYZ=True,
            mirrorBehavior=True,
            searchReplace=('_l_', '_r_')
        )

        self._store(f"l_{region}_leg_joints", new_chain)
        self._store(f"r_{region}_leg_joints", mirrored_chain)
    
    def create_pivot_joints(self, region):
        """Create and store pivot joints (heelPivot, footOutPivot, toeRvs) for both sides."""
        pivots = PIVOT_TEMP_JOINTS.get(region, [])
    
        piv_root = self.ensure_group("grp_legPivots_0001", JOINTS_GRP)
        
        # Left and right pivot groups under region root
        side_grps = {
            "l": self.ensure_group(f"grp_l_{region}_legPivots_0001", piv_root),
            "r": self.ensure_group(f"grp_r_{region}_legPivots_0001", piv_root)
        }
        
        for src in pivots:
           
            # duplicate L source and rename
            l_root = cmds.duplicate(src, rc=True)[0]
            
            l_chain = self._rename_chain_temp_to_jnt(self._ordered_chain(l_root))
            # mirror to right side
            r_chain = cmds.mirrorJoint(
                l_chain[0],
                mirrorYZ=True,
                mirrorBehavior=True,
                searchReplace=("_l_", "_r_")
            )
            
            # anatomy name (e.g. heelPivot / footOutPivot / toeRvs)
            parts = l_chain[0].split("_")
            anatomy = "_".join(parts[3:-1]) if len(parts) > 4 else parts[3]
            
            # store automatically by side name
            for side, chain in zip(["l", "r"], [l_chain, r_chain]):
                self._store(f"{side}_{region}_{anatomy}_root", chain)
                self._store(f"{side}_{region}_{anatomy}_chain", chain)
                self._store(f"{side}_{region}_{anatomy}_jnt", chain[0])
            
    
    # ======================
    # FK / IK Setup
    # ======================
    def create_fk_ik_chains(self, side, region):
        """Duplicate and rename for FK/IK"""
        base_chain = getattr(self, f"{side}_{region}_leg_joints", [])
        if not base_chain:
            cmds.warning(f"No base chain found for {side}_{region}.")
            return

        fk_chain = self._duplicate_chain_with_suffix(base_chain, "fk")
        ik_chain = self._duplicate_chain_with_suffix(base_chain, "ik")

        self._store(f"{side}_{region}_leg_fk_joints", fk_chain)
        self._store(f"{side}_{region}_leg_ik_joints", ik_chain)

        # organize joints
        leg_root = self.ensure_group("grp_legJnts_0001", JOINTS_GRP)
        rig_grp = self.ensure_group(f"grp_{side}_{region}_legJnts_0001", leg_root)
        for root in [base_chain[0], fk_chain[0], ik_chain[0]]:
            cmds.parent(root, rig_grp)
        
        self._store(f"grp_{side}_{region}_legJnts", rig_grp)
           

    def create_ctrl_groups(self, side, region):
        """Build controller group hierarchy for FK/IK legs"""
        ctrl_root = self.ensure_group("grp_legCtrls_0001", MOVE_ALL_CTRL)
        ctrl_grp = self.ensure_group(f"grp_{side}_{region}_legCtrls_0001", ctrl_root)
        fk_grp = self.ensure_group(f"grp_{side}_{region}_legFkCtrls_0001", ctrl_grp)
        ik_grp = self.ensure_group(f"grp_{side}_{region}_legIkCtrls_0001", ctrl_grp)

        self._store(f"{side}_{region}_leg_ctrl_grp", ctrl_grp)
        self._store(f"{side}_{region}_leg_fk_grp", fk_grp)
        self._store(f"{side}_{region}_leg_ik_grp", ik_grp)

    def build_fk_setup(self, side, region):
        """Create FK controls"""
        fk_chain = getattr(self, f"{side}_{region}_leg_fk_joints", [])
        if not fk_chain:
            return

        fk_grp = getattr(self, f"{side}_{region}_leg_fk_grp", None)
        prev_ctrl = None
        for jnt in fk_chain[:-1]:
            ctrl_name = jnt.replace("jnt", "ctrl")
            fk_ctrl = crv_lib.create_cube_curve(ctrl_name)
            cmds.matchTransform(fk_ctrl, jnt)
            AutoRigHelpers.create_control_hierarchy(fk_ctrl, 2)

            zero_grp = fk_ctrl.replace("ctrl", "zero")
            if prev_ctrl is None:
                cmds.parent(zero_grp, fk_grp)
            else:
                cmds.parent(zero_grp, prev_ctrl)

            cmds.parentConstraint(fk_ctrl, jnt, mo=False)
            prev_ctrl = fk_ctrl

    def build_ik_setup(self, side, region):
        """Create a simple IK placeholder locator"""
        ik_chain = getattr(self, f"{side}_{region}_leg_ik_joints", [])

        # create ik controllers
        self.create_ik_controllers(side, region, ik_chain)
        self.create_ikHnd(side, region, ik_chain)
        self.create_ik_stretch(side, region, ik_chain)
        
    def create_ikHnd(self, side, region, ik_chain):
        ball_jnt = ik_chain[3]
        ankle_jnt = ik_chain[2]
        knee_jnt = ik_chain[1]
        upperleg_jnt = ik_chain[0]
        toe_jnt = ik_chain[-2]
        toe_end_jnt = ik_chain[-1]
        
        # foot_ctrl = self.get(f"{side}_{region}_footIk_ctrl")
        ctrls = self._get_leg_data(side, region)
        foot_ctrl  = ctrls['foot']
        ball_ctrl = self.get(f"{side}_{region}_ball_ctrl")
        toe_ctrl = self.get(f"{side}_{region}_toe_ctrl")
        pv_ctrl = self.get(f"{side}_{region}_kneePvIk_ctrl")
        leg_roll_ctrl = self.get(f"{side}_{region}_legRoll_ctrl")
        upperleg_ctrl = self.get(f"{side}_{region}_upperlegIk_ctrl")
        leg_roll_aim_grp = self.get(f"{side}_{region}_leg_roll_aim_grp")
        ankle_roll_grp = self.get(f"{side}_{region}_ankle_roll_grp")
        
        # leg ikhnd
        leg_ikHnd = cmds.ikHandle(sj=upperleg_jnt,
                                  ee=ankle_jnt,
                                  sol='ikRPsolver',
                                  srp=True,
                                  n=f'ikHnd_{side}_{region}_leg_0001')[0]
        cmds.parent(leg_ikHnd, leg_roll_aim_grp)
        AutoRigHelpers.set_attr(leg_ikHnd, 'visibility', False)
        
        # add pvik
        cmds.poleVectorConstraint(pv_ctrl, leg_ikHnd)
        
        # ankle ikHnd
        ankle_ikHnd = cmds.ikHandle(sj=ankle_jnt,
                                  ee=ball_jnt,
                                  sol='ikSCsolver',
                                  srp=True,
                                  n=f'ikHnd_{side}_{region}_ankle_0001')[0]
        cmds.parent(ankle_ikHnd, ankle_roll_grp)
        AutoRigHelpers.set_attr(ankle_ikHnd, 'visibility', False)
        
        # ball ikHnd
        ball_ikHnd = cmds.ikHandle(sj=ball_jnt,
                                    ee=toe_jnt,
                                    sol='ikSCsolver',
                                    srp=True,
                                    n=f'ikHnd_{side}_{region}_ball_0001')[0]
        cmds.parent(ball_ikHnd, ball_ctrl)
        AutoRigHelpers.set_attr(ball_ikHnd, 'visibility', False)
        
        # toe ikHnd
        toe_ikHnd = cmds.ikHandle(sj=toe_jnt,
                                   ee=toe_end_jnt,
                                   sol='ikSCsolver',
                                   srp=True,
                                   n=f'ikHnd_{side}_{region}_toe_0001')[0]
        cmds.parent(toe_ikHnd, toe_ctrl)
        AutoRigHelpers.set_attr(toe_ikHnd, 'visibility', False)
        
        # create leg roll aim
        self.create_leg_roll_aim_jnt(side, region, ik_chain)
        
    
    def create_leg_roll_aim_jnt(self, side, region, ik_chain):
        """
        Create a temporary leg roll aim joint chain (upperleg → knee → ball)
        with correct orientation (X primary, Y secondary, Y-up).
        """
        # Define source joints
        upperleg_src = ik_chain[0]
        ball_src = ik_chain[3]  # typically foot_jnt or ball_jnt depending on your chain
        
        ctrls = self._get_leg_data(side, region)
        foot_ctrl = ctrls['foot']
        leg_roll_ctrl = ctrls['legRoll']
        leg_roll_aim_grp = ctrls['legRollAimGrp']
        pv_ctrl = ctrls['pv']
        leg_joint_grp = ctrls['leg_joints_grp']
        leg_roll_offset = ctrls['legRollOffset']
        
        # Create joints
        upperleg_jnt = cmds.createNode('joint', n=f'jnt_{side}_{region}_legRollAimTip_0001')
        ball_jnt = cmds.createNode('joint', n=f'jnt_{side}_{region}_legRollAim_0001')
        
        # Match transforms
        cmds.matchTransform(upperleg_jnt, upperleg_src, pos=True)
        cmds.matchTransform(ball_jnt, ball_src, pos=True)
        
        # Parent hierarchy
        cmds.parent(upperleg_jnt, ball_jnt)
        cmds.parent(ball_jnt, leg_joint_grp)
        
        # Orient the chain (X primary, Y secondary, Y up)
        cmds.joint(
            ball_jnt,
            e=True,
            oj='xyz',  # orient joints in X (primary) → Y (secondary)
            sao='ydown',  # secondary axis orientation = Y-up
            ch=True,  # orient children
            zso=True  # zero scale orientation
        )
        
        # create ikHnd
        leg_roll_ikHnd = cmds.ikHandle(sj=ball_jnt,
                                  ee=upperleg_jnt,
                                  sol='ikRPsolver',
                                  srp=True,
                                  n=f'ikHnd_{side}_{region}_legRollAim_0001')[0]
        AutoRigHelpers.set_attr(leg_roll_ikHnd, 'visibility', False)
        # pole vector
        cmds.poleVectorConstraint(pv_ctrl, leg_roll_ikHnd)
        
        ikHnd_zero = cmds.createNode('transform', n=f'zero_ikHnd_{side}_{region}_legRollAim_0001')
        cmds.matchTransform(ikHnd_zero, leg_roll_ikHnd)
        cmds.parent(leg_roll_ikHnd, ikHnd_zero)
        cmds.parent(ikHnd_zero, leg_joint_grp)
        cmds.pointConstraint(upperleg_src, ikHnd_zero, mo=True)
        # Freeze joint orientation (optional)
        for jnt in [upperleg_jnt, ball_jnt]:
            cmds.makeIdentity(jnt, apply=True, t=False, r=True, s=False, n=False)
        
        cmds.pointConstraint(foot_ctrl, ball_jnt, mo=True)
        
        leg_roll_cons = cmds.parentConstraint(ball_jnt, foot_ctrl, leg_roll_offset, mo=True)[0]
        AutoRigHelpers.set_attr(leg_roll_cons, 'interpType', 2)
        
        # create reverse node
        rvs_roll = cmds.createNode('reverse', n=f'rvs_{side}_{region}_legRoll_0001')
        AutoRigHelpers.connect_attr(leg_roll_ctrl, 'roll_active', rvs_roll, 'inputX')
        AutoRigHelpers.connect_attr(leg_roll_ctrl, 'roll_active', leg_roll_cons, f'{ball_jnt}W0')
        AutoRigHelpers.connect_attr(rvs_roll, 'outputX', leg_roll_cons, f'{foot_ctrl}W1')
        cmds.orientConstraint(leg_roll_ctrl, leg_roll_aim_grp, mo=True)
        
        # Store for easy access later
        self._store(f"{side}_{region}_legRollAim_joints", [ball_jnt, upperleg_jnt])
        
    def create_ik_controllers(self, side, region, ik_chain):
        foot_jnt = ik_chain[3]
        ankle_jnt = ik_chain[2]
        knee_jnt = ik_chain[1]
        upperleg_jnt = ik_chain[0]
        
        foot_ctrl_name = f'ctrl_{side}_{region}_footIk_0001'
        foot_ctrl = cmds.createNode('joint', n=foot_ctrl_name)
        AutoRigHelpers.create_control_hierarchy(foot_ctrl)
        zero_grp, offset_grp, *_ = AutoRigHelpers.get_parent_grp(foot_ctrl)
        foot_ctrl_temp = crv_lib.circle(name=f'crv_{side}_{region}_footIk_0001')
        foot_ctrl_shape = cmds.listRelatives(foot_ctrl_temp, shapes=True, fullPath=True)
        cmds.parent(zero_grp, getattr(self, f"{side}_{region}_leg_ik_grp"))
        
        # parent shape to control joint
        cmds.parent(foot_ctrl_shape, foot_ctrl, relative=True, shape=True)
        cmds.delete(foot_ctrl_temp)
        cmds.delete(foot_ctrl, ch=True)
        AutoRigHelpers.set_attr(foot_ctrl, 'drawStyle', 2)
        # add attrs
        AutoRigHelpers.lock_hide_attr(foot_ctrl, ['radi'])
        AutoRigHelpers.add_attr(foot_ctrl, 'auto_stretch', 'float', 0, 0, 1)
        AutoRigHelpers.add_attr(foot_ctrl, 'upper_leg_stretch', 'float', 0)
        AutoRigHelpers.add_attr(foot_ctrl, 'knee_stretch', 'float', 0)
        AutoRigHelpers.add_attr(foot_ctrl, 'ankle_stretch', 'float', 0)
        AutoRigHelpers.add_attr(foot_ctrl, 'follow', 'enum', enum_names=['World','Cog','UpperLeg'])
        AutoRigHelpers.add_attr(foot_ctrl, 'foot_bank', 'float', 0, 0, 1)
        AutoRigHelpers.add_attr(foot_ctrl, 'heel_roll', 'float', 0, 0, 1)
        
        # create temp locators
        loc_name = f"loc_{side}_{region}_foot_up_0001"
        loc = cmds.spaceLocator(n=loc_name)[0]
        cmds.matchTransform(loc, foot_jnt, pos=True, rot=False)
        cmds.matchTransform(zero_grp, foot_jnt, pos=True, rot=False)
        # move loc up
        AutoRigHelpers.set_attr(loc, 'translateY', AutoRigHelpers.get_attr(loc, 'translateY') + 5)
        # aim constraint
        aim_cons = cmds.aimConstraint(loc,
                                      zero_grp,
                                      aimVector=(0,1,0),
                                      upVector=(1,0,0),
                                      wut='object',
                                      wuo=ik_chain[-1],
                                      mo=False)[0]
        cmds.delete(aim_cons)
        
        # create ik hierachy
        heel_ctrl = crv_lib.create_diamond_sphere(f'ctrl_{side}_{region}_heelPivotIk_0001')
        cmds.matchTransform(heel_ctrl, getattr(self, f"{side}_{region}_heelPivot_root")[0])
        AutoRigHelpers.create_control_hierarchy(heel_ctrl, 2)
        _, _, heel_zero, heel_offset = AutoRigHelpers.get_parent_grp(heel_ctrl)
        cmds.parent(heel_zero, foot_ctrl)

        toe_pivot_ctrl = crv_lib.create_diamond_sphere(f'ctrl_{side}_{region}_toePivotIk_0001')
        cmds.matchTransform(toe_pivot_ctrl, getattr(self, f"{side}_{region}_heelPivot_root")[1])
        AutoRigHelpers.create_control_hierarchy(toe_pivot_ctrl, 2)
        _, _, toe_pivot_zero, toe_pivot_offset= AutoRigHelpers.get_parent_grp(toe_pivot_ctrl)
        cmds.parent(toe_pivot_zero, heel_ctrl)

        foot_out_ctrl = crv_lib.create_diamond_sphere(f'ctrl_{side}_{region}_footOutPivotIk_0001')
        cmds.matchTransform(foot_out_ctrl, getattr(self, f"{side}_{region}_footOutPivot_root")[0])
        AutoRigHelpers.create_control_hierarchy(foot_out_ctrl, 2)
        _, _, foot_out_zero, foot_out_offset = AutoRigHelpers.get_parent_grp(foot_out_ctrl)
        cmds.parent(foot_out_zero, toe_pivot_ctrl)
        
        foot_in_ctrl = crv_lib.create_diamond_sphere(f'ctrl_{side}_{region}_footInnPivotIk_0001')
        cmds.matchTransform(foot_in_ctrl, getattr(self, f"{side}_{region}_footOutPivot_root")[1])
        AutoRigHelpers.create_control_hierarchy(foot_in_ctrl, 2)
        _, _, foot_in_zero, foot_in_offset = AutoRigHelpers.get_parent_grp(foot_in_ctrl)
        cmds.parent(foot_in_zero, foot_out_ctrl)
        
        # create ball and toe ctrl
        ball_ctrl = crv_lib.create_closed_arc(name=f'ctrl_{side}_{region}_ball_0001')
        cmds.matchTransform(ball_ctrl, getattr(self, f"{side}_{region}_toeRvs_root")[0])
        AutoRigHelpers.create_control_hierarchy(ball_ctrl, 2)
        _, _, ball_zero, ball_offset = AutoRigHelpers.get_parent_grp(ball_ctrl)
        cmds.parent(ball_zero, foot_in_ctrl)
        
        toe_ctrl = crv_lib.create_closed_arc(name=f'ctrl_{side}_{region}_toe_0001')
        cmds.matchTransform(toe_ctrl, getattr(self, f"{side}_{region}_toeRvs_root")[1])
        AutoRigHelpers.create_control_hierarchy(toe_ctrl, 2)
        _, _, toe_zero, toe_offset = AutoRigHelpers.get_parent_grp(toe_ctrl)
        cmds.parent(toe_zero, foot_in_ctrl)
        
        # create leg roll aim
        leg_roll_aim_grp = cmds.createNode('transform', n=f'driven_{side}_{region}_legRollAim_0001')
        cmds.matchTransform(leg_roll_aim_grp, foot_ctrl)
        AutoRigHelpers.create_control_hierarchy(leg_roll_aim_grp, 2)
        _, _, leg_roll_aim_zero, leg_roll_aim_offset = AutoRigHelpers.get_parent_grp(leg_roll_aim_grp)
        cmds.parent(leg_roll_aim_zero, ball_ctrl)

        leg_roll_ctrl = crv_lib.create_cube_curve(f'ctrl_{side}_{region}_legRoll_0001')
        cmds.matchTransform(leg_roll_ctrl, foot_ctrl)
        AutoRigHelpers.create_control_hierarchy(leg_roll_ctrl, 2)
        _, _, leg_roll_zero, leg_roll_offset = AutoRigHelpers.get_parent_grp(leg_roll_ctrl)
        cmds.parent(leg_roll_zero, getattr(self, f"{side}_{region}_leg_ik_grp"))
        cmds.orientConstraint(leg_roll_ctrl, leg_roll_aim_grp, mo=True)
        
        # add leg roll ctrl attr
        AutoRigHelpers.lock_hide_attr(leg_roll_ctrl, ['tx','ty','tz'])
        AutoRigHelpers.add_attr(leg_roll_ctrl, 'roll_active', 'float', 0, 0, 1)
        
        # create ankle roll
        ankle_roll_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_ankleRoll_0001')
        cmds.matchTransform(ankle_roll_grp, ankle_jnt, pos=True, rot=False)
        cmds.parent(ankle_roll_grp, leg_roll_aim_grp)
        
        # create pvik ctrl
        pv_ik_ctrl = crv_lib.create_cross(f'ctrl_{side}_{region}_kneePvIk_0001')
        cmds.matchTransform(pv_ik_ctrl, knee_jnt)
        AutoRigHelpers.create_control_hierarchy(pv_ik_ctrl, 2)
        _, _, pv_ik_zero, pv_ik_offset = AutoRigHelpers.get_parent_grp(pv_ik_ctrl)
        cmds.parent(pv_ik_zero, knee_jnt)
        if region == 'ft' and side == 'r':
            AutoRigHelpers.set_attr(pv_ik_zero, 'translateY', 5)
        elif region == 'ft' and side == 'l':
            AutoRigHelpers.set_attr(pv_ik_zero, 'translateY', -5)
        elif region == 'bk' and side == 'r':
            AutoRigHelpers.set_attr(pv_ik_zero, 'translateY', -5)
        elif region == 'bk' and side == 'l':
            AutoRigHelpers.set_attr(pv_ik_zero, 'translateY', 5)
            
        cmds.parent(pv_ik_zero, getattr(self, f"{side}_{region}_leg_ik_grp"))
        AutoRigHelpers.set_attr(pv_ik_zero, 'rotateX', 0)
        AutoRigHelpers.set_attr(pv_ik_zero, 'rotateY', 0)
        AutoRigHelpers.set_attr(pv_ik_zero, 'rotateZ', 0)
        
        # create annotation
        anno_loc = cmds.spaceLocator(n=f"annotationLoc_{side}_{region}_kneePvIk_0001")[0]
        AutoRigHelpers.set_attr(cmds.listRelatives(anno_loc, shapes=True, fullPath=False)[0], 'visibility', False)
        AutoRigHelpers.set_attr(anno_loc, 'overrideEnabled', True)
        AutoRigHelpers.set_attr(anno_loc, 'overrideDisplayType', 2)
        cmds.matchTransform(anno_loc, pv_ik_ctrl)
        cmds.parent(anno_loc, pv_ik_ctrl)
        # Create annotation (returns shape node inside transform)
        anno_shape = cmds.annotate(pv_ik_ctrl, tx=' ')
        AutoRigHelpers.set_attr(anno_shape, 'overrideEnabled', True)
        AutoRigHelpers.set_attr(anno_shape, 'overrideDisplayType', 2)
        anno_trans = cmds.listRelatives(anno_shape, parent=True, fullPath=False)[0]
        # Rename and parent properly
        anno_trans = cmds.rename(anno_trans, f"annotation_{side}_{region}_kneePvIk_0001")
        cmds.parent(anno_trans, anno_loc)
        # Constrain locator to knee joint (drives annotation line)
        cmds.parentConstraint(knee_jnt, anno_trans, mo=False)
        
        # create upperleg ik ctrl
        upperleg_ctrl = crv_lib.create_closed_arc(f'ctrl_{side}_{region}_upperleg_ik_0001')
        cmds.matchTransform(upperleg_ctrl, upperleg_jnt)
        AutoRigHelpers.create_control_hierarchy(upperleg_ctrl, 2)
        _, _, upperleg_zero, upperleg_offset = AutoRigHelpers.get_parent_grp(upperleg_ctrl)
        cmds.parent(upperleg_zero, getattr(self, f"{side}_{region}_leg_ik_grp"))
        cmds.parentConstraint(upperleg_ctrl, upperleg_jnt)
    
        self._store(f"{side}_{region}_footIk_ctrl", foot_ctrl)
        self._store(f"{side}_{region}_heelPivotIk_ctrl", heel_ctrl)
        self._store(f"{side}_{region}_toePivotIk_ctrl", toe_pivot_ctrl)
        self._store(f"{side}_{region}_footOutPivotIk_ctrl", foot_out_ctrl)
        self._store(f"{side}_{region}_footInnPivotIk_ctrl", foot_in_ctrl)
        self._store(f"{side}_{region}_ball_ctrl", ball_ctrl)
        self._store(f"{side}_{region}_toe_ctrl", toe_ctrl)
        self._store(f"{side}_{region}_legRoll_ctrl", leg_roll_ctrl)
        self._store(f"{side}_{region}_legRollAim_grp", leg_roll_aim_grp)
        self._store(f"{side}_{region}_ankleRoll_grp", ankle_roll_grp)
        self._store(f"{side}_{region}_kneePvIk_ctrl", pv_ik_ctrl)
        self._store(f"{side}_{region}_upperlegIk_ctrl", upperleg_ctrl)
        self._store(f"{side}_{region}_leg_roll_aim_grp", leg_roll_aim_grp)
        self._store(f"{side}_{region}_ankle_roll_grp", ankle_roll_grp)
        
        self._store(f"{side}_{region}_legRoll_offset", leg_roll_offset)
        
    def create_ik_stretch(self, side, region, ik_chain):
        """
        create ik stretch setup
        """
        ball_jnt = ik_chain[3]
        ankle_jnt = ik_chain[2]
        knee_jnt = ik_chain[1]
        upperleg_jnt = ik_chain[0]
        
        ctrls = self._get_leg_data(side, region)
        foot_ctrl = ctrls['foot']
        upperleg_ctrl = ctrls['upperleg']
        jnt_grp = ctrls['leg_joints_grp']
        
        # create locators
        data_grp = cmds.createNode('transform', n=f'grp_{side}_{region}_strData_0001', p=jnt_grp)
        start_loc = cmds.spaceLocator(n=f'loc_{side}_{region}_leg_startPos_0001')[0]
        end_loc = cmds.spaceLocator(n=f'loc_{side}_{region}_leg_endPos_0001')[0]
        cmds.parentConstraint(upperleg_ctrl, start_loc, mo=False)
        cmds.parentConstraint(foot_ctrl, end_loc, mo=False)
        cmds.parent(start_loc, data_grp)
        cmds.parent(end_loc, data_grp)
        
        # create distance between
        dis_btw = cmds.createNode('distanceBetween', n=f'disBtw_{side}_{region}_leg_0001')
        AutoRigHelpers.connect_attr(start_loc, 'translate', dis_btw, 'point1')
        AutoRigHelpers.connect_attr(end_loc, 'translate', dis_btw, 'point2')
        # get distance
        distance = AutoRigHelpers.get_attr(dis_btw, 'distance')
        # create div norm
        div_norm = cmds.createNode('multiplyDivide', n=f'div_{side}_{region}_leg_strNorm_0001')
        AutoRigHelpers.set_attr(div_norm, 'operation', 2)
        AutoRigHelpers.connect_attr(dis_btw, 'distance', div_norm, 'input1X')
        AutoRigHelpers.set_attr(div_norm, 'input2X', distance)
        # create mult translate node
        mult_trans = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_leg_str_0001')
        # get joints translate
        knee_tx = AutoRigHelpers.get_attr(knee_jnt, 'translateX')
        ankle_tx = AutoRigHelpers.get_attr(ankle_jnt, 'translateX')
        # set translate value
        AutoRigHelpers.set_attr(mult_trans, 'input1X', knee_tx)
        AutoRigHelpers.set_attr(mult_trans, 'input1Y', ankle_tx)
        # connect div norm
        AutoRigHelpers.connect_attr(div_norm, 'outputX', mult_trans, 'input2X')
        AutoRigHelpers.connect_attr(div_norm, 'outputX', mult_trans, 'input2Y')
        
        # create condition
        cond = cmds.createNode('condition', n=f'cond_{side}_{region}_leg_str_0001')
        AutoRigHelpers.set_attr(cond, 'operation', 2)
        AutoRigHelpers.connect_attr(mult_trans, 'outputX', cond, 'colorIfTrueR')
        AutoRigHelpers.connect_attr(mult_trans, 'outputY', cond, 'colorIfTrueG')
        AutoRigHelpers.connect_attr(mult_trans, 'input1X', cond, 'colorIfFalseR')
        AutoRigHelpers.connect_attr(mult_trans, 'input1Y', cond, 'colorIfFalseG')
        AutoRigHelpers.connect_attr(dis_btw, 'distance', cond, 'firstTerm')
        AutoRigHelpers.set_attr(cond, 'secondTerm', distance)
        
        # create pair blend
        pair_blend = cmds.createNode('pairBlend', n=f'pairBlend_{side}_{region}_leg_str_0001')
        AutoRigHelpers.connect_attr(foot_ctrl, 'auto_stretch', pair_blend, 'weight')
        AutoRigHelpers.connect_attr(mult_trans, 'input1', pair_blend, 'inTranslate1')
        AutoRigHelpers.connect_attr(cond, 'outColor', pair_blend, 'inTranslate2')
        
        # connect output to tx
        AutoRigHelpers.connect_attr(pair_blend, 'outTranslateX', knee_jnt, 'translateX')
        AutoRigHelpers.connect_attr(pair_blend, 'outTranslateY', ankle_jnt, 'translateX')
        
        # create individual stretch mult
        ind_mult = cmds.createNode('multiplyDivide', n=f'mult_{side}_{region}_leg_indvStr_0001')
        AutoRigHelpers.set_attr(ind_mult, 'operation', 2)
        AutoRigHelpers.connect_attr(foot_ctrl, 'upper_leg_stretch', ind_mult, 'input1X')
        AutoRigHelpers.connect_attr(foot_ctrl, 'knee_stretch', ind_mult, 'input1Y')
        AutoRigHelpers.connect_attr(foot_ctrl, 'ankle_stretch', ind_mult, 'input1Z')
        AutoRigHelpers.set_attr(ind_mult, 'input2X', 10)
        AutoRigHelpers.set_attr(ind_mult, 'input2Y', 10)
        AutoRigHelpers.set_attr(ind_mult, 'input2Z', 10)
        # create individual stretch plus minus avg
        ind_pma = cmds.createNode('plusMinusAverage', n=f'pma_{side}_{region}_leg_indvStr_0001')
        AutoRigHelpers.set_attr(ind_pma, 'input3D[0].input3Dx', 1)
        AutoRigHelpers.set_attr(ind_pma, 'input3D[0].input3Dy', 1)
        AutoRigHelpers.set_attr(ind_pma, 'input3D[0].input3Dz', 1)
        AutoRigHelpers.connect_attr(ind_mult, 'outputX', ind_pma, 'input3D[1].input3Dx')
        AutoRigHelpers.connect_attr(ind_mult, 'outputY', ind_pma, 'input3D[1].input3Dy')
        AutoRigHelpers.connect_attr(ind_mult, 'outputZ', ind_pma, 'input3D[1].input3Dz')
        # connect to joint scale x
        AutoRigHelpers.connect_attr(ind_pma, 'output3Dx', upperleg_jnt, 'scaleX')
        AutoRigHelpers.connect_attr(ind_pma, 'output3Dy', knee_jnt, 'scaleX')
        AutoRigHelpers.connect_attr(ind_pma, 'output3Dz', ankle_jnt, 'scaleX')
        
    
    # ======================fq
    # Scapula
    # ======================
    def create_scapula_joint(self):
        """Duplicate scapula joints left/right"""
        temp_joint = TEMP_JOINTS["scapula"]
        if not cmds.objExists(temp_joint):
            cmds.warning(f"Missing scapula template: {temp_joint}")
            return

        root = self.ensure_group("grp_scapulaJnts_0001", JOINTS_GRP)
        l_grp = self.ensure_group("grp_l_scapulaJnts_0001", root)
        r_grp = self.ensure_group("grp_r_scapulaJnts_0001", root)

        l_chain_root = cmds.duplicate(temp_joint, rc=True)[0]
        l_chain = [l_chain_root] + (cmds.listRelatives(l_chain_root, ad=True, type='joint') or [])
        l_chain = [cmds.rename(j, j.replace("temp", "jnt").replace("0002", "0001")) for j in l_chain]
        cmds.parent(l_chain[0], l_grp)

        print(l_chain)
        r_chain = cmds.mirrorJoint(l_chain[0], mirrorYZ=True, mirrorBehavior=True, searchReplace=("_l_", "_r_"))
        cmds.parent(r_chain[0], r_grp)

        self._store("l_scapula_joints", l_chain)
        self._store("r_scapula_joints", r_chain)

    def create_scapula_ctrls(self):
        """Create scapula controls for L/R"""
        ctrl_root = self.ensure_group("grp_scapulaCtrls_0001", MOVE_ALL_CTRL)

        for side in ["l", "r"]:
            side_grp = self.ensure_group(f"grp_{side}_scapulaCtrls_0001", ctrl_root)
            chain = getattr(self, f"{side}_scapula_joints", [])
            if not chain:
                continue

            jnt = chain[0]
            ctrl_name = f"ctrl_{side}_scapula_0001"
            ctrl = crv_lib.create_prism_line(ctrl_name)
            cmds.matchTransform(ctrl, jnt)
            AutoRigHelpers.create_control_hierarchy(ctrl, 2)
            zero_grp = ctrl.replace("ctrl", "zero")
            cmds.parent(zero_grp, side_grp)
            cmds.parentConstraint(ctrl, jnt, mo=False)

            if side == "r":
                left_ctrl = ctrl.replace("_r_", "_l_")
                if cmds.objExists(left_ctrl):
                    AutoRigHelpers.mirror_curve_shape(left_ctrl, ctrl)

            self._store(f"{side}_scapula_ctrl", ctrl)

    def create_scapula_orient(self):
        """Create scapula orientation helper locators"""
        root = self.ensure_group("grp_scapula_orient_0001", RIG_NODES_LOCAL_GRP)
        for side in ["l", "r"]:
            side_grp = self.ensure_group(f"grp_{side}_scapulaOrient_0001", root)
            offset_grp = self.ensure_group(f"offset_{side}_scapulaOrient_0001", side_grp)

            # loc_local = self.ensure_group(f"loc_{side}_scapula_local_0001", offset_grp)
            loc_local = cmds.spaceLocator(n=f"loc_{side}_scapula_local_0001")
            cmds.parent(loc_local, offset_grp)
            loc_world = cmds.spaceLocator(n=f"loc_{side}_scapula_world_0001")
            cmds.parent(loc_world, offset_grp)

            chain = getattr(self, f"{side}_scapula_joints", [])
            if chain:
                cmds.matchTransform(side_grp, chain[0])

            self._store(f"{side}_scapula_local_loc", loc_local)
            self._store(f"{side}_scapula_world_loc", loc_world)
            
  
  
    # ======================
    # Main Rig Constructor
    # ======================
    def construct_rig(self):
        """Build the entire rig once"""
        # base joints
        for region in ["ft", "bk"]:
            self.create_base_joints(region)
            self.create_pivot_joints(region)

        # scapula
        self.create_scapula_joint()
        self.create_scapula_ctrls()
        self.create_scapula_orient()

        # legs
        for side in ["l", "r"]:
            for region in ["ft", "bk"]:
                self.create_fk_ik_chains(side, region)
                self.create_ctrl_groups(side, region)
                self.build_fk_setup(side, region)
                self.build_ik_setup(side, region)

        print("✅ Rig construction completed successfully!")
        AutoRigHelpers.mirror_all_right_shapes()
        AutoRigHelpers.lock_and_hide_ctrls()