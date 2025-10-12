import maya.cmds as cmds
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


class LimbsAutoRig(object):
    def __init__(self):
        pass
    
    # ======================
    # Utility Functions
    # ======================
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
    
    def create_ik_controllers(self, side, region, ik_chain):
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
        
        foot_jnt = ik_chain[3]
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
        

    # ======================
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
