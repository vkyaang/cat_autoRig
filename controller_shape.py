import maya.cmds as cmds
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

    print(f"Controller shapes and colors saved to: {json_path}")

import maya.cmds as cmds
import json
import os

def load_controller_shapes(json_path):
    """
    Load controller shapes and colors
   
    """
    if not os.path.exists(json_path):
        cmds.warning(f"⚠️ Shape file not found: {json_path}")
        return

    with open(json_path, "r") as f:
        data = json.load(f)

    missing_ctrls = []
    color_fail = []

    for ctrl, ctrl_info in data.items():
        if not cmds.objExists(ctrl):
            missing_ctrls.append(ctrl)
            continue

        # === Restore shapes ===
        saved_shapes = ctrl_info.get("shapes", {})
        current_shapes = cmds.listRelatives(ctrl, s=True, ni=True, f=True) or []

        for i, (saved_shape, shape_info) in enumerate(saved_shapes.items()):
            if not current_shapes:
                continue

            # Try to match shapes 1:1, otherwise fallback to first
            shape = current_shapes[i] if i < len(current_shapes) else current_shapes[-1]

            # Apply CV positions
            cvs = cmds.ls(f"{shape}.cv[*]", fl=True)
            cvs_data = shape_info.get("cv_positions", [])
            for j, cv in enumerate(cvs):
                if j < len(cvs_data):
                    cmds.xform(cv, ws=True, t=cvs_data[j])

            # Apply color (index-based)
            color_index = shape_info.get("color_index")
            if color_index is not None:
                try:
                    cmds.setAttr(f"{shape}.overrideEnabled", 1)
                    cmds.setAttr(f"{shape}.overrideRGBColors", 0)
                    cmds.setAttr(f"{shape}.overrideColor", int(color_index))
                except Exception:
                    color_fail.append(shape)

    if missing_ctrls:
        print(f"Skipped missing controllers: {missing_ctrls}")
    if color_fail:
        print(f"Color failed to apply on: {color_fail}")

    print(f"Controller shapes loaded successfully from: {json_path}")







