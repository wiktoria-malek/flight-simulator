from datetime import datetime
import numpy as np
import pickle

class State:
    def __init__(self, filename=None):
        if filename is not None:
            self.load(filename)

    def get_machine (self, interface):
        self.correctors = interface.read_correctors()
        self.bpms = interface.read_bpms()
        self.icts = interface.read_icts()
        self.sequence = interface.get_sequence()
        self.hcorrectors_names = interface.get_hcorrectors_names()
        self.vcorrectors_names = interface.get_vcorrectors_names()
        self.timestamp = datetime.now()

    def write_to_machine(self,interface):
        interface.write_correctors(self.correctors['names'], self.correctors['bdes'])

    def get_sequence(self):
        return self.sequence

    def get_correctors(self, names=None):
        correctors = self.correctors
        if names is not None:
            corr_indexes = np.array([index for index, string in enumerate(correctors['names']) if string in names])
            correctors = {
                "names": correctors['names'][corr_indexes],
                "bdes": correctors['bdes'][corr_indexes],
                "bact": correctors['bact'][corr_indexes]
            }
        return correctors         

    def get_hcorrectors_names(self):
        return self.hcorrectors_names

    def get_vcorrectors_names(self):
        return self.vcorrectors_names

    def get_bpms(self, names=None):
        bpms = self.bpms
        if names is not None:
            bpm_indexes = np.array([index for index, string in enumerate(bpms['names']) if string in names])
            bpms = {
                "names": bpms['names'][bpm_indexes],
                "x": bpms['x'][:,bpm_indexes],
                "y": bpms['y'][:,bpm_indexes],
                "tmit": bpms['tmit'][:,bpm_indexes],
            }
        return bpms         

    def get_icts(self, names=None):
        icts = self.icts
        if names is not None:
            ict_indexes = np.array([index for index, string in enumerate(icts['names']) if string in names])
            print('sei', type(icts['charge']))
            icts = {
                "names": self.icts['names'][ict_indexes],
                "charge": self.icts['charge'][ict_indexes]
            }
        return icts         

    def get_orbit(self, names=None):
        bpms = self.get_bpms(names)
        x = np.mean(bpms['x'],axis=0) # mm
        y = np.mean(bpms['y'],axis=0) # mm
        stdx = np.std(bpms['x'],axis=0) # mm
        stdy = np.std(bpms['y'],axis=0) # mm
        tmit = np.mean(bpms['tmit'],axis=0)
        faulty = (x == 0.0) & (y == 0.0)
        x[faulty] = np.NaN
        y[faulty] = np.NaN
        orbit = { "names": names, "x": x, "y": y, "stdx": stdx, "stdy": stdy, "tmit": tmit, "faulty": faulty, "nbpms": len(x) }
        return orbit

    def load(self, filename):
        with open(filename, "r") as pickle_file:
            data = pickle.load(pickle_file)
        self.sequence = data['sequence']
        self.correctors = {
            "names": data['correctors']['names']
            "bdes": data['correctors']['bdes']
            "bact": data['correctors']['bact']
        }
        self.bpms = {
            "names": data['bpms']['names'],
            "x": data['bpms']['x'],
            "y": data['bpms']['y'],
            "tmit": data['bpms']['tmit']
        }
        self.icts = {
            "names": data['icts']['names'],
            "charge": data['icts']['charge']
        }
        self.hcorrectors_names = data["hcorrectors_names"]
        self.vcorrectors_names = data["vcorrectors_names"]
        self.timestamp = datetime.strptime(data['timestamp'], "%Y/%m/%d, %H:%M:%S")

    def save(self, basename=None, filename=None):
        if basename is not None:
            time_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"{basename}_{time_str}.pkl"
        correctors = {
            'names': self.correctors['names'],
            'bdes': self.correctors['bdes'],
            'bact': self.correctors['bact']
        }
        bpms = {
            'names': self.bpms['names'],
            'x': self.bpms['x'],
            'y': self.bpms['y'],
            'tmit': self.bpms['tmit']
        }
        icts = {
            'names': self.icts['names'],
            'charge': self.icts['charge']
        }
        state = {
            "sequence": self.sequence,
            "correctors": correctors,
            "bpms": bpms,
            "icts": icts,
            "hcorrectors_names": self.hcorrectors_names,
            "vcorrectors_names": self.vcorrectors_names,
            "timestamp": self.timestamp.strftime("%Y/%m/%d, %H:%M:%S")
        }
        with open(filename, "w") as pickle_file:
            pickle.dump(state, pickle_file)
        return filename
            
