# main.py
import sys
import importlib

pvr_path = r"D:\maya2023\Maya2023\scripts\cat_autoRig"
if pvr_path not in sys.path:
    sys.path.append(pvr_path)

import build_master_hierachy
importlib.reload(build_master_hierachy)
import neck_spine_auto_rig
importlib.reload(neck_spine_auto_rig)
import  limbs_auto_rig
importlib.reload(limbs_auto_rig)

# Run it
# group = auto_rig.InitRigSetUp()
# group.construct_setup()

# master
master = build_master_hierachy.Master()
master.construct_master()

# build neck and spine
neck_spine_rig = neck_spine_auto_rig.SpineNeckAutoRig(master)
neck_spine_rig.construct_rig()

# build limbs
limbs_rig = limbs_auto_rig.LimbsAutoRig(master, neck_spine_rig)
limbs_rig.construct_rig()

