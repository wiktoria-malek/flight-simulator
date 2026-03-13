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

        self._save_session_quad_scan(delta_min=min_delta,delta_max=max_delta,steps=steps,nshots=nshots,quad_name=quad_name,K1_0=initial_K1_0,sigx_mean=sigx_mean,sigy_mean=sigy_mean,sigx_std=sigx_std,sigy_std=sigy_std,deltas=deltas,K1_values=K1_values)

    def _load_session_em(self):
        self.load_session_settings_quad_scan()
        selected_screens=[it.text() for it in self.screens_list.selectedItems()]
        saved_session=dict(self._quad_scan_session)
        saved_session["screens"]=selected_screens
        self.session=saved_session
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


    def _get_transport_matrix(self, screen0,screen1,plane):
        try:
            B0=self.interface.lattice[screen0].get_bunch()
            B1=self.interface.lattice[screen1].get_bunch()
        except Exception as e:
            raise RuntimeError(f"Cannot access screen {screen0} or {screen1}. {e}")
        if plane == "x":
            M0=B0.get_phase_space('%x %xp')
            M1=B1.get_phase_space('%x %xp')

        elif plane == "y":
            M0=B0.get_phase_space('%y %yp')
            M1=B1.get_phase_space('%y %yp')

        M0=np.asarray(M0,dtype=float)
        M1=np.asarray(M1,dtype=float)

        # using the same number of particles for both screens
        n=min(len(M0),len(M1))
        M0=M0[:n,:]
        M1=M1[:n,:]

        # filtering
        filtering=np.all(np.isfinite(M0),axis=1) & np.all(np.isfinite(M1),axis=1)
        M0=M0[filtering]
        M1=M1[filtering]

        R=np.linalg.lstsq(M0,M1,rcond=None)[0].T
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
        #sigx=np.asarray(self.session.get("sigx_mean",[]),dtype=float)
        #sigy=np.asarray(self.session.get("sigy_mean",[]),dtype=float)

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

        screen0=screens[0]
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

                for screen in screens:
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
        Rx_list=np.asarray(Rx_list,dtype=float)
        Ry_list=np.asarray(Ry_list,dtype=float)


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
                emit_geom,beta0,alpha0=params
                if emit_geom<=0 or beta0<=0:
                    return np.full(sig_matrix.size,1e9,dtype=float) # big error for nonrealistic results

                beta_values=_beta_from_R(R,beta0,alpha0)
                sig2_model=emit_geom*beta_values
                sig2_meas=sig_matrix**2
                diff=(sig2_meas-sig2_model).ravel()
                diff[~np.isfinite(diff)]=1e9
                return diff

            # do the upstream-downstream logic like in bba too

            if plane=='x':
                x0=np.array([1e-6,6.8,1],dtype=float) # guessing initial values
            else:
                x0=np.array([1e-8,3,-2],dtype=float)

            result = least_squares(residuals,x0,bounds=([1e-12,0,-20],[np.inf,np.inf,20]))
            return result
        fit_x=_fit_per_plane(sigx,Rx_list,'x')
        fit_y=_fit_per_plane(sigy,Ry_list,'y')

        emit_x_geom,beta_x0,alpha_x0=fit_x.x # because optimize returns several parameters and result.x are the fit parameters
        emit_y_geom,beta_y0,alpha_y0=fit_y.x

        gamma_rel=(self.interface.Pref+self.interface.electronmass)/self.interface.electronmass
        beta_rel=np.sqrt(1-1/(gamma_rel**2))

        emit_x_norm=gamma_rel*beta_rel*emit_x_geom
        emit_y_norm=gamma_rel*beta_rel*emit_y_geom

        self.fit_result_twiss_emit={
            "screen0": screen0,
            "quad_name":quad_name,
            #"emit_x_geom":emit_x_geom, # mm.rad
            #"emit_y_geom":emit_y_geom, # mm.rad
            "emit_x_norm":emit_x_norm,
            "emit_y_norm":emit_y_norm,
            "beta_x0":beta_x0,
            "beta_y0":beta_y0,
            "alpha_x0":alpha_x0,
            "alpha_y0":alpha_y0,
        }
        pprint.pp(self.fit_result_twiss_emit)




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