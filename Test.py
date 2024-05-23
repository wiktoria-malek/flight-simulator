from State import State
from datetime import datetime
from functools import partial

from InterfaceATF2_Linac import InterfaceATF2_Linac

# Connect to interface ATF2 Linac
I = InterfaceATF2_Linac (nsamples=10)
S = State ()
S.get_machine (I)

S.save(filename='machine_status.json')

