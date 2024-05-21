from datetime import datetime
import numpy as np
import json

class State:
    def __init__(self, interface):
        self.interface = interface;

    def get_machine(self):
        self.correctors = self.interface.read_correctors()
        self.bpms = self.interface.read_bpms()
        self.timestamp = datetime.now()

    def vary_correctors(self, names, corr_vals):
        self.interface.vary_correctors(names, corr_vals)
        self.get_machine()
            
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

    def get_bpms(self, names=None):
        bpms = self.bpms
        print(enumerate(bpms['names']))
        if names is not None:
            bpm_indexes = np.array([index for index, string in enumerate(bpms['names']) if string in names])
            bpms = {
                "names": bpms['names'][bpm_indexes],
                "x": bpms['x'][:,bpm_indexes],
                "y": bpms['y'][:,bpm_indexes],
                "tmit": bpms['tmit'][:,bpm_indexes],
            }
        return bpms         

    def get_orbit(self, names=None):
        bpms = self.get_bpms(names)
        x = np.mean(bpms['x'],axis=0)
        y = np.mean(bpms['y'],axis=0)
        stdx = np.std(bpms['x'],axis=0)
        stdy = np.std(bpms['y'],axis=0)
        tmit = np.mean(bpms['tmit'],axis=0)
        faulty = (x == 0.0) & (y == 0.0)
        x[faulty] = np.NaN
        y[faulty] = np.NaN
        orbit = { "names": names, "x": x, "y": y, "stdx": stdx, "stdy": stdy, "tmit": tmit, "faulty": faulty, "nbpms": len(x) }
        return orbit

    def load(self, filename):
        with open(filename, "r") as json_file:
            data = json.load(json_file)
        self.correctors = {
            "names": data['correctors']['names'],
            "bdes": np.array(data['correctors']['bdes']),
            "bact": np.array(data['correctors']['bact']),
        }
        self.bpms = {
            "names": data['bpms']['names'],
            "x": np.array(data['bpms']['x']),
            "y": np.array(data['bpms']['y']),
            "tmit": np.array(data['bpms']['tmit'])
        }
        self.timestamp = datetime.strptime(data['timestamp'], "%Y/%m/%d, %H:%M:%S")

    def save(self, basename):
        time_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{basename}_{time_str}.json"
        correctors = self.correctors
        correctors['bdes'] = correctors['bdes'].tolist()
        correctors['bact'] = correctors['bact'].tolist()
        bpms = self.bpms
        bpms['x'] = bpms['x'].tolist()
        bpms['y'] = bpms['y'].tolist()
        bpms['tmit'] = bpms['tmit'].tolist()
        state = {
            "correctors": correctors,
            "bpms": bpms,
            "timestamp": self.timestamp.strftime("%Y/%m/%d, %H:%M:%S")
        }
        with open(filename, "w") as json_file:
            json.dump(state, json_file, indent=4)

