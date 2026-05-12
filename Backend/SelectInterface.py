try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QDialogButtonBox,
        QRadioButton, QLabel,QMessageBox,QPushButton,
        QButtonGroup
        )
    from PyQt6.QtCore import QEvent, Qt
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QDialogButtonBox,
        QRadioButton, QLabel,QMessageBox, QPushButton,
        QButtonGroup
        )
    from PyQt5.QtCore import QEvent, Qt

import importlib

from Interfaces.interface_setup import INTERFACE_SETUP

def _no_focus_policy():
    return Qt.FocusPolicy.NoFocus if hasattr(Qt, "FocusPolicy") else Qt.NoFocus

def _strong_focus_policy():
    return Qt.FocusPolicy.StrongFocus if hasattr(Qt, "FocusPolicy") else Qt.StrongFocus

class SelectAcc(QDialog):
    def __init__(self,machines,parent=None):
        super().__init__(parent)
        self.setFocusPolicy(_strong_focus_policy())
        self.setWindowTitle("Select a machine")
        self.selected_machine = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose one of the following accelerators:"))

        self.radio_buttons = []
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        for index, acc in enumerate(machines):
            rb = QRadioButton(acc)
            rb.setFocusPolicy(_no_focus_policy())
            self.radio_buttons.append(rb)
            self.button_group.addButton(rb, index)
            layout.addWidget(rb)

        if self.radio_buttons:
            self.radio_buttons[0].setChecked(True) #default ATF2

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.button_box = QDialogButtonBox(buttons)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setDefault(True)
        self.button_box.setFocusPolicy(_no_focus_policy())
        for button in self.button_box.buttons():
            button.setFocusPolicy(_no_focus_policy())
        layout.addWidget(self.button_box)
        self.setFocus()

        # self.installEventFilter(self)

    def accept(self):
        for rb in self.radio_buttons:
            if rb.isChecked():
                self.selected_machine = rb.text()
                break
        super().accept()

    def _move_selection(self, step):
        if not self.radio_buttons:
            return
        current_index = next((i for i, rb in enumerate(self.radio_buttons) if rb.isChecked()), 0)
        new_index = (current_index + int(step)) % len(self.radio_buttons)
        self.radio_buttons[new_index].setChecked(True)

    def keyPressEvent(self, event):
        key = event.key()
        enter_keys = {getattr(Qt.Key, "Key_Return", None), getattr(Qt.Key, "Key_Enter", None)}
        down_keys = {getattr(Qt.Key, "Key_Down", None), getattr(Qt.Key, "Key_Right", None)}
        up_keys = {getattr(Qt.Key, "Key_Up", None), getattr(Qt.Key, "Key_Left", None)}

        if key in enter_keys:
            ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button.isEnabled():
                ok_button.click()
                return

        if key in down_keys:
            self._move_selection(1)
            return

        if key in up_keys:
            self._move_selection(-1)
            return

        super().keyPressEvent(event)

class InterfaceSelectionDialog(QDialog):
    def __init__(self, selected_acc,parent=None):
        super().__init__(parent)
        self.setFocusPolicy(_strong_focus_policy())
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
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        for index, entry in enumerate(self.entries):
            rb = QRadioButton(entry["display_name"])
            rb.setFocusPolicy(_no_focus_policy())
            self.radio_buttons.append(rb)
            self.button_group.addButton(rb, index)
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
        self.button_box.setFocusPolicy(_no_focus_policy())
        for button in self.button_box.buttons():
            button.setFocusPolicy(_no_focus_policy())
        layout.addWidget(self.button_box)
        self.setFocus()

        # self.installEventFilter(self)

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

            super().accept()

        except Exception as e:
            QMessageBox.critical(self,"Interface unavailable",f"This interface is unavailable. {e}")

    def _move_selection(self, step):
        if not self.radio_buttons:
            return
        current_index = next((i for i, rb in enumerate(self.radio_buttons) if rb.isChecked()), 0)
        new_index = (current_index + int(step)) % len(self.radio_buttons)
        self.radio_buttons[new_index].setChecked(True)

    def keyPressEvent(self, event):
        key = event.key()
        enter_keys = {getattr(Qt.Key, "Key_Return", None), getattr(Qt.Key, "Key_Enter", None)}
        down_keys = {getattr(Qt.Key, "Key_Down", None), getattr(Qt.Key, "Key_Right", None)}
        up_keys = {getattr(Qt.Key, "Key_Up", None), getattr(Qt.Key, "Key_Left", None)}
        back_keys = {getattr(Qt.Key, "Key_Escape", None), getattr(Qt.Key, "Key_Backspace", None)}

        if key in enter_keys:
            ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button.isEnabled():
                ok_button.click()
                return

        if key in back_keys and self.are_more_machines:
            self._go_back()
            return

        if key in down_keys:
            self._move_selection(1)
            return

        if key in up_keys:
            self._move_selection(-1)
            return

        super().keyPressEvent(event)


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


