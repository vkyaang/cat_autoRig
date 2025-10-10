# main.py
import sys
import importlib

# Add path so Maya can find your module
pvr_path = r"D:\maya2023\Maya2023\scripts\cat_autoRig"
if pvr_path not in sys.path:
    sys.path.append(pvr_path)

# Import your autorig class
import auto_rig
importlib.reload(auto_rig)

# Run it
# group = auto_rig.InitRigSetUp()
# group.construct_setup()

rig = auto_rig.SpineNeckAutoRig()
rig.construct_rig()