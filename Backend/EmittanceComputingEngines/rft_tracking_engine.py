from Backend.EM_helpers.Optimization_EM import Optimization_EM
from Backend.EmittanceComputingEngines.AbstractComputingEngine import AbstractComputingEngine


class RFTrackEngine(AbstractComputingEngine):
    name = "rftrack"
    display_name = "RFTrack tracking"

    def __init__(self, interface, **kwargs):
        super().__init__(interface)
        self.optimizer = Optimization_EM(interface=interface, **kwargs)

    def request_pause(self):
        self.optimizer.request_pause()

    def request_stop(self):
        self.optimizer.request_stop()

    def fit_from_session(self, session, bounds=None):
        return self.optimizer.fit_from_session(session, bounds=bounds)