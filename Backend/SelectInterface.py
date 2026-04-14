try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QDialogButtonBox,
        QRadioButton, QLabel,QMessageBox,QPushButton
        )
    from PyQt6.QtCore import QEvent, Qt
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QDialogButtonBox,
        QRadioButton, QLabel,QMessageBox, QPushButton
        )
    from PyQt5.QtCore import QEvent, Qt

import importlib
from Interfaces.interface_setup import INTERFACE_SETUP

class SelectAcc(QDialog):
    def __init__(self,machines,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select a machine")
        self.selected_machine = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose one of the following accelerators:"))

        self.radio_buttons = []
        for acc in machines:
            rb = QRadioButton(acc)
            self.radio_buttons.append(rb)
            layout.addWidget(rb)

        if self.radio_buttons:
            self.radio_buttons[0].setChecked(True) #default ATF2

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        layout.addWidget(self.button_box)

        self.installEventFilter(self)

    def accept(self):
        for rb in self.radio_buttons:
            if rb.isChecked():
                self.selected_machine = rb.text()
                break
        super().accept()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            enter_keys = {getattr(Qt.Key, "Key_Return", None), getattr(Qt.Key, "Key_Enter", None)}
            if event.key() in enter_keys:
                ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
                if ok_button.isEnabled():
                    ok_button.click()
                    return True
        return super().eventFilter(obj, event)

class InterfaceSelectionDialog(QDialog):
    def __init__(self, selected_acc,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select an Interface")
        self.selected_interface = None
        self.selected_interface_name = None
        self.selected_acc = selected_acc
        self.go_back=False
        self.are_more_machines=len(INTERFACE_SETUP.keys())>1
        self.entries=INTERFACE_SETUP.get(selected_acc,[])
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose one of the following Interfaces:"))

        self.radio_buttons = []
        for entry in self.entries:
            rb = QRadioButton(entry["display_name"])
            self.radio_buttons.append(rb)
            layout.addWidget(rb)

        if self.radio_buttons:
            self.radio_buttons[0].setChecked(True)

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        if self.are_more_machines:
            self.back_button=QPushButton("Back")
            self.button_box.addButton(self.back_button,QDialogButtonBox.ButtonRole.ActionRole)
            self.back_button.clicked.connect(self._go_back)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        layout.addWidget(self.button_box)

        self.installEventFilter(self)

    def _go_back(self):
        self.go_back=True
        self.reject()

    def accept(self):
        selected_entry = None
        for rb, entry in zip(self.radio_buttons, self.entries):
            if rb.isChecked():
                selected_entry = entry
                break

        if selected_entry is None:
            super().accept()
            return

        module_name = selected_entry["module"]
        class_name = selected_entry["class_name"]
        settings = dict(selected_entry.get("settings", {}))
        actions = list(selected_entry.get("actions", []))

        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            self.selected_interface = cls(**settings)

            for action_name in actions:
                action = getattr(self.selected_interface, action_name, None)
                if callable(action):
                    action()

            self.selected_interface_name = self.selected_interface.get_name()
            super().accept()

        except Exception as e:
            QMessageBox.critical(self,"Interface unavailable",f"This interface is unavailable. {e}")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            enter_keys = {getattr(Qt.Key, "Key_Return", None), getattr(Qt.Key, "Key_Enter", None)}
            if event.key() in enter_keys:
                ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
                if ok_button.isEnabled():
                    ok_button.click()
                    return True
        return super().eventFilter(obj, event)


def choose_acc_and_interface(parent=None):
    machines=sorted(INTERFACE_SETUP.keys())

    if len(machines)==1:
        accelerator=machines[0]
        interface_dialog=InterfaceSelectionDialog(accelerator,parent=parent)
        if interface_dialog.exec():
            return interface_dialog.selected_interface
        return None
    while True:
        acc_dialog=SelectAcc(machines,parent=parent)
        if acc_dialog.exec():
            accelerator=acc_dialog.selected_machine
        else:
            return None
        interface_dialog=InterfaceSelectionDialog(accelerator,parent=None)
        if interface_dialog.exec():
            return interface_dialog.selected_interface
        if getattr(interface_dialog,"go_back",False):
            continue
        return None


