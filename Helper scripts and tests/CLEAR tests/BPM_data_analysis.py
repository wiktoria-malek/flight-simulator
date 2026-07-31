import os, sys, h5py
import numpy as np
from pprint import pprint
import matplotlib.pyplot as plt
from pathlib import Path
project_root_path = Path.cwd().resolve()
while not (project_root_path / "Interfaces").exists() and project_root_path.parent != project_root_path:
    project_root_path = project_root_path.parent
sys.path.insert(0, str(project_root_path))
os.chdir(project_root_path)
from Interfaces.CLEAR.Setup_files.CLEAR_BPM_getHV import baseline_correct, find_peak, threshold_integral

path_to_datafiles = "/Users/wiktoriamalek/CERN-Flight_Simulator-Data/20260729_BPMtests"
bpms = ["BPM0530", "BPM0595", "BPM0690", "BPM0820", "BPM0890"]

def analyze_data(filename, bpm, show=False):
    file_path = os.path.join(path_to_datafiles, filename)
    with h5py.File(file_path, "r") as f:

        H_SA = f["CLEAREventData"][f"CA.{bpm}H-SA"]["SamplesFromTrigger"]["samples"][0]
        V_SA = f["CLEAREventData"][f"CA.{bpm}V-SA"]["SamplesFromTrigger"]["samples"][0]
        S_SA = f["CLEAREventData"][f"CA.{bpm}S-SA"]["SamplesFromTrigger"]["samples"][0]

        H_b_samples = baseline_correct(H_SA)
        V_b_samples = baseline_correct(V_SA)
        S_b_samples = baseline_correct(S_SA)

        H, H_idx = find_peak(H_b_samples)
        V, V_idx = find_peak(V_b_samples)
        S, S_idx = find_peak(S_b_samples)
        print(f"{bpm}: H = {H}, V = {V}")

    if show==True:
        plt.figure()
        plt.plot(H_SA, label="H")
        plt.plot(V_SA, label="V")
        plt.plot(S_SA, label="S")
        plt.xlabel("Sample number")
        plt.ylabel("Signal amplitude [mV]")
        plt.title(f"{bpm}: H = {H}, V = {V}")
        plt.legend()
        plt.show()

    return {
        "file": filename,
        "bpm": bpm,
        "H": H,
        "V": V,
        "S": S
    }

list_to_datafiles = "/Users/wiktoriamalek/CERN-Flight_Simulator-Data/20260729_BPMtests"
list_of_files = sorted(filename for filename in os.listdir(list_to_datafiles) if filename.endswith(".h5"))
all_results = []

for orbit_number, filename in enumerate(list_of_files, start=1):
    print(f"=====================ORBIT {orbit_number}====================")
    for bpm in bpms:
        result = analyze_data(filename, bpm)
        all_results.append(result)

plt.figure()
for bpm in bpms:
    bpm_results = [result for result in all_results if result["bpm"] == bpm]
    H_values = [result["H"] for result in bpm_results]
    event_numbers = range(1, len(bpm_results) + 1)
    plt.plot(event_numbers, H_values, label=f"{bpm} H")
    plt.title("H values")
    plt.xlabel("Event number")
    plt.ylabel("Signal amplitude [mV]")
    plt.legend()
plt.show()


plt.figure()
for bpm in bpms:
    bpm_results = [result for result in all_results if result["bpm"] == bpm]
    V_values = [result["V"] for result in bpm_results]
    event_numbers = range(1, len(bpm_results) + 1)
    plt.plot(event_numbers, V_values, label=f"{bpm} V")
    plt.title("V values")
    plt.xlabel("Event number")
    plt.ylabel("Signal amplitude [mV]")
    plt.legend()
plt.show()

plt.figure()
for bpm in bpms:
    bpm_results = [result for result in all_results if result["bpm"] == bpm]
    S_values = [result["S"] for result in bpm_results]
    event_numbers = range(1, len(bpm_results) + 1)
    plt.plot(event_numbers, S_values, label=f"{bpm} S")
    plt.title("S values")
    plt.xlabel("Event number")
    plt.ylabel("Signal amplitude [mV]")
    plt.legend()
plt.show()

M_h = np.array([
    [next(result["H"] for result in all_results if result["bpm"] == bpm and result["file"]==filename)
                 for bpm in bpms]
                for filename in list_of_files])

M_v = np.array([
    [next(result["V"] for result in all_results if result["bpm"] == bpm and result["file"]==filename)
                 for bpm in bpms]
                for filename in list_of_files])

M_h = M_h - np.mean(M_h, axis=0)
U_h, singular_values_h, Vt_h = np.linalg.svd(M_h)
print(f"Singular values for H: {singular_values_h}")
variance_percent_h = singular_values_h**2 / np.sum(singular_values_h**2) * 100
print("Singular values for H in %: ", variance_percent_h)

print("First mode:", Vt_h[0])
print("Second mode:", Vt_h[1])

M_v = M_v - np.mean(M_v, axis=0)
U_v, singular_values_v, Vt_v = np.linalg.svd(M_v)
print(f"Singular values for V: {singular_values_v}")
variance_percent_v = singular_values_v**2 / np.sum(singular_values_v**2) * 100
print("Singular values for V in %: ", variance_percent_v)

print("First mode:", Vt_v[0])
print("Second mode:", Vt_v[1])

# plt.figure()
# plt.xlabel("S")
# plt.ylabel("H")
# plt.scatter(S_values, H_values)
# plt.show()

'''
The BPM position signals are relatively stable over the 97 recorded pulses, with no catastrophic outliers. 
Their pulse-to-pulse variation is strongly correlated and dominated by one common mode, accounting for 91% of the 
horizontal variation and 98% of the vertical variation.
'''