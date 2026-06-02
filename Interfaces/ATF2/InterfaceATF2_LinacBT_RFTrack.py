class InterfaceATF2_LinacBT_RFTrack(InterfaceATF2_Linac_RFTrack):

    def get_name(self):
        return "ATF2_LinacBT_RFT"

    def _build_lattice(self):
        lattice = super()._build_lattice()

        self._append_bt(lattice)

        return lattice