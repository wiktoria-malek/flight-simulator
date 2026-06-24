# from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack  # popraw ścieżkę importu jeśli inna
# interface = InterfaceATF2_Ext_RFTrack()
# print("ok")

# ^ it works

# from Backend.EmittanceComputingEngines.select_engine import EmittanceComputingEngineSelector
# from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack
# interface = InterfaceATF2_Ext_RFTrack()
# print("ok")

# ^ this doesn't work


import sys, RF_Track as rft
before = set(sys.modules)
from Backend.EmittanceComputingEngines.select_engine import EmittanceComputingEngineSelector
new = set(sys.modules) - before
print(sorted(m for m in new if any(k in m for k in
      ("torch","xopt","botorch","gpytorch","scipy","sklearn","numba","mkl","tensorflow"))))