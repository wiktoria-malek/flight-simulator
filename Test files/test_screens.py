from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack
import numpy as np

interface=InterfaceATF2_Ext_RFTrack()
screens=interface.get_screens()
interface.push(["ZH100RX"], [1])
screens_after=interface.get_screens()
print(screens["x"]-screens_after["x"])
print("screens:", screens["names"])
print("x:", screens["x"])
print("y:", screens["y"])
print("sigx:", screens["sigx"])
print("sigy:", screens["sigy"])
print("sum:", screens["sum"])

scr0 = interface.get_screens()
interface.change_energy()
scr1 = interface.get_screens()
print(scr0["sigx"], scr1["sigx"])

for name, img in zip(screens["names"], screens["images"]):
    print(name, "image shape:", np.array(img).shape, "min/max:", np.min(img), np.max(img))