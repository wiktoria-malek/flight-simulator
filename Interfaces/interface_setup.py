INTERFACE_SETUP = {
    "ATF2": [
        {
            "display_name": "ATF2 Damping Ring",
            "module": "Interfaces.ATF2.InterfaceATF2_DR",
            "class_name": "InterfaceATF2_DR",
            "settings": {"nsamples": 10},
            "actions": [],
            "units":
            {
                "corrector_strength":"T*mm",
                "bpm_position": "mm",
                "sysid_corrector_kick": 0.01
            }
        },
        {
            "display_name": "ATF2 Damping Ring RFTrack",
            "module": "Interfaces.ATF2.InterfaceATF2_DR_RFTrack",
            "class_name": "InterfaceATF2_DR_RFTrack",
            "settings": {"jitter":0.0, "bpm_resolution":0.0, "nsamples":1},
            "actions": ["align_everything", "misalign_bpms"],
            "units":
                {
                    "corrector_strength": "T*mm",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.01
                }
        },
        {
            "display_name": "ATF2 Extraction Line",
            "module": "Interfaces.ATF2.InterfaceATF2_Ext",
            "class_name": "InterfaceATF2_Ext",
            "settings": {"nsamples": 3},
            "actions": [],
            "units":
                {
                    "corrector_strength": "T*mm",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.01
                },
        },
        {
            "display_name": "ATF2 Extraction Line RFTrack",
            "module": "Interfaces.ATF2.InterfaceATF2_Ext_RFTrack",
            "class_name": "InterfaceATF2_Ext_RFTrack",
            "settings": {"jitter":0.00, "bpm_resolution":0.00},
            "actions": ["align_everything", "misalign_bpms"],
            "units":
                {
                    "corrector_strength": "T*mm",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.01
                }
        },
        {
            "display_name": "ATF2 Linac",
            "module": "Interfaces.ATF2.InterfaceATF2_Linac",
            "class_name": "InterfaceATF2_Linac",
            "settings": {"nsamples":3},
            "actions": [],
            "units":
                {
                    "corrector_strength": "T*mm",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.01
                },
        },
    ],

    "FACET2": [
        {
            "display_name": "FACET2 Linac RFTrack",
            "module": "Interfaces.FACET2.InterfaceFACET2_Linac_RFTrack",
            "class_name": "InterfaceFACET2_Linac_RFTrack",
            "settings": {"jitter":0.0, "bpm_resolution":0.0, "nsamples":1},
            "actions": ["align_everything"],
            "units":
                {
                    "corrector_strength": "gauss*m",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.0001
                },
        },
        {
            "display_name": "FACET2 Linac",
            "module": "Interfaces.FACET2.InterfaceFACET2_Linac",
            "class_name": "InterfaceFACET2_Linac",
            "settings": {"nsamples":10},
            "actions": [],
            "units":
                {
                    "corrector_strength": "gauss*m",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.0001
                },
        },],

    "CLEAR": [
        {
            "display_name": "CLEAR",
            "module": "Interfaces.CLEAR.InterfaceCLEAR",
            "class_name": "CLEAR_real_machine",
            "settings": {"nsamples":3},
            "actions": [],
            "units":
                {
                    "corrector_strength": "gauss*m",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.0001
                },
        },
        {
            "display_name": "CLEAR RFTrack",
            "module": "Interfaces.CLEAR.InterfaceCLEAR_RFTrack",
            "class_name": "InterfaceCLEAR_RFTrack",
            "settings": {"jitter":0.1, "bpm_resolution":0.05, "nsamples":1},
            "actions": ["align_everything","misalign_quadrupoles","misalign_bpms"],
            "units":
                {
                    "corrector_strength": "gauss*m",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.0001
                },
        },
    ],
}