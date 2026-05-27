from MachineLearning.ML_train import MLInterface
from Backend.EmittanceComputingEngines.rft_tracking_engine import RFTrackEngine


class MLEngine(RFTrackEngine):
    name = "machine_learning"
    display_name = "Machine learning model"

    def __init__(self, interface, quad_name, screens, machine_name, **kwargs):
        ml_interface = MLInterface(interface, quad_name=quad_name, screens=screens, machine_name=machine_name)
        super().__init__(ml_interface, **kwargs)
        self.real_interface = interface