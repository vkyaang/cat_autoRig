import maya.cmds as cmds
import maya.mel as mel
import json
import os


def save_controller_shapes(controls, json_path):
    """
    Save controller world transforms, CV positions, and color index to JSON.
    """
    folder = os.path.dirname(json_path)
    if not os.path.exists(folder):
        os.makedirs(folder)

    data = {}

    for ctrl in controls:
        if not cmds.objExists(ctrl):
            continue

        # === Transform data ===
        pos = cmds.xform(ctrl, q=True, ws=True, t=True)
        rot = cmds.xform(ctrl, q=True, ws=True, ro=True)
        scl = cmds.xform(ctrl, q=True, r=True, s=True)

        # === Shape data ===
        shapes = cmds.listRelatives(ctrl, s=True, ni=True, f=True) or []
        cvs_data = []
        color_index = None

        for shape in shapes:
            # save CVs
            cvs = cmds.ls(f"{shape}.cv[*]", fl=True)
            for cv in cvs:
                cvs_data.append(cmds.pointPosition(cv, w=True))

            # save indexed color
            if cmds.getAttr(f"{shape}.overrideEnabled"):
                color_index = cmds.getAttr(f"{shape}.overrideColor")

        data[ctrl] = {
            "translate": pos,
            "rotate": rot,
            "scale": scl,
            "cv_positions": cvs_data,
        }

        if color_index is not None:
            data[ctrl]["color_index"] = color_index

    # === Write JSON file ===
    with open(json_path, "w") as f:
        json.dump(data, f, indent=4)

    print(f"✅ Controller shapes and colors saved to: {json_path}")

def load_controller_shapes(json_path):
    """
    Load controller transforms, per-shape CVs, and color index from JSON.
    Fully supports multiple shapes per control.
    """
    if not os.path.exists(json_path):
        cmds.warning(f"⚠️ File not found: {json_path}")
        return

    with open(json_path, "r") as f:
        data = json.load(f)

    for ctrl, ctrl_info in data.items():
        if not cmds.objExists(ctrl):
            cmds.warning(f"⚠️ Skipping missing controller: {ctrl}")
            continue

        # --- Apply transforms ---
        cmds.xform(ctrl, ws=True, t=ctrl_info.get("translate", [0, 0, 0]))
        cmds.xform(ctrl, ws=True, ro=ctrl_info.get("rotate", [0, 0, 0]))
        cmds.xform(ctrl, r=True, s=ctrl_info.get("scale", [1, 1, 1]))

        # --- Apply each shape's stored data ---
        for shape, shape_info in ctrl_info.get("shapes", {}).items():
            if not cmds.objExists(shape):
                continue

            # Apply CVs
            cvs = cmds.ls(f"{shape}.cv[*]", fl=True)
            for i, cv in enumerate(cvs):
                if i < len(shape_info["cv_positions"]):
                    cmds.xform(cv, ws=True, t=shape_info["cv_positions"][i])

            # Apply color index
            color_index = shape_info.get("color_index")
            if color_index is not None:
                try:
                    cmds.setAttr(f"{shape}.overrideEnabled", 1)
                    cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                    cmds.setAttr(f"{shape}.overrideColor", int(color_index))
                    if cmds.attributeQuery("useOutlinerColor", node=shape, exists=True):
                        cmds.setAttr(f"{shape}.useOutlinerColor", 0)
                except Exception as e:
                    cmds.warning(f"⚠️ Could not color {shape}: {e}")

                # Force shading update
                cmds.setAttr(f"{shape}.overrideShading", 0)
                cmds.setAttr(f"{shape}.overrideShading", 1)

    # # --- Force viewport refresh ---
    # try:
    #     mel.eval("ogs -reset")
    #     mel.eval("displayColor -reset -active")
    # except:
    #     pass
    # cmds.refresh(force=True)

    print(f"✅ Controller shapes (multi-shape) + colors reloaded from: {json_path}")





