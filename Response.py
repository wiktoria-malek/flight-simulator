import numpy as np
import json

class Response():
    def __init__(self,filename=None):
        if filename is not None:
            self.load(filename)
        else:
            self.bpms = []
            self.hcorrs = []
            self.vcorrs = []
            self.Rxx = []
            self.Rxy = []
            self.Ryx = []
            self.Ryy = []

    def load(self,filename):
        with open(filename, "r") as json_file:
            data = json.load(json_file)
        self.bpms = data['bpms']
        self.hcorrs = data['hcorrs']
        self.vcorrs = data['vcorrs']
        self.Rxx = np.array(data['Rxx']).reshape(len(self.bpms), len(self.hcorrs))
        self.Rxy = np.array(data['Rxy']).reshape(len(self.bpms), len(self.vcorrs))
        self.Ryx = np.array(data['Ryx']).reshape(len(self.bpms), len(self.hcorrs))
        self.Ryy = np.array(data['Ryy']).reshape(len(self.bpms), len(self.vcorrs))

    def save(self,filename):
        R = {
            "bpms": self.bpms,
            "hcorrs": self.hcorrs,
            "vcorrs": self.vcorrs,
            "Rxx": self.Rxx.tolist(),
            "Rxy": self.Rxy.tolist(),
            "Ryx": self.Ryx.tolist(),
            "Ryy": self.Ryy.tolist()
        }
        with open(filename, "w") as json_file:
            json.dump(R, json_file, indent=4)
