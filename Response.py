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
            self.Byy = []

    def submatrix_B(self, bpms):
        bpm_indexes = [index for index, string in enumerate(self.bpms) if string in bpms]
        return (self.Bxx[bpm_indexes],
                self.Byy[bpm_indexes])

    def submatrix_Rx(self, bpms, hcorrs):
        bpm_indexes = [index for index, string in enumerate(self.bpms) if string in bpms]
        hcorrs_indexes = [index for index, string in enumerate(self.hcorrs) if string in hcorrs]
        Rxx = self.Rxx[bpm_indexes,:]
        Ryx = self.Ryx[bpm_indexes,:]
        return (Rxx[:,hcorrs_indexes],
                Ryx[:,hcorrs_indexes])

    def submatrix_Ry(self, bpms, vcorrs):
        bpm_indexes = [index for index, string in enumerate(self.bpms) if string in bpms]
        vcorrs_indexes = [index for index, string in enumerate(self.vcorrs) if string in vcorrs]
        Rxy = self.Rxy[bpm_indexes,:]
        Ryy = self.Ryy[bpm_indexes,:]
        return (Rxy[:,vcorrs_indexes],
                Ryy[:,vcorrs_indexes])

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
        self.Byy = np.array(data['Byy']).reshape(len(self.bpms), 1)

    def save(self, filename):
        R = {
            "bpms": self.bpms,
            "hcorrs": self.hcorrs,
            "vcorrs": self.vcorrs,
            "Rxx": self.Rxx.tolist(),
            "Rxy": self.Rxy.tolist(),
            "Ryx": self.Ryx.tolist(),
            "Ryy": self.Ryy.tolist(),
            "Bxx": self.Bxx.tolist(),
            "Byy": self.Byy.tolist()
        }
        with open(filename, "w") as json_file:
            json.dump(R, json_file, indent=4)
