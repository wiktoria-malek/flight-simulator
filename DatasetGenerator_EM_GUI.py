import os, sys, time
from datetime import datetime
import numpy as np
try:
    pyqt_version = 6
    from PyQt6 import uic
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QVBoxLayout, QListWidgetItem, QStyledItemDelegate
    )
    from PyQt6.QtCore import Qt, QTimer, QRect, QObject, QThread, pyqtSignal
    from PyQt6.QtGui import QPainter, QPixmap, QFont
except ImportError:
    pyqt_version = 5
    from PyQt5 import uic
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QVBoxLayout, QListWidgetItem, QStyledItemDelegate
    )
    from PyQt5.QtCore import Qt, QTimer, QRect, QObject, QThread, pyqtSignal
    from PyQt5.QtGui import QPainter, QPixmap, QFont
from Backend.SaveOrLoad import SaveOrLoad


class SPositionDelegate(QStyledItemDelegate):
    S_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    def paint(self, painter: QPainter, option, index):
        painter.save()
        try:
            opt = option
            self.initStyleOption(opt, index)
            style = opt.widget.style() if opt.widget is not None else None
            if style is not None:
                opt_no_text = opt
                opt_no_text.text = ""
                style.drawControl(style.ControlElement.CE_ItemViewItem, opt_no_text, painter, opt.widget)

            device_name = str(index.data(Qt.ItemDataRole.UserRole) or index.data(Qt.ItemDataRole.DisplayRole) or "")
            s_text = str(index.data(self.S_ROLE) or "")
            r = opt.rect
            margin = 8
            painter.setFont(opt.font)
            painter.setPen(opt.palette.color(opt.palette.ColorRole.Text))

            fm = painter.fontMetrics()
            s_column_width = max(fm.horizontalAdvance("S = 000.000 m"), 90)

            left_rect = QRect(r.left() + margin, r.top(), max(10, r.width() - s_column_width - 3 * margin), r.height())
            right_rect = QRect(r.left() + r.width() - s_column_width - margin, r.top(), s_column_width, r.height())
            elided_name = fm.elidedText(device_name, Qt.TextElideMode.ElideRight, max(10, left_rect.width()))
            painter.drawText(left_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), elided_name)
            if s_text:
                painter.drawText(right_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), s_text)
        finally:
            painter.restore()

class MainWindow(QMainWindow, SaveOrLoad):
    def __init__(self, interface, dir_name):
        super().__init__()
        self.interface = interface
        self.dir_name = dir_name
        self.session = None
        ui_path = os.path.join(os.path.dirname(__file__),"UI files/DatasetGenerator_EM_GUI.ui")
        uic.loadUi(ui_path, self)
        self._load_logo()
        self.start_generation_button.clicked.connect(self._run_generating)
        self.stop_generation_button.clicked.connect(self._stop_generating)
        self.setWindowTitle("Emittance Measurement GUI")
        self.progressBar.setValue(0)
        self.quadrupoles_list.setItemDelegate(SPositionDelegate(self.quadrupoles_list))
        self.screens_list.setItemDelegate(SPositionDelegate(self.screens_list))
        self._optimization_t0 = None
        self._scan_stop_requested = False
        self._is_running = False
        quadrupoles = list(self.interface.get_quadrupoles()["names"])
        screens_data = self.interface.get_screens()
        screens = list(screens_data["names"])
        screen_order, screen_order_type = self._get_element_order_values(screens)
        screen_pairs = sorted(zip(screens, screen_order),key=lambda x: x[1] if np.isfinite(x[1]) else np.inf) # assigns S position to each screen
        screens_sorted = [name for name, _ in screen_pairs] # only names
        self._show_s_values_and_device_lists(self.quadrupoles_list, quadrupoles)
        self._show_s_values_and_device_lists(self.screens_list, screens_sorted)
        self._set_progress(0)
        self.screens_list.itemSelectionChanged.connect(self._screen_selection_changed)
        self._last_selected_quadrupoles = []
        self._filter_quadrupoles_in_gui()
        if hasattr(self, "pause_button"):
            self.pause_button.clicked.connect(self._pause_task)

        if hasattr(self, "resume_button"):
            self.resume_button.clicked.connect(self._resume_task)
        self._pause_requested = False
        self._stop_requested = False
        self._ml_paused = False
        self._ml_stopped = None

    def _pause_ml(self):
        if self._is_running:
            self._pause_requested = True
            return

    def _resume_task(self):
        if self._is_scanning and (self._scan_pause_requested or self._scan_is_paused):
            self.log("Resuming scan...")
            self._scan_pause_requested = False
            self._scan_is_paused = False
            return

    def _stop_scan(self):
        self.log("Stopping scan...")
        if self._is_scanning:
            self._scan_stop_requested = True
            self._scan_pause_requested = False
            self._scan_is_paused = False


    def _get_element_order_values(self, names):
        names = list(names)
        s_positions = self._get_twiss_s_positions(names)
        s_values = []
        for value in s_positions:
            try:
                value = float(value)
            except (ValueError, TypeError):
                value = np.nan
            s_values.append(value)

        if any(np.isfinite(s_values)):
            return s_values, "S"
        sequence_indices = None
        try:
            sequence_indices = self.interface.get_elements_indices(names)
        except Exception:
            sequence_indices = None
        if sequence_indices is not None:
            try:
                sequence_indices = list(sequence_indices)
            except TypeError:
                sequence_indices = None
        if sequence_indices is not None and len(sequence_indices) == len(names):
            index_values = []
            for value in sequence_indices:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = np.nan
                index_values.append(value)
            if any(np.isfinite(index_values)):
                return index_values, "index"
        return [np.nan] * len(names), ""

    def _show_s_values_and_device_lists(self, list_widget, names):
        names = list(names)
        order_values, order_kind = self._get_element_order_values(names)
        list_widget.clear()
        for name, order_value in zip(names, order_values):
            item = QListWidgetItem(str(name))
            item.setData(Qt.ItemDataRole.UserRole, str(name))
            list_widget.addItem(item)
            try:
                order_value = float(order_value)
            except (ValueError, TypeError):
                order_value = np.nan

            if np.isfinite(order_value):
                if order_kind == "index":
                    order_text = f"index = {int(order_value)}"
                else:
                    order_text = f"S = {order_value:.3f} m"
            else:
                order_text = ""
            item.setData(SPositionDelegate.S_ROLE, order_text)

    def _load_logo(self):
        if not hasattr(self, "logo_label"):
            return
        self.logo_label.setText("")
        self.logo_label.setScaledContents(False)

        transform_mode = (
            Qt.TransformationMode.SmoothTransformation
            if pyqt_version == 6
            else Qt.SmoothTransformation
        )
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "UI files", "Assets", "CERN_logo.png")
        if not os.path.isfile(logo_path):
            return
        pixmap = QPixmap(logo_path)
        if pixmap.isNull():
            return
        scaled = pixmap.scaledToHeight(80, transform_mode)
        self.logo_label.setPixmap(scaled)
        self.logo_label.setToolTip(logo_path)

    def _set_progress(self, value):
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(int(max(0, min(100,value))))
        QApplication.processEvents()

    def _get_selection(self):
        quadrupoles_all = []
        for i in range(self.quadrupoles_list.count()):
            it = self.quadrupoles_list.item(i)
            quadrupoles_all.append(it.data(Qt.ItemDataRole.UserRole) or it.text())

        screens_all = []
        for i in range(self.screens_list.count()):
            it = self.screens_list.item(i)
            screens_all.append(it.data(Qt.ItemDataRole.UserRole) or it.text())

        selected_quadrupoles = []
        for i in range(self.quadrupoles_list.count()):
            it = self.quadrupoles_list.item(i)
            if it.isSelected():
                selected_quadrupoles.append(it.data(Qt.ItemDataRole.UserRole) or it.text())

        selected_screens = []
        for i in range(self.screens_list.count()):
            it = self.screens_list.item(i)
            if it.isSelected():
                selected_screens.append(it.data(Qt.ItemDataRole.UserRole) or it.text())

        quadrupoles = selected_quadrupoles or quadrupoles_all
        screens = selected_screens or screens_all

        return quadrupoles, screens

    def _screen_selection_changed(self):
        self._filter_quadrupoles_in_gui()


    def _filter_quadrupoles_in_gui(self):
        if not hasattr(self, "quadrupoles_list") or self.quadrupoles_list is None:
            return
        if not hasattr(self, "screens_list") or self.screens_list is None:
            return

        previously_selected = []
        for i in range(self.quadrupoles_list.count()):
            item = self.quadrupoles_list.item(i)
            if item.isSelected():
                previously_selected.append(item.data(Qt.ItemDataRole.UserRole) or item.text())

        if previously_selected:
            self._last_selected_quadrupoles = list(previously_selected)
        else:
            self._last_selected_quadrupoles = list(getattr(self, "_last_selected_quadrupoles", []))

        _, selected_screens = self._get_selection()
        if not selected_screens:
            return

        screen_position, screen_order_kind = self._get_element_order_values(selected_screens)
        finite_screen_positions = [float(s) for s in screen_position if np.isfinite(s)]
        if not finite_screen_positions:
            return

        first_screen_position = min(finite_screen_positions)
        last_screen_position = max(finite_screen_positions)
        all_quadrupoles = list(self.interface.get_quadrupoles().get("names", []))
        quad_order, quad_order_kind = self._get_element_order_values(all_quadrupoles)

        if quad_order_kind != screen_order_kind: # S [m] or index
            return

        quad_pos = {name: float(s) for name, s in zip(all_quadrupoles, quad_order) if np.isfinite(s)}

        before_last_screen_quads = [
            name for name in all_quadrupoles
            if name in quad_pos and quad_pos[name] < last_screen_position
        ]

        valid_previous = [q for q in getattr(self, "_last_selected_quadrupoles", []) if q in before_last_screen_quads]
        upstream_to_first_screen_quads = [name for name in before_last_screen_quads if quad_pos[name] < first_screen_position]

        self.quadrupoles_list.blockSignals(True)
        self._show_s_values_and_device_lists(self.quadrupoles_list, before_last_screen_quads)

        if valid_previous:
            for i in range(self.quadrupoles_list.count()):
                item = self.quadrupoles_list.item(i)
                item_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                if item_name in valid_previous:
                    item.setSelected(True)
            self._last_selected_quadrupoles = list(valid_previous)
        elif upstream_to_first_screen_quads:
            closest_quad = max(upstream_to_first_screen_quads, key=lambda name: quad_pos[name])
            for i in range(self.quadrupoles_list.count()):
                item = self.quadrupoles_list.item(i)
                item_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                if item_name == closest_quad:
                    item.setSelected(True)
                    self._last_selected_quadrupoles = [closest_quad]
                    break
        elif self.quadrupoles_list.count() > 0:
            item = self.quadrupoles_list.item(0)
            if item is not None:
                item.setSelected(True)
                item_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                self._last_selected_quadrupoles = [item_name]
        else:
            self._last_selected_quadrupoles = []

        self.quadrupoles_list.blockSignals(False)

    def _get_twiss_s_positions(self, names):
        names = list(names)
        positions = [np.nan] * len(names)
        if not hasattr(self.interface, "_get_elements_positions"):
            return positions

        try:
            pos = self.interface._get_elements_positions()
            pos_names = list(pos.get("names", []))
            s = np.asarray(pos.get("S", []), dtype=float)
            lookup = {
                name: float(s[i])
                for i, name in enumerate(pos_names)
                if i < s.size and np.isfinite(s[i])
            }
            positions = [lookup.get(name, np.nan) for name in names]
        except Exception:
            positions = [np.nan] * len(names)
        return positions

    def _run_generating(self):
        self.log("Dataset generation is not connected yet.")

    def _stop_generating(self):
        self._stop_requested = True
        self.log("Stopping dataset generation requested.")

    def log(self, text):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {text}"
        if hasattr(self, "log_console"):
            self.log_console.appendPlainText(line)
        else:
            print(line)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    from Backend import SelectInterface
    interface = SelectInterface.choose_acc_and_interface()

    if interface is None:
        sys.exit(0)

    project_name = (
        interface.get_name()
        if hasattr(interface, "get_name")
        else type(interface).__name__
    )

    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = os.path.expanduser(
        f"~/flight-simulator-data/EM_{project_name}_{time_str}"
    )

    w = MainWindow(interface, dir_name)
    w.show()
    sys.exit(app.exec())