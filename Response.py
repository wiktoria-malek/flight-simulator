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
            self.Bxx = []
            self.Bxy = []
            self.Byx = []
            self.Byy = []

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
        self.Bxx = np.array(data['Bxx']).reshape(len(self.bpms), 1)
        self.Bxy = np.array(data['Bxy']).reshape(len(self.bpms), 1)
        self.Byx = np.array(data['Byx']).reshape(len(self.bpms), 1)
        self.Byy = np.array(data['Byy']).reshape(len(self.bpms), 1)

    def save(self,filename):
        R = {
            "bpms": self.bpms,
            "hcorrs": self.hcorrs,
            "vcorrs": self.vcorrs,
            "Rxx": self.Rxx.tolist(),
            "Rxy": self.Rxy.tolist(),
            "Ryx": self.Ryx.tolist(),
            "Ryy": self.Ryy.tolist(),
            "Bxx": self.Bxx.tolist(),
            "Bxy": self.Bxy.tolist(),
            "Byx": self.Byx.tolist(),
            "Byy": self.Byy.tolist()
        }
        with open(filename, "w") as json_file:
            json.dump(R, json_file, indent=4)
