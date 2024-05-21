import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel

class MyGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # Create layout
        layout = QVBoxLayout()

        # Add components
        label = QLabel("Hello, PyQt!")
        layout.addWidget(label)

        button = QPushButton("Click Me!")
        button.clicked.connect(self.onButtonClick)
        layout.addWidget(button)

        # Set the layout
        self.setLayout(layout)

        # Set window properties
        self.setWindowTitle("My PyQt GUI")
        self.setGeometry(100, 100, 300, 200)

    def onButtonClick(self):
        print("Button clicked!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyGUI()
    window.show()
    sys.exit(app.exec())

