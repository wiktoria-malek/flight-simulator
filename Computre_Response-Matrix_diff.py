python
import pickle
import numpy as np

def load_matrix_from_pickle(filepath):
    """Loads a matrix (NumPy array) from a .pkl file."""
    try:
        with open(filepath, 'rb') as f:
            matrix = pickle.load(f)
            # Optional: Ensure the loaded object is a NumPy array for safety
            if not isinstance(matrix, np.ndarray):
                raise TypeError(f"Data in {filepath} is not a NumPy array.")
            return matrix
    except FileNotFoundError:
        print(f"Error: The file {filepath} was not found.")
        return None
    except Exception as e:
        print(f"An error occurred while loading {filepath}: {e}")
        return None

def compute_matrix_difference(file1, file2):
    """Loads two matrices and computes their difference (matrix1 - matrix2)."""
    matrix1 = load_matrix_from_pickle(file1)
    matrix2 = load_matrix_from_pickle(file2)

    if matrix1 is None or matrix2 is None:
        return None

    try:
        # NumPy allows direct subtraction of arrays
        difference = matrix1 - matrix2
        return difference
    except ValueError as e:
        print(f"Error: Matrix dimensions do not match for subtraction. Details: {e}")
        return None

# --- Example Usage ---
file_path_1 = "matrix_a.pkl"
file_path_2 = "matrix_b.pkl"

# Note: You need to have these .pkl files created first.
# Example on how to create them (uncomment to run once):
# matrix_a = np.array([[1, 2], [3, 4]])
# matrix_b = np.array([[1, 1], [1, 1]])
# with open(file_path_1, 'wb') as f: pickle.dump(matrix_a, f)
# with open(file_path_2, 'wb') as f: pickle.dump(matrix_b, f)


result_matrix = compute_matrix_difference(file_path_1, file_path_2)

if result_matrix is not None:
    print("\nMatrix A:")
    print(load_matrix_from_pi