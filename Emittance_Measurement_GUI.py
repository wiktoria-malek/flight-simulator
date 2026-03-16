import os, sys, json, matplotlib, pickle,pprint
from datetime import datetime
import numpy as np
from SaveOrLoad import SaveOrLoad
matplotlib.use("QtAgg")
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow,QMessageBox,QFileDialog,QVBoxLayout, QListWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from State import State
from scipy.optimize import least_squares

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure(figsize=(5, 3.2), tight_layout=True)
        super().__init__(fig)
        self.setParent(parent)
        self.ax = fig.add_subplot(111)

class MainWindow(QMainWindow,SaveOrLoad):
    def __init__(self, interface, dir_name):
        super().__init__()
        self.interface = interface
        self.dir_name = dir_name
        self._cancel = False
        self.S = State(interface=self.interface)
        ui_path = os.path.join(os.path.dirname(__file__), "UI files/Emittance_Measurement_GUI.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Emittance Measurement GUI")
        self.session = None
        self.canvas = MatplotlibWidget(self.plotPlaceholder)
        layout = self.plotPlaceholder.layout()
        if layout is None:
            layout = QVBoxLayout(self.plotPlaceholder)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        quadrupoles_list = interface.get_quadrupoles()['names']
        screens_list = interface.get_screens()['names']
        self.quadrupoles_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.quadrupoles_list.insertItems(0, quadrupoles_list)
        self.screens_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.screens_list.insertItems(0, screens_list)
        self.load_quadrupoles_button.clicked.connect(self._load_quadrupoles)
        self.load_screens_button.clicked.connect(self._load_screens)
        self.stop_button.clicked.connect(self._stop_scan)
        self.start_button.clicked.connect(self._run_scan)
        self.load_session_button.clicked.connect(self._load_session_em)
        self.fit_emm_twiss_button.clicked.connect(self._fit_twiss_and_emittance)
        self.quadrupoles_list.itemSelectionChanged.connect(self._update_plot_controls)
        self.screens_list.itemSelectionChanged.connect(self._update_plot_controls)
        self._update_plot_controls()
        self.measure_optics_button.clicked.connect(self._run_measure_optics)
        self._clear_fit_result_panel()

    def _clear_fit_result_panel(self):
        self.result_reference_screen.setText("-")
        self.result_quad.setText("-")
        self.result_emit_x_norm.setText("-")
        self.result_emit_y_norm.setText("-")
        self.result_beta_x0.setText("-")
        self.result_alpha_x0.setText("-")
        self.result_beta_y0.setText("-")
        self.result_alpha_y0.setText("-")

    def _update_fit_result_panel(self, result):
        self.result_reference_screen.setText(str(result.get("screen0", "-")))
        self.result_quad.setText(str(result.get("quad_name", "-")))
        self.result_emit_x_norm.setText(f'{result.get("emit_x_norm", float("nan")):.4f} mm.mrad')
        self.result_emit_y_norm.setText(f'{result.get("emit_y_norm", float("nan")):.4f} mm.mrad')
        self.result_beta_x0.setText(f'{result.get("beta_x0", float("nan")):.4f} m')
        self.result_beta_y0.setText(f'{result.get("beta_y0", float("nan")):.4f} m')
        self.result_alpha_x0.setText(f'{result.get("alpha_x0", float("nan")):.4f}')
        self.result_alpha_y0.setText(f'{result.get("alpha_y0", float("nan")):.4f}')

    def _update_plot_controls(self):
        selected_quadrupoles = [it.text() for it in self.quadrupoles_list.selectedItems()]
        selected_screens=[it.text() for it in self.screens_list.selectedItems()]

        if not selected_quadrupoles:
            selected_quadrupoles = self.interface.get_quadrupoles()["names"]
        if not selected_screens:
            selected_screens = self.interface.get_screens()["names"]
        current_quadrupole=self.quad_on_plot.currentText() if self.quad_on_plot.count() else ""
        current_screen=self.screen_on_plot.currentText() if self.screen_on_plot.count() else ""

        self.quad_on_plot.blockSignals(True) # stops sudden signal exchange
        self.screen_on_plot.blockSignals(True)

        self.quad_on_plot.clear()
        self.screen_on_plot.clear()

        self.quad_on_plot.addItems(selected_quadrupoles)
        self.screen_on_plot.addItems(selected_screens)

        if current_quadrupole in selected_quadrupoles:
            self.quad_on_plot.setCurrentText(current_quadrupole)
        if current_screen in selected_screens:
            self.screen_on_plot.setCurrentText(current_screen)

        self.quad_on_plot.blockSignals(False)
        self.screen_on_plot.blockSignals(False)


    def _stop_scan(self):
        self._cancel = True
        QMessageBox.information(self, "Scan", "Stop requested. Finishing current iteration...")

    def _get_selection(self):
        quadrupoles_all = self.S.get_quadrupoles()["names"]
        screens_all = self.S.get_screens()["names"]

        selected_quadrupoles = []
        for i in range(self.quadrupoles_list.count()):
            it = self.quadrupoles_list.item(i)
            if it.isSelected():
                selected_quadrupoles.append(it.text())
        quadrupoles = selected_quadrupoles or quadrupoles_all

        selected_screens = []
        for i in range(self.screens_list.count()):
            it = self.screens_list.item(i)
            if it.isSelected():
                selected_screens.append(it.text())
        screens = selected_screens or screens_all

        return quadrupoles, screens

    def _run_scan(self):
        selected_quadrupoles =[it.text() for it in self.quadrupoles_list.selectedItems()]
        selected_screens =[it.text() for it in self.screens_list.selectedItems()]

        if not selected_quadrupoles:
            selected_quadrupoles = self.interface.get_quadrupoles()["names"]
        if not selected_screens:
            selected_screens = self.interface.get_screens()["names"]

        max_delta=float(self.delta_max_scan.value())
        min_delta=float(self.delta_min_scan.value())
        steps=int(self.steps_settings.value())
        nshots=int(self.meas_per_step.value())
        deltas=np.linspace(min_delta, max_delta, steps)

        if max_delta<=min_delta:
            QMessageBox.information(self, "Scan", "Max delta must be bigger than min delta.!")

        quadrupoles=self.interface.get_quadrupoles()
        quad_name=self.quad_on_plot.currentText()
        if not quad_name:
            quad_name=selected_quadrupoles[0]
        screen_for_plot=self.screen_on_plot.currentText()
        if not screen_for_plot:
            screen_for_plot=selected_screens[0]

        if screen_for_plot in selected_screens:
            plot_screen_index=selected_screens.index(screen_for_plot)
        else:
            plot_screen_index=0

        quad_index=list(quadrupoles['names']).index(quad_name)
        K1_0=float(quadrupoles['bdes'][quad_index])
        K1_values=K1_0*(1+deltas)
        print("quad:", quad_name, "K1_0:", K1_0)
        print("K1 min/max:", float(K1_values.min()), float(K1_values.max()))
        number_of_screens=len(selected_screens)
        sigx_mean=np.full((steps,number_of_screens), np.nan,dtype=float)
        sigy_mean=np.full((steps,number_of_screens), np.nan,dtype=float)
        sigx_std=np.full((steps,number_of_screens), np.nan,dtype=float)
        sigy_std=np.full((steps,number_of_screens), np.nan,dtype=float)

        initial_K1_0=K1_0

        for i, K1 in enumerate(K1_values):
            if self._cancel:
               break
            self.interface.set_quadrupoles([quad_name],[float(K1)])
            sx_shots=np.full((nshots,number_of_screens), np.nan,dtype=float)
            sy_shots=np.full((nshots,number_of_screens), np.nan,dtype=float)

            for j in range(nshots):
                if self._cancel:
                    break
                screens=self.interface.get_screens(selected_screens)
                name_to_index={name: index for index, name in enumerate(screens["names"])}

                for k,sname in enumerate(selected_screens):
                    index=name_to_index[sname]
                    sx_shots[j,k]=float(screens['sigx'][index])
                    sy_shots[j,k]=float(screens['sigy'][index])

            sigx_mean[i,:]=np.nanmean(sx_shots,axis=0)
            print("selected_screens:", selected_screens)
            print("sigx_mean step", i, ":", sigx_mean[i, :])
            sigy_mean[i,:]=np.nanmean(sy_shots,axis=0)
            sigx_std[i,:]=np.nanstd(sx_shots,axis=0)
            sigy_std[i,:]=np.nanstd(sy_shots,axis=0)

            self.canvas.ax.clear()
            self.canvas.ax.plot(deltas[:i+1],sigx_mean[:i+1,plot_screen_index]**2,'b')
            self.canvas.ax.set_xlabel("delta value")
            self.canvas.ax.set_ylabel(f"sigx^2 value on {screen_for_plot}")
            self.canvas.ax.grid(True)
            self.canvas.ax.set_title(f"Quadrupole scan for {quad_name}")
            self.canvas.draw_idle()
            QApplication.processEvents()

        self.interface.set_quadrupoles([quad_name],[float(initial_K1_0)])
        QMessageBox.information(self, "Scan", "Scan finished.")
        self.session={
            "measured_optics":None,
            "fit_result_twiss_emit":None,
            "delta_min": min_delta,
            "delta_max": max_delta,
            "steps": steps,
            "nshots": nshots,
            "quad_name": quad_name,
            "quadrupoles": selected_quadrupoles,
            "screens": selected_screens,
            "K1_0": initial_K1_0,
            "sigx_mean": sigx_mean.tolist(),
            "sigy_mean": sigy_mean.tolist(),
            "sigx_std": sigx_std.tolist(),
            "sigy_std": sigy_std.tolist(),
            "deltas": deltas.tolist() if deltas is not None else None,
            "K1_values": K1_values.tolist() if K1_values is not None else None,
        }

        self.session["scan_quality"]=self._is_quality_scan(sigx_mean=sigx_mean,sigy_mean=sigy_mean,screens=selected_screens)
        self._clear_fit_result_panel()
        self._save_session_quad_scan(delta_min=min_delta,delta_max=max_delta,steps=steps,nshots=nshots,quad_name=quad_name,K1_0=initial_K1_0,sigx_mean=sigx_mean,sigy_mean=sigy_mean,sigx_std=sigx_std,sigy_std=sigy_std,deltas=deltas,K1_values=K1_values)

        scan_quality=self.session["scan_quality"]
        if not scan_quality["is_useful_scan"]:
            QMessageBox.information(self, "Scan", "Scan not useful. Obtained too small beam size variation on the selected screens.")

    def _is_quality_scan(self,sigx_mean,sigy_mean,screens,threshold=0.05):
        sigx_mean=np.array(sigx_mean,dtype=float)
        sigy_mean=np.array(sigy_mean,dtype=float)
        screens=list(screens)

        x_range=np.nanmax(sigx_mean**2,axis=0) - np.nanmin(sigx_mean**2,axis=0) # maximum - minimum of an array
        y_range=np.nanmax(sigy_mean**2,axis=0) - np.nanmin(sigy_mean**2,axis=0)

        x_mean=np.nanmean(sigx_mean**2,axis=0)
        y_mean=np.nanmean(sigy_mean**2,axis=0) # 0 for columns, 1 for rows

        x_rel=np.full(len(screens),np.nan,dtype=float)
        y_rel=np.full(len(screens),np.nan,dtype=float)

        mx=np.isfinite(x_range) & np.isfinite(x_mean) & (np.abs(x_mean)>0)
        my=np.isfinite(y_range) & np.isfinite(y_mean) & (np.abs(y_mean)>0)

        x_rel[mx]=x_range[mx]/x_mean[mx]
        y_rel[my]=y_range[my]/y_mean[my]

        best_x_idx=int(np.nanargmax(x_rel)) if np.any(np.isfinite(x_rel)) else None
        best_y_idx=int(np.nanargmax(y_rel)) if np.any(np.isfinite(y_rel)) else None

        best_x_rel=float(x_rel[best_x_idx]) if best_x_idx is not None else None
        best_y_rel=float(y_rel[best_y_idx]) if best_y_idx is not None else None

        return {
            "sigx2_range_per_screen": x_range.tolist(),
            "sigy2_range_per_screen": y_range.tolist(),
            "sigx2_rel_range_per_screen": x_rel.tolist(),
            "sigy2_rel_range_per_screen": y_rel.tolist(),
            "best_screen_x": screens[best_x_idx] if best_x_idx is not None else None,
            "best_screen_y": screens[best_y_idx] if best_y_idx is not None else None,
            "best_rel_var_x": best_x_rel,
            "best_rel_var_y": best_y_rel,
            "is_useful_scan": bool(np.isfinite(best_x_rel) and best_x_rel>=threshold) or bool(np.isfinite(best_y_rel) and best_y_rel>=threshold),
            "rel_threshold": threshold,
        }

    def _load_session_em(self):
        self.load_session_settings_quad_scan()
        selected_screens=[it.text() for it in self.screens_list.selectedItems()]
        saved_session=dict(self._quad_scan_session)
        saved_session["screens"]=selected_screens
        self.session=saved_session
        self.session.pop("measured_optics",None) # removes measured optics
        self.session.pop("fit_result_twiss_emit",None)
        self._clear_fit_result_panel()
        QMessageBox.information(self, "Session", "Session loaded.")

    def _fit_emittance_with_model_beta(self):
        if self.session is None:
            QMessageBox.information(self, "Session", "Session not loaded.")
            return
        quad_name=self.session["quadrupoles"][0]
        screens=self.session["screens"]
        K1_values=np.asarray(self.session.get("K1_values",[]),dtype=float)
        sigx=np.asarray(self.session.get("sigx_mean",[]),dtype=float)
        sigy=np.asarray(self.session.get("sigy_mean",[]),dtype=float)

        if len(screens)==0 or len(K1_values)==0 or sigx.ndim!=2 or sigy.ndim!=2:
            QMessageBox.information(self, "Wrong data", "Wrong data detected.")
            return

        steps,nscreens=sigx.shape

        betax=np.full((steps,nscreens),np.nan,dtype=float)
        betay=np.full((steps,nscreens),np.nan,dtype=float)

        quads=self.interface.get_quadrupoles()
        quads_index=quads["names"].index(quad_name)
        K1_after_restoring=float(quads["bdes"][quads_index])

        try:
            for k,K1 in enumerate(K1_values):
                self.interface.set_quadrupoles([quad_name],[float(K1)])
                T=self.interface.lattice.get_transport_table('%S %beta_x %beta_y')
                S_vals=np.asarray(T[:,0],dtype=float)
                betax_vals=np.asarray(T[:,1],dtype=float)
                betay_vals=np.asarray(T[:,2],dtype=float)

                scr=self.interface.get_screens(screens)
                S_of_each_screen=np.asarray(scr["S"],dtype=float)

                for i,s_for_each_screen in enumerate(S_of_each_screen):
                    if not np.isfinite(s_for_each_screen): # checks if thats not nan, -inf, +inf etc
                        continue
                    index=int(np.argmin(np.abs(S_vals-s_for_each_screen))) # because transport table returns S over many elements, and we need only s for each screen
                    betax[k,i]=betax_vals[index]
                    betay[k,i]=betay_vals[index]
        finally:
            self.interface.set_quadrupoles([quad_name],[float(K1_after_restoring)])

        sigx_values=(sigx**2).ravel()
        sigy_values=(sigy**2).ravel()
        betax_values=betax.ravel()[:,None]
        betay_values=betay.ravel()[:,None]

        #Ax=y, eps*beta=sig2

        mx=np.isfinite(sigx_values) & np.isfinite(betax_values[:,0]) # which data is true and which is false
        my=np.isfinite(sigy_values) & np.isfinite(betay_values[:,0])

        eps_x=float(np.linalg.lstsq(betax_values[mx],sigx_values[mx],rcond=None)[0][0])
        eps_y=float(np.linalg.lstsq(betay_values[my],sigy_values[my],rcond=None)[0][0])

        gamma_rel=(self.interface.Pref+self.interface.electronmass)/self.interface.electronmass
        beta_rel=np.sqrt(1-(1/gamma_rel)**2)
        emit_x_norm=gamma_rel*beta_rel*eps_x
        emit_y_norm=gamma_rel*beta_rel*eps_y
        QMessageBox.information(self, "Fit result", f"Emittance_x={emit_x_norm}, Emittance_y={emit_y_norm}.")


    def _get_R_from_twiss_file(self, screen0,screen1,plane):
        '''
        Uses R matrices from the twiss file, not from rft tracking.
        Model can be outdated, twiss file has only nominal R, so for one K1 value.
        If K1 changes, R changes too, but twiss doesn't.
        Therefore, we need to measure the optics.
        '''
        optics=self.interface._get_optics_from_twiss_file(names=[screen0,screen1])
        names=optics["names"]

        if screen0 not in names or screen1 not in names:
            QMessageBox.information(self, "Wrong data", "No such screens in the twiss file.")

        index0=names.index(screen0)
        index1=names.index(screen1)

        if plane=="x":
            beta0, alpha0, mu0 = optics["betx"][index0], optics["alfx"][index0], optics["mux"][index0]
            beta1, alpha1, mu1 = optics["betx"][index1], optics["alfx"][index1], optics["mux"][index1]

        elif plane=="y":
            beta0, alpha0,mu0= optics["bety"][index0], optics["alfy"][index0],optics["muy"][index0]
            beta1, alpha1,mu1= optics["bety"][index1], optics["alfy"][index1],optics["muy"][index1]

        delta_phi_in_rad=2*np.pi *(mu1-mu0)

        def _courant_snyder(beta,alpha): # normalised -> physical coordinates
            return np.asarray([[np.sqrt(beta),0],
                            [-alpha/np.sqrt(beta), 1/np.sqrt(beta)]])

        A0 = _courant_snyder(beta0,alpha0)
        A1 = _courant_snyder(beta1,alpha1)

        rotation= np.array([[np.cos(delta_phi_in_rad),np.sin(delta_phi_in_rad)],
                           [-np.sin(delta_phi_in_rad),np.cos(delta_phi_in_rad)]])

        # R(0->1) = A(1) * Rot * A0^{-1}

        R= A1 @ rotation @ np.linalg.inv(A0)
        return R

    def _get_transport_twiss(self, R, beta0,alpha0):
        gamma0=(1+alpha0**2)/beta0

        R11=R[0,0]
        R12=R[0,1]
        R21=R[1,0]
        R22=R[1,1]

        beta1=R11**2*beta0-2*R11*R12*alpha0+R12**2*gamma0
        alpha1=-R11*R21*beta0+(R11*R22+R12*R21)*alpha0-R12*R22*gamma0
        gamma1=R21**2*beta0-2*R21*R22*alpha0+R22**2*gamma0

        return beta1,alpha1,gamma1

    def _fit_twiss_and_emittance(self):
        if self.session is None:
            QMessageBox.information(self, "Session error.", f"Session not loaded.")
            return
        screens=list(self.session.get("screens",[]))
        # not in the gui selection order
        screens_info=self.interface.get_screens(screens)
        screen_names=list(screens_info["names"])
        screen_S=np.asarray(screens_info["S"],dtype=float)
        order=np.argsort(screen_S)
        screens=[screen_names[i] for i in order]
        sigx=np.asarray(self.session.get("sigx_mean",[]),dtype=float)
        sigy=np.asarray(self.session.get("sigy_mean",[]),dtype=float)

        sigx=sigx[:,order]
        sigy=sigy[:,order]

        if len(screens)<2:
            QMessageBox.information(self, "Data error.", f"Select at least two screens.")
            return
        quad_name=self.session.get("quad_name")

        if quad_name is None:
            quadrupoles=self.session.get("quadrupoles",[])
            if len(quadrupoles)==0:
                QMessageBox.information(self, "Data error.", f"Select at least one quadrupole.")
                return
            quad_name=quadrupoles[0]

        K1_values=np.asarray(self.session.get("K1_values",[]),dtype=float)

        if K1_values.size==0 or sigx.ndim!=2 or sigy.ndim!=2:
            QMessageBox.information(self, "Data error.", f"Session has wrong data.")
            return
        steps,nscreens=sigx.shape

        if sigy.shape!=sigx.shape:
            QMessageBox.information(self, "Data error.", f"Sigx and Sigy have different shape.")
            return
        if nscreens!=len(screens):
            QMessageBox.information(self, "Data error.", f"Number of screens is wrong.")
            return

        measured_optics = self.session.get("measured_optics",[])
        if not measured_optics:
            QMessageBox.information(self, "Data error.", "Measure optics first.")
            return
        screens = list(measured_optics["screens"])
        screen0 = measured_optics["screen0"]
        Rx_list = np.array(measured_optics["Rx_list"],dtype=float)
        Ry_list = np.array(measured_optics["Ry_list"],dtype=float)

        def _beta_from_R(R,beta0,alpha0):
            '''
            What beta value should be at each screen and for each step,
            if initial Twiss parameters are beta0,alpha0,gamma0
            '''
            beta_values=np.full((steps,nscreens),np.nan,dtype=float)
            for k in range(steps):
                for i in range(nscreens):
                    beta_i,alpha_i,gamma_i=self._get_transport_twiss(R[k,i],beta0,alpha0)
                    beta_values[k,i]=beta_i
            return beta_values

        def _fit_per_plane(sig_matrix,R,plane):
            def residuals(params):
                emit_geom, beta0, alpha0 = params
                if emit_geom <= 0 or beta0 <= 0:
                    return np.full(sig_matrix.size, 1e9, dtype=float)  # big error for nonrealistic results

                beta_values = _beta_from_R(R, beta0, alpha0)
                sig2_model = emit_geom * beta_values
                sig2_meas = sig_matrix ** 2
                diff = (sig2_meas - sig2_model).ravel()
                diff[~np.isfinite(diff)] = 1e9
                return diff

            # do the upstream-downstream logic like in bba too

            if plane == 'x':
                x0 = np.array([1e-6, 6.8, 1], dtype=float)  # guessing initial values
            else:
                x0 = np.array([1e-8, 3, -2], dtype=float)

            result = least_squares(residuals, x0, bounds=([1e-12, 0, -20], [np.inf, np.inf, 20]))
            return result

        fit_x = _fit_per_plane(sigx, Rx_list, 'x')
        fit_y = _fit_per_plane(sigy, Ry_list, 'y')

        emit_x_geom, beta_x0, alpha_x0 = fit_x.x  # because optimize returns several parameters and result.x are the fit parameters
        emit_y_geom, beta_y0, alpha_y0 = fit_y.x

        gamma_rel = (self.interface.Pref + self.interface.electronmass) / self.interface.electronmass
        beta_rel = np.sqrt(1 - 1 / (gamma_rel ** 2))

        emit_x_norm = gamma_rel * beta_rel * emit_x_geom
        emit_y_norm = gamma_rel * beta_rel * emit_y_geom

        self.session["fit_result_twiss_emit"] = {
            "screen0": screen0,
            "quad_name": quad_name,
            # "emit_x_geom":emit_x_geom, # mm.rad
            # "emit_y_geom":emit_y_geom, # mm.rad
            "emit_x_norm": emit_x_norm,
            "emit_y_norm": emit_y_norm,
            "beta_x0": beta_x0,
            "beta_y0": beta_y0,
            "alpha_x0": alpha_x0,
            "alpha_y0": alpha_y0,
        }

        self._update_fit_result_panel(self.session["fit_result_twiss_emit"])

    def _measure_optics(self,screens,quad_name,K1_values):
        screens_info=self.interface.get_screens(screens)
        screens_names=list(screens_info["names"])
        screen_S=np.asarray(screens_info["S"],dtype=float)
        order=np.argsort(screen_S)
        screens_sorted=[screens_names[i] for i in order]

        screen0=screens_sorted[0]
        Rx_list=[]
        Ry_list=[]
        quads=self.interface.get_quadrupoles()
        quads_index=quads["names"].index(quad_name)
        K1_after_restoring=float(quads["bdes"][quads_index])

        try:
            for K1 in K1_values:
                self.interface.set_quadrupoles([quad_name],[float(K1)])
                Rx_step=[] # transport matrix for one scan step, per one K1 value
                Ry_step=[] # Rx_list=[Rx_step for K1_1, Rx_step for K1_2, ...]

                for screen in screens_sorted:
                    if screen==screen0:
                        Rx_step.append(np.eye(2,dtype=float))
                        Ry_step.append(np.eye(2,dtype=float))
                    else:
                        Rx_step.append(self._get_transport_matrix(screen0,screen,"x"))
                        Ry_step.append(self._get_transport_matrix(screen0,screen,"y"))

                Rx_list.append(Rx_step)
                Ry_list.append(Ry_step)
        finally:
            self.interface.set_quadrupoles([quad_name],[float(K1_after_restoring)])

        return {
            "screens":screens_sorted,
            "screen0":screen0,
            "Rx_list":np.asarray(Rx_list,dtype=float),
            "Ry_list":np.asarray(Ry_list,dtype=float),
        }

    def _run_measure_optics(self):
        if self.session is None:
            QMessageBox.information(self, "Error", "No session selected")
            return
        screens=list(self.session.get("screens",[]))
        if len(screens)<2:
            QMessageBox.information(self, "Error", "Select at least two screens")
            return
        quad_name=self.session.get("quad_name")
        if quad_name is None:
            quadrupoles=self.session.get("quadrupoles",[])
            if len(quadrupoles)==0:
                QMessageBox.information(self, "Error", "No quadrupole selected")
                return
            quad_name=quadrupoles[0]
        K1_values=np.asarray(self.session.get("K1_values",[]),dtype=float)
        if K1_values.size==0:
            QMessageBox.information(self, "Error", "No K1 values selected")
            return
        optics=self._measure_optics(screens,quad_name,K1_values)
        self.session["measured_optics"]={
            "screen0":optics["screen0"],
            "screens":optics["screens"],
            "Rx_list":optics["Rx_list"].tolist(),
            "Ry_list":optics["Ry_list"].tolist(),
            "K1_values":K1_values.tolist(),
        }
        self.session["fit_result_twiss_emit"]=None
        self._clear_fit_result_panel()
        QMessageBox.information(self, "Done", "Measurement done")
    def _get_transport_matrix(self,screen0,screen1,plane):
        try:
            B0=self.interface.lattice[screen0].get_bunch()
            B1=self.interface.lattice[screen1].get_bunch()
        except Exception:
            raise RuntimeError("Cannot get bunch from lattice")
        if plane == "x":
            M0=B0.get_phase_space('%x %xp')
            M1=B1.get_phase_space('%x %xp')
        elif plane == "y":
            M0=B0.get_phase_space('%y %yp')
            M1=B1.get_phase_space('%y %yp')
        else:
            raise RuntimeError("Cannot get phase space from lattice")
        M0=np.asarray(M0,dtype=float)
        M1=np.asarray(M1,dtype=float)

        n=min(len(M0),len(M1))
        M0=M0[:n,:]
        M1=M1[:n,:]

        mask=np.all(np.isfinite(M0),axis=1) & np.all(np.isfinite(M1),axis=1)
        M0=M0[mask]
        M1=M1[mask]
        R=np.linalg.lstsq(M0,M1,rcond=None)[0].T
        return R

if __name__ == "__main__":
    app = QApplication(sys.argv)

    import SelectInterface
    dialog = SelectInterface.choose_acc_and_interface()
    if dialog is None:
        print("Selection cancelled.")
        sys.exit(1)

    I = dialog
    project_name = I.get_name() if hasattr(I, "get_name") else type(I).__name__
    print(f"Selected interface: {project_name}")

    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"~/flight-simulator-data/EM_{project_name}_{time_str}_session"
    dir_name = os.path.expanduser(os.path.expandvars(dir_name))

    w = MainWindow(interface=I, dir_name=dir_name)
    w.show()
    sys.exit(app.exec())