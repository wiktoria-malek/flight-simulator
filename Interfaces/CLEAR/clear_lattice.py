import re
from linear_optics import Lattice, Drift, Quad
from config import quad_length, get_ITF

# Source (November 2024)
# https://gitlab.cern.ch/acc-models/acc-models-clear/-/blob/master/survey/clear.survey0_filtered.tfs?ref_type=heads

def get_quad_K(I, P_ref):
    G_0 = I * get_ITF(I) / quad_length
    K = 299.8 * G_0 / P_ref # 1/m2
    return K

# Load survey file
with open('resources/clearST.survey0_filtered.tfs') as file:
    lines = file.readlines()

# Construct a dict of all elements relevant for the quad scan
element_descriptions = {}
previous_name = None
quad_index = 0

# Loop through the survey line-by-line
for line in lines:
    # Skip preamble
    if line[0:2] != ' "':
        continue

    # Find relevant parts of text
    text = re.findall(r'"([A-Za-z0-9.$_]+)"', line)
    numbers = re.findall('\d+\.\d+', line)

    name = text[0]

    # Skip everything except screens and quads
    if not('BTV' in name or 'QFD' in name or 'QDD' in name):
        continue

    # Skip unused screens
    if name == 'CA.BTV0215' or name == 'CA.BTV0800':
        continue

    # Specify element type
    element_type = name.split('.')[1][0:3]

    # Set length and position
    s_end = float(numbers[0])
    L = float(numbers[1])
    s_start = s_end - L
    s_center = round((s_start + s_end)/2, 5)

    # Adjust length if quad
    if element_type == 'QFD' or element_type == 'QDD':
        s_end = s_center + quad_length/2
        s_start = s_center - quad_length/2
        L = quad_length

    # Round values to remove float errors
    L = round(L, 4)
    s_start = round(s_start, 4)
    s_center = round(s_center, 5)
    s_end = round(s_end, 4)

    # Add drift from previous element
    if previous_name is not None:
        element_descriptions[previous_name + ' Drift'] = {
            'element_type': 'Drift',
            'L': round(s_start - element_descriptions[previous_name]['s_end'], 4),
            's_start': element_descriptions[previous_name]['s_end'], 
            's_center': round((element_descriptions[previous_name]['s_end'] + s_start)/2, 5), 
            's_end': s_start,
            'quad_index': None,
        }

    # Add current element
    element_descriptions[name] = {
        'element_type': element_type,
        'L': L,
        's_start': s_start, 
        's_center': s_center,
        's_end': s_end,
        'quad_index': quad_index if text[1] == 'QUADRUPOLE' else None,
    }

    if element_type == 'QFD' or element_type == 'QDD':
        quad_index += 1
    
    previous_name = name

# Return a lattice object from start to end, using a current vector with the currents of each quad in order
def get_lattice(start, end, P_ref, currents, include_end = True):
    start_index = list(element_descriptions.keys()).index(start)
    end_index = list(element_descriptions.keys()).index(end)
    if include_end: end_index += 1

    K = get_quad_K(currents, P_ref)
    
    lattice = Lattice()
    for element_description in list(element_descriptions.values())[start_index:end_index]:
        element_type, L, _, _, _, quad_index = element_description.values()
        if element_type == 'Drift':
            element = Drift(L)
            lattice.append_element(element)

        elif element_type == 'QFD':
            element = Quad(L, K[quad_index])
            lattice.append_element(element)
            
        elif element_type == 'QDD':
            element = Quad(L, -K[quad_index])
            lattice.append_element(element)
            
    return lattice