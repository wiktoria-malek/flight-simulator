from abc import ABC, abstractmethod
from Backend.State import State
import numpy as np

class AbstractMachineInterface(ABC):

    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def get_sequence(self):
        pass

    @abstractmethod
    def get_correctors(self):
        pass

    @abstractmethod
    def get_bpms(self):
        pass

    @abstractmethod
    def get_icts(self):
        pass

    def get_quadrupoles(self):
        return {
            "names": [],
            "bdes": np.array([]),
            "bact": np.array([]),
        }

    def get_sextupoles(self):
        return {
            "names": [],
            "bdes": np.array([]),
            "bact": np.array([]),
        }

    def set_sextupoles(self, names, values):
        raise NotImplementedError(f"{self.get_name()} does not implement set_sextupoles")

    def get_screens(self):
        return {"names": [], "hpixel": np.array([]), "vpixel": np.array([]), "x":np.array([]),"y":np.array([]), "sigx":np.array([]), "sigy":np.array([]),"sum":np.array([]),"hedges":[],"vedges":[],"images":[],"S":np.array([])}

    def get_target_dispersion(self, names=None):
        if names is None:
            names = self.bpms
        if isinstance(names, str):
            names = [names]
        return np.zeros(len(names)), np.zeros(len(names))

    @abstractmethod
    def get_hcorrectors_names(self):
        pass

    @abstractmethod
    def get_vcorrectors_names(self):
        pass

    @abstractmethod
    def set_correctors(self, names, values):
        pass

    @abstractmethod
    def change_energy(self):
        pass

    @abstractmethod
    def reset_energy(self):
        pass

    @abstractmethod
    def change_intensity(self):
        pass

    @abstractmethod
    def reset_intensity(self):
        pass

    def set_quadrupoles(self, names, values):
        raise NotImplementedError(f"{self.get_name()} does not implement set_quadrupoles")

    def get_state(self):
        return State(
            correctors=self.get_correctors(),
            bpms=self.get_bpms(),
            icts=self.get_icts(),
            sequence=self.get_sequence(),
            hcorrectors_names=self.get_hcorrectors_names(),
            vcorrectors_names=self.get_vcorrectors_names(),
            screens=self.get_screens(),
            quadrupoles=self.get_quadrupoles(),
            sextupoles=self.get_sextupoles(),
        )

    def restore_correctors_state(self, state):
        correctors = state.get_correctors()
        self.set_correctors(correctors["names"], correctors["bdes"])

    def restore_quadrupoles_state(self, state):
        quadrupoles = state.get_quadrupoles()
        if len(quadrupoles["names"]) > 0:
            try:
                self.set_quadrupoles(quadrupoles["names"], quadrupoles["bdes"])
            except NotImplementedError:
                pass

    def restore_sextupoles_state(self, state):
        sextupoles = state.get_sextupoles()
        if len(sextupoles["names"]) > 0:
            try:
                self.set_sextupoles(sextupoles["names"], sextupoles["bdes"])
            except NotImplementedError:
                pass

