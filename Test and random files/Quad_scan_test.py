import numpy as np
from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack
from State import State

interface = InterfaceATF2_Ext_RFTrack(nparticles=2000)
S=State(interface=interface)
quadrupole_names=interface.get_quadrupoles_names()
screens=interface.get_screens_names()
quads_to_scan=quadrupole_names[:3]
deltas=np.linspace(-0.05,0.05,11)
results={}
for quadrupole in quads_to_scan:
    quad_info=interface.get_quadrupoles()
    quad_index = list(quad_info["names"]).index(quadrupole)
    k1_0 = float(quad_info["bdes"][quad_index])
    k1_values=deltas+k1_0
    sigx_list=[]
    sigy_list=[]
    print("Scanning quadrupole:", quadrupole)
    for k1 in k1_values:
        interface.set_quadrupoles(quadrupole,k1)
        S.pull(interface)
        screen=interface.get_screens()
        sigx_list.append(np.array(screen['sigx']))
        sigy_list.append(np.array(screen['sigy']))
        print("K1:", k1, "sigy:", screen["sigy"])

    results[quadrupole]={
        "k1":k1_values,
        "sigx":np.vstack(sigx_list),
        "sigy":np.vstack(sigy_list),
        "k1_0":k1_0,
        "screens":np.array(screens)
    }