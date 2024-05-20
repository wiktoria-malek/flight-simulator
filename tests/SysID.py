import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QPushButton, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CERN SYSID")
        self.setGeometry(100, 100, 400, 300)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # Left side layout
        left_layout = QVBoxLayout()
        top_layout.addLayout(left_layout)

        # Pattern input and correctors list
        pattern_layout = QHBoxLayout()
        left_layout.addLayout(pattern_layout)

        pattern_label = QLabel("Pattern:")
        pattern_layout.addWidget(pattern_label)

        self.pattern_input = QLineEdit("?COR:LI??:*")
        pattern_layout.addWidget(self.pattern_input)

        self.correctors_list = QListWidget()
        left_layout.addWidget(self.correctors_list)

        # Add and remove buttons
        button_layout = QHBoxLayout()
        left_layout.addLayout(button_layout)

        self.add_button = QPushButton("+")
        button_layout.addWidget(self.add_button)

        self.remove_button = QPushButton("-")
        button_layout.addWidget(self.remove_button)

        self.add_from_button = QPushButton("Add from...")
        left_layout.addWidget(self.add_from_button)

        # Right side layout
        right_layout = QVBoxLayout()
        top_layout.addLayout(right_layout)

        # Info section
        info_layout = QVBoxLayout()
        right_layout.addLayout(info_layout)

        self.info_label = QLabel("Info")
        info_layout.addWidget(self.info_label)

        self.working_directory_input = QLineEdit("Working directory")
        info_layout.addWidget(self.working_directory_input)

        self.current_corr_label = QLabel("Current corr: XCOR:LI04:802")
        info_layout.addWidget(self.current_corr_label)

        # Options section
        options_layout = QVBoxLayout()
        right_layout.addLayout(options_layout)

        self.options_label = QLabel("Options")
        options_layout.addWidget(self.options_label)

        samples_layout = QHBoxLayout()
        options_layout.addLayout(samples_layout)

        self.samples_label = QLabel("N. of samples:")
        samples_layout.addWidget(self.samples_label)

        self.samples_spinbox = QSpinBox()
        self.samples_spinbox.setValue(1)
        samples_layout.addWidget(self.samples_spinbox)

        max_strength_layout = QHBoxLayout()
        options_layout.addLayout(max_strength_layout)

        self.max_strength_label = QLabel("Max strength:")
        max_strength_layout.addWidget(self.max_strength_label)

        self.max_strength_spinbox = QDoubleSpinBox()
        self.max_strength_spinbox.setValue(0.060)
        self.max_strength_spinbox.setSuffix(" kG*m")
        max_strength_layout.addWidget(self.max_strength_spinbox)

        cycle_mode_layout = QHBoxLayout()
        options_layout.addLayout(cycle_mode_layout)

        self.cycle_mode_label = QLabel("Cycle mode:")
        cycle_mode_layout.addWidget(self.cycle_mode_label)

        self.cycle_mode_combobox = QComboBox()
        self.cycle_mode_combobox.addItems(["Repeat all"])
        cycle_mode_layout.addWidget(self.cycle_mode_combobox)

        excitation_layout = QHBoxLayout()
        options_layout.addLayout(excitation_layout)

        self.horizontal_excitation_label = QLabel("Horizontal excitation:")
        excitation_layout.addWidget(self.horizontal_excitation_label)

        self.horizontal_excitation_spinbox = QDoubleSpinBox()
        self.horizontal_excitation_spinbox.setValue(0.5)
        self.horizontal_excitation_spinbox.setSuffix(" mm")
        excitation_layout.addWidget(self.horizontal_excitation_spinbox)

        self.vertical_excitation_label = QLabel("Vertical excitation:")
        excitation_layout.addWidget(self.vertical_excitation_label)

        self.vertical_excitation_spinbox = QDoubleSpinBox()
        self.vertical_excitation_spinbox.setValue(0.5)
        self.vertical_excitation_spinbox.setSuffix(" mm")
        excitation_layout.addWidget(self.vertical_excitation_spinbox)

        self.plot_orbits_checkbox = QCheckBox("Plot Orbits")
        self.plot_orbits_checkbox.setChecked(True)
        options_layout.addWidget(self.plot_orbits_checkbox)

        # Start and Stop buttons
        buttons_layout = QHBoxLayout()
        main_layout.addLayout(buttons_layout)

        self.start_button = QPushButton("START")
        self.start_button.setStyleSheet("background-color: green; color: white;")
        buttons_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("STOP")
        self.stop_button.setStyleSheet("background-color: red; color: white;")
        buttons_layout.addWidget(self.stop_button)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

