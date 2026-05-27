from abc import ABC, abstractmethod


class AbstractComputingEngine(ABC):
    name = "abstract"
    display_name = "Abstract computing engine"

    def __init__(self, interface):
        self.interface = interface

    @abstractmethod
    def fit_from_session(self, session, bounds=None):
        pass