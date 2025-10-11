# main.py
import sys
import importlib

# Add path so Maya can find your module
pvr_path = r"D:\maya2023\Maya2023\scripts\cat_autoRig"
if pvr_path not in sys.path:
    sys.path.append(pvr_path)

# Import your autorig class
import neck_spine_auto_rig
importlib.reload(neck_spine_auto_rig)
import  limbs_auto_rig
importlib.reload(limbs_auto_rig)

# Run it
# group = auto_rig.InitRigSetUp()
# group.construct_setup()

# build neck and spine
# neck_spine_rig = neck_spine_auto_rig.SpineNeckAutoRig()
# neck_spine_rig.construct_rig()

# build limbs
limbs_rig = limbs_auto_rig.LimbsAutoRig()
limbs_rig.construct_rig()