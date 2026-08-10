INTERFACE_SETUP = {
    "ATF2": [
        {
            "display_name": "ATF2 Damping Ring",
            "module": "Interfaces.ATF2.InterfaceATF2_DR",
            "class_name": "InterfaceATF2_DR",
            "settings": {"nsamples": 3},
            "actions": [],
            "units":
            {
                "corrector_strength":"T*mm",
                "bpm_position": "mm",
                "sysid_corrector_kick": 0.01
            },
            "bounds": {
                "emit_x_norm": [1.0, 10.0],
                "beta_x0": [1.0, 12.0],
                "alpha_x0": [-10.0, 3.0],
                "emit_y_norm": [0.005, 0.15],
                "beta_y0": [0.5, 8.0],
                "alpha_y0": [-4.0, 6.0],
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
                },
            "bounds": {
                "emit_x_norm": [1.0, 10.0],
                "beta_x0": [1.0, 12.0],
                "alpha_x0": [-10.0, 3.0],
                "emit_y_norm": [0.005, 0.15],
                "beta_y0": [0.5, 8.0],
                "alpha_y0": [-4.0, 6.0],
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
                    "sysid_corrector_kick": 0.01,
                    "em_sigma_unit": "mm"
                },
            "bounds":
                {
                    "emit_x_norm": [0.5, 8.0],
                    "beta_x0": [0.2, 5.0],
                    "alpha_x0": [-4.0, 2.0],
                    "emit_y_norm": [0.005, 0.12],
                    "beta_y0": [2.0, 20.0],
                    "alpha_y0": [-8.0, 2.0],
                }
        },
        {
            "display_name": "ATF2 Extraction Line RFTrack",
            "module": "Interfaces.ATF2.InterfaceATF2_Ext_RFTrack",
            "class_name": "InterfaceATF2_Ext_RFTrack",
            "settings": {"jitter":0.0, "bpm_resolution":0.00, "nsamples":1},
            "actions": ["align_everything"],
            "units":
                {
                    "corrector_strength": "T*mm",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.01,
                    "em_sigma_unit": "mm"

                },
            # # QF17X — simulation
            # "bounds": {
            #     "emit_x_norm": [4.5, 6.0],
            #     "beta_x0": [3.5, 6.5],
            #     "alpha_x0": [-1.0, 1.0],
            #     "emit_y_norm": [0.01, 0.06],
            #     "beta_y0": [0.4, 1.0],
            #     "alpha_y0": [-0.4, 0.6],
            # }

            # # QD16X — simulation
            # "bounds": {
            #     "emit_x_norm": [4.5, 6.0],
            #     "beta_x0": [0.5, 1.4],
            #     "alpha_x0": [-0.8, 0.8],
            #     "emit_y_norm": [0.01, 0.06],
            #     "beta_y0": [4.0, 7.0],
            #     "alpha_y0": [-0.5, 1.0],
            # }

        # # QD18X — simulation
        # "bounds": {
        #     "emit_x_norm": [4.5, 10.0],
        #     "beta_x0": [0.7, 5.0],
        #     "alpha_x0": [-3.0, -0.5],
        #     "emit_y_norm": [0.01, 0.9],
        #     "beta_y0": [7.5, 15.0],
        #     "alpha_y0": [-1.5, 1.0],
        # }

        # # QF17X — real machine, initial fit
        #    # around:
        #     # ml | rftrack
        #     # 8.458 | 7.8677
        #     # 5.280 | 5.782
        #     # -2.453 | -2.644
        #     # 0.389 | 0.388
        #     # 0.631 | 0.63944
        #     # 0.032 | 0.02945
        #
        # "bounds": {
        #     "emit_x_norm": [5.0, 9.0],
        #     "beta_x0": [3.0, 9.0],
        #     "alpha_x0": [-4.0, -1.0],
        #     "emit_y_norm": [0.08, 0.8],
        #     "beta_y0": [0.2, 1.5],
        #     "alpha_y0": [-1.0, 1.0],
        # }


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
            "bounds": {
                "emit_x_norm": [1e-4, 0.05],
                "beta_x0": [0.05, 5.0],
                "alpha_x0": [-6.0, 2.0],
                "emit_y_norm": [1e-4, 0.05],
                "beta_y0": [0.2, 8.0],
                "alpha_y0": [-15.0, 2.0],
            }
        },
        {
            "display_name": "ATF2 Linac Beam Transport",
            "module": "Interfaces.ATF2.InterfaceATF2_LinacBT",
            "class_name": "InterfaceATF2_LinacBT",
            "settings": {"nsamples": 3},
            "actions": [],
            "units":
                {
                    "corrector_strength": "T*mm",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.01
                },
            "bounds": {
                "emit_x_norm": [1e-4, 0.05],
                "beta_x0": [0.05, 5.0],
                "alpha_x0": [-6.0, 2.0],
                "emit_y_norm": [1e-4, 0.05],
                "beta_y0": [0.2, 8.0],
                "alpha_y0": [-15.0, 2.0],
            }
        },
        {
            "display_name": "ATF2 Linac RFTrack",
            "module": "Interfaces.ATF2.InterfaceATF2_Linac_RFTrack",
            "class_name": "InterfaceATF2_Linac_RFTrack",
            "settings": {"jitter": 0.00, "bpm_resolution": 0.00},
            "actions": ["align_everything"],
            "units":
                {
                    "corrector_strength": "T*mm",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.01
                },
            "bounds": {
                "emit_x_norm": [1e-4, 0.05],
                "beta_x0": [0.05, 5.0],
                "alpha_x0": [-6.0, 2.0],
                "emit_y_norm": [1e-4, 0.05],
                "beta_y0": [0.2, 8.0],
                "alpha_y0": [-15.0, 2.0],
            }
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
            "bounds": {
                "emit_x_norm": [0.5, 8.0],
                "beta_x0": [0.5, 12.0],
                "alpha_x0": [-5.0, 3.0],
                "emit_y_norm": [0.5, 8.0],
                "beta_y0": [0.5, 12.0],
                "alpha_y0": [-5.0, 5.0],
            }
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
            "bounds": {
                "emit_x_norm": [0.5, 8.0],
                "beta_x0": [0.5, 12.0],
                "alpha_x0": [-5.0, 3.0],
                "emit_y_norm": [0.5, 8.0],
                "beta_y0": [0.5, 12.0],
                "alpha_y0": [-5.0, 5.0],
            }
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
            "bounds":
                {
                    "emit_x_norm": [0.5, 10.0],
                    "beta_x0": [0.2, 20.0],
                    "alpha_x0": [-4.0, 2.0],
                    "emit_y_norm": [0.5, 10.0],
                    "beta_y0": [10.0, 30.0],
                    "alpha_y0": [-8.0, 2.0],
                }
        },
        {
            "display_name": "CLEAR RFTrack",
            "module": "Interfaces.CLEAR.InterfaceCLEAR_RFTrack",
            "class_name": "InterfaceCLEAR_RFTrack",
            "settings": {"jitter": 0.0, "bpm_resolution": 0.0, "nsamples": 1},
            "actions": ["align_everything","misalign_quadrupoles","misalign_bpms"],
            "units":
                {
                    "corrector_strength": "gauss*m",
                    "bpm_position": "mm",
                    "sysid_corrector_kick": 0.0001
                },
            "bounds": {
                "emit_x_norm": [5.0, 10.0],
                "beta_x0": [30.0, 70.0],
                "alpha_x0": [10.0, 35.0],
                "emit_y_norm": [5.0, 12.0],
                "beta_y0": [200.0, 400.0],
                "alpha_y0": [-150.0, -80.0],
            }
        },
    ],
}
