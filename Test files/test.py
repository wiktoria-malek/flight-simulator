import sys, os, pickle, re, matplotlib, glob, time, json
from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QSizePolicy, QMainWindow, QFileDialog, QListWidget,
                             QMessageBox, QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel)
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from Emitt_Meas_Simulation_ATF2 import Emitt_Meas_Simulation
import RF_Track as rft


class EmittMeasGUI(QMainWindow, Emitt_Meas_Simulation):
    def __init__(self):
        super().__init__()
        here = os.path.dirname(os.path.abspath(__file__))
        ui_path = os.path.join(here, "EmittMeas_GUI.ui")
        uic.loadUi(ui_path, self)

        # simulation object (your original name)
        self.simulation_atf2 = Emitt_Meas_Simulation()

        self.screensListWidget.addItems(["OTR0X", "OTR1X", "OTR2X", "OTR3X"])
        self.cwd = os.getcwd()

        self.loadTwissButton.clicked.connect(self._pick_and_load_lattice_data)
        self.measureButton.clicked.connect(self._on_measure_click)

        self._hist_sigma_x = []
        self._hist_sigma_y = []
        self._hist_y_phase_space = []
        self._hist_y_phase_space = []
        self._otr_s = []          # s positions of OTRs
        self._otr_names = []      # names of OTRs in same order as sigmas

        self._setup_canvases()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def _loading_func(self, filename="", loading_name="Load file", *, use_dialog=True, base_dir=None):
        default_dir = base_dir or os.path.join(self.cwd, "Ext_ATF2")
        os.makedirs(default_dir, exist_ok=True)

        if use_dialog:
            start_path = os.path.join(default_dir, filename) if filename else default_dir
            fn, _ = QFileDialog.getOpenFileName(self, loading_name, start_path, "All files (*)")
            if not fn:
                return
        else:
            if not filename:
                return
            fn = filename
            if not os.path.isabs(fn):
                fn = os.path.join(default_dir, fn)

        fn = os.path.expanduser(fn)

        if not os.path.isfile(fn):
            QMessageBox.warning(self, "Load data", f"File not found:\n{fn}")
            return

        # you were reading the file into "selected" but never used it – not needed
        QMessageBox.information(self, "Data file selected", f"Loaded:\n{fn}")
        self.twissFileLineEdit.setText(fn)

        # keep simulation object in sync
        self.simulation_atf2.filename = fn

    def _pick_and_load_lattice_data(self):
        self._loading_func(loading_name="Load MAD-X file")

    # ------------------------------------------------------------------
    # Measurement + plots
    # ------------------------------------------------------------------
    def _on_measure_click(self):
        madx_file_path = self.twissFileLineEdit.text().strip()  # deletes chars from beginning and the end of a string
        if not madx_file_path:
            QMessageBox.warning(self, "No file selected", "Please load a MAD-X / Twiss file first.")
            return

        madx_file_path = os.path.expanduser(madx_file_path)
        if not os.path.isfile(madx_file_path):
            QMessageBox.warning(self, "File not found", f"The file does not exist:\n{madx_file_path}")
            return

        self.simulation_atf2.filename = madx_file_path
        self._start_measuring()
        self._draw_plots()

    def _setup_canvases(self):
        if FigureCanvas is None:
            self.y_phase_space_canvas = self.sigma_y_canvas = self.x_phase_space_canvas = self.sigma_x_canvas = None
            return

        def install(host):
            fig = Figure(figsize=(5, 2.4), tight_layout=True)
            canvas = FigureCanvas(fig)
            layout = host.layout()
            if layout is None:
                from PyQt6.QtWidgets import QVBoxLayout
                layout = QVBoxLayout(host)
                layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(canvas)
            return fig, canvas

        self.y_phase_space_fig, self.y_phase_space_canvas = install(self.plotFrame11)
        self.sigma_y_fig, self.sigma_y_canvas = install(self.plotFrame12)
        self.x_phase_space_fig, self.x_phase_space_canvas = install(self.plotFrame21)
        self.sigma_x_fig, self.sigma_x_canvas = install(self.plotFrame22)

    def _plot_series(self, canvas, fig, x, y, title, ylabel, xlabel):
        if canvas is None or fig is None or x is None or y is None:
            return
        fig.clear()
        ax = fig.add_subplot(111)
        ax.plot(x, y, marker="o")
        ax.set_title(title)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.tick_params(axis="both", which="major", labelsize=7)
        ax.yaxis.get_offset_text().set_fontsize(7)
        ax.grid(True, alpha=0.3)
        canvas.draw_idle()

    def _plot_phase_space(self, fig, plane_for_M, ylabel, xlabel):
        emitt_meas_simulation = self.simulation_atf2
        if self.screensListWidget.currentItem() is None:
            return
        chosen_otr = self.screensListWidget.currentItem().text()
        # use your helper to get bunch at that OTR
        B = emitt_meas_simulation.get_bunch_at_otr(chosen_otr)

        fig.clear()
        ax = fig.add_subplot(111)
        M = B.get_phase_space(plane_for_M)

        # raw coordinates (mm, mrad) – same as before, just without the broken range-plot
        ax.plot(M[:, 0], M[:, 1], '.', markersize=1)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if plane_for_M == '%x %xp':
            ax.set_title(f"Horizontal phase space at {chosen_otr}")
            self.x_phase_space_canvas.draw_idle()
        else:
            ax.set_title(f"Vertical phase space at {chosen_otr}")
            self.y_phase_space_canvas.draw_idle()
        ax.grid(True)

    def _start_measuring(self):
        emitt_meas_simulation = self.simulation_atf2

        # use the filename set from GUI; if empty, fall back to your default
        filename = emitt_meas_simulation.filename or 'Ext_ATF2/ATF2_EXT_FF_v5.2.twiss'

        lattice, element_descriptions, start, end = emitt_meas_simulation.obtaining_the_lattice(filename=filename)
        entrance_name, entrance, otrs = emitt_meas_simulation.get_data_from_twiss_file()
        Mx, My = emitt_meas_simulation.compute_transport_matrix()
        Sigma_xy_beam = emitt_meas_simulation.compute_beam_matrix()

        # use your extended version that can return bunches + names
        sigma_x_i, sigma_y_i, B_screens, inserted_screens = emitt_meas_simulation.measure_sigmas(return_bunches=True)

        emittance_x, emittance_y, beta_x, beta_y, alpha_x, alpha_y, gamma_x, gamma_y = \
            emitt_meas_simulation.solve_least_squares(Mx, My, sigma_x_i, sigma_y_i)

        # store sigmas (mm) and OTR s-positions for plotting
        self._hist_sigma_x = list(sigma_x_i)
        self._hist_sigma_y = list(sigma_y_i)
        self._otr_names = inserted_screens

        # build s coordinate list from element_descriptions
        desc_map = {name.upper(): desc for name, desc in element_descriptions.items()}
        self._otr_s = []
        for name in inserted_screens:
            desc = desc_map.get(name)
            if desc is not None:
                self._otr_s.append(desc["s_end"])
            else:
                self._otr_s.append(0.0)

        mass = rft.electronmass
        Pref = emitt_meas_simulation.Pref
        beta_gamma = Pref / mass
        print(f"Beta gamma is: {beta_gamma}")
        print(f"emittance_x (normalised) = {emittance_x} mm mrad")
        print(f"emittance_y (normalised) = {emittance_y} mm mrad")

    def _draw_plots(self):
        if not self._otr_s or not self._hist_sigma_y or not self._hist_sigma_x:
            return

        # vertical / horizontal beam size vs s
        self._plot_series(
            canvas=self.sigma_y_canvas,
            fig=self.sigma_y_fig,
            x=self._otr_s,
            y=self._hist_sigma_y,
            title="Vertical Beam Size",
            ylabel=r"$\sigma_y$ [mm]",
            xlabel="s [m]",
        )
        self._plot_series(
            canvas=self.sigma_x_canvas,
            fig=self.sigma_x_fig,
            x=self._otr_s,
            y=self._hist_sigma_x,
            title="Horizontal Beam Size",
            ylabel=r"$\sigma_x$ [mm]",
            xlabel="s [m]",
        )

        # phase-space plots at currently selected OTR
        self._plot_phase_space(plane_for_M='%x %xp', xlabel="x [mm]", ylabel="x' [mrad]", fig=self.x_phase_space_fig)
        self._plot_phase_space(plane_for_M='%y %yp', xlabel="y [mm]", ylabel="y' [mrad]", fig=self.y_phase_space_fig)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = EmittMeasGUI()
    w.show()
    sys.exit(app.exec())
