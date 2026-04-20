# Emittance Measurement Application
---

# 1. Backend

The application currently has two steps:

## Step 1  - beam-size-based emittance reconstruction
This is the main emittance workflow:

1. Do a **quadrupole scan**.
2. Measure beam sizes on screens for each quadrupole setting.
3. Infer optics at the reference screen and transport to downstream screens.
4. With those optics/transport fixed, fit the emittance.

## Step 2 - trajectory-response-based transport inference
Testing the new approach where:

1. For a few quadrupole settings, excite correctors by `+Δ` and `-Δ`.
2. Measure centroid response on screens and BPMs.
3. Build response matrices.
4. Fit monitor optics from those response matrices.
5. Convert the fitted optics on screens into `R11`, `R12`.

At the moment, the **main final emittance fit** uses the optics/transport handed to it from step 1.

---

# 2. Measurements

## 2.1 Beam-size scan data
For each quadrupole setting `K1_values[k]` and each screen `screens[i]`, the application stores:

- `sigx_mean[k, i]`
- `sigy_mean[k, i]`
- `sigx_std[k, i]`
- `sigy_std[k, i]`

These are the measured beam sizes and their spread.

In the fit, the code works with beam size squared:

$$
\sigma_x^2(k,i), \qquad \sigma_y^2(k,i)
$$

computed as

$$
\sigma^2 = \sigma^2_{\text{measured}}.
$$

The uncertainty used in the residuals is calculated as

$$
\Delta(\sigma^2) \approx 2\,|\sigma|\,|\Delta \sigma|.
$$
---

## 2.2 Trajectory response data
For measured transport, the code excites correctors and measures monitor response.

For each selected quadrupole setting, and for each corrector \(c\), the code applies:

- $$(+\Delta \theta_c)$$
- $$(-\Delta \theta_c\)$$

and measures the resulting centroids on:

- screens
- BPMs

The response is computed by the difference:

$$
\frac{\partial x_j}{\partial \theta_c}
\approx
\frac{x_j(+\Delta \theta_c)-x_j(-\Delta \theta_c)}{2\Delta \theta_c},
$$

$$
\frac{\partial y_j}{\partial \theta_c}
\approx
\frac{y_j(+\Delta \theta_c)-y_j(-\Delta \theta_c)}{2\Delta \theta_c}.
$$

This produces the data:

- `raw_Rxx`
- `raw_Ryy`
- `raw_bpm_Rxx`
- `raw_bpm_Ryy`

where each array is indexed by:
- quadrupole setting,
- monitor,
- corrector.
---

# 3. Beam matrix formula

The transverse beam matrix at the reference screen is written as

$$
\Sigma_0(K)=
\varepsilon
\begin{pmatrix}
\beta_0(K) & -\alpha_0(K) \\
-\alpha_0(K) & \gamma_0(K)
\end{pmatrix},
$$

with

$$
\gamma_0(K)=\frac{1+\alpha_0(K)^2}{\beta_0(K)}.
$$
The individual entries are:

$$
\Sigma_{11} = \varepsilon \beta,
\qquad
\Sigma_{12} = -\varepsilon \alpha,
\qquad
\Sigma_{22} = \varepsilon \gamma.
$$
---

# 4. Propagation to downstream screens

If the transport from the reference screen to screen \(i\) is

$$
R_i=
\begin{pmatrix}
R_{11,i} & R_{12,i} \\
R_{21,i} & R_{22,i}
\end{pmatrix},
$$

then the propagated beam matrix is

$$
\Sigma_i(K)=R_i\,\Sigma_0(K)\,R_i^T.
$$

The measured beam size squared at that screen is the \((1,1)\) element:

$$
\sigma_i^2(K)=\Sigma^{(i)}_{11}(K).
$$

Expanding this gives the main formula used by the application:

$$
\sigma_i^2(K)
=
\varepsilon
\left(
R_{11,i}^2\beta_0(K)
-2R_{11,i}R_{12,i}\alpha_0(K)
+R_{12,i}^2\gamma_0(K)
\right).
$$

For the reference screen itself, the application uses

$$
\sigma_0^2(K)=\varepsilon\,\beta_0(K).
$$

That is because at the reference screen the beam size squared is simply \(\Sigma_{11}\).

---

# 6. Step 1 in the application: `MeasureOptics`

The job of `MeasureOptics` is to infer optics at the reference screen and define downstream transport.

It does **not** yet perform the final emittance fit in the same way as the final GUI step.

## 6.1 Parametrization of Twiss vs quadrupole setting
In `MeasureOptics`, the Twiss parameters at the reference screen are parametrized as smooth functions of the scan variable:

$$
\Delta K = K - K_{\text{nom}}.
$$

Then

$$
\beta_0(K)=\exp(p_0+p_1\Delta K+p_2\Delta K^2),
$$

$$
\alpha_0(K)=a_0+a_1\Delta K+a_2\Delta K^2.
$$

The corresponding Twiss gamma is

$$
\gamma_0(K)=\frac{1+\alpha_0(K)^2}{\beta_0(K)}.
$$

The exponential guarantees that

$$
\beta_0(K) > 0
$$

for all fit parameters, which avoids negative beta values during optimization.

# 7. Approach used in `MeasureOptics`

In `MeasureOptics`, the code does **not** directly fit emittance in the same way as the final GUI fit.

Instead, for each scan point \(K_k\), it uses the measured reference-screen size

$$
\sigma_0^2(K_k)
$$

as a known value.

Since

$$
\sigma_0^2(K_k)=\varepsilon\beta_0(K_k),
$$

one can rewrite the downstream screen model as

$$
\sigma_i^2(K_k)
=
c_i\,\sigma_0^2(K_k)\,
\frac{
R_{11,i}^2\beta_0(K_k)
-2R_{11,i}R_{12,i}\alpha_0(K_k)
+R_{12,i}^2\gamma_0(K_k)
}{
\beta_0(K_k)
}.
$$

---

# 9. Merit function in `MeasureOptics`

## 9.1 Data residuals
For downstream screens:

$$
r^{\text{data}}_{k,i} = \frac{ \sigma^2_{\text{model},k,i}-
\sigma^2_{\text{meas},k,i}
}{
\Delta \sigma^2_{k,i}
}.
$$

- $$(\sigma^2_{\text{model},k,i})$$ is the value predicted by the beam-matrix formula,
- $$(\sigma^2_{\text{meas},k,i})$$ is the measured beam size squared,
- $$(\Delta \sigma^2_{k,i})$$ is the propagated uncertainty from the screen beam-size measurement.

## 9.3 Relation with model Twiss file
If model optics is available at the reference screen, the fit adds soft priors to keep the solution from wandering too far from the model starting point.

So the fit uses model at the beigging, thus it is not purely model-free.

# 10. Final step in the GUI: fit emittance only

After `MeasureOptics` has provided:

- `beta0_measured[k]`
- `alpha0_measured[k]`
- `transport_params`
- `screen_scale_params`

the GUI runs a final per-plane fit.

At this stage:

$$
\beta_0(K_k),\quad \alpha_0(K_k),\quad \gamma_0(K_k),\quad R_{11,i},R_{12,i}
$$

are treated as known.

Then the only unknown is the emittance:

$$
\varepsilon.
$$

The final model is

$$
\sigma_0^2(K_k)=\varepsilon\,\beta_0(K_k),
$$

$$
\sigma_i^2(K_k)=
\varepsilon\,c_i
\left(
R_{11,i}^2\beta_0(K_k)
-2R_{11,i}R_{12,i}\alpha_0(K_k)
+R_{12,i}^2\gamma_0(K_k)
\right).
$$

So the final least-squares in the GUI is a **one-parameter fit per plane**:
- one parameter for \(x\)-plane emittance,
- one parameter for \(y\)-plane emittance.

---

# 11. Merit function in the GUI

The final fit residuals are conceptually

$$
r_{k,i} = \frac{ \sigma^2_{\text{model},k,i}-
\sigma^2_{\text{meas},k,i}
}{
\Delta \sigma^2_{k,i}
}.
$$

The solver minimizes a weighted least-squares quantity, i.e. a \(\chi^2\)-like objective:

$$
\chi^2 = \sum_{k,i} r_{k,i}^2.
$$

## 12.1 Model transport
If `transport_source="model"`, then `MeasureOptics` computes `R11` and `R12` from Twiss-file optics.

From screen optics:

- \(\beta_0,\alpha_0,\mu_0\) at the reference screen
- \(\beta_i,\mu_i\) at downstream screen \(i\)

the code uses

$$
R_{11}^{0\to i}
=
\sqrt{\frac{\beta_i}{\beta_0}}
\left(
\cos \Delta\mu + \alpha_0 \sin \Delta\mu
\right),
$$

$$
R_{12}^{0\to i}
=
\sqrt{\beta_i\beta_0}\,\sin \Delta\mu,
$$

with

$$
\Delta\mu = 2\pi(\mu_i-\mu_0).
$$

This is exactly what `_get_model_transport_params(...)` computes.

## 12.2 Measured fitted transport
If you use the trajectory-response machinery, the code attempts to infer monitor optics from response matrices, then computes `R11`, `R12` from the fitted optics on the screens using the same formulas above.

So in both cases the final formulas for `R11`, `R12` are the same; what changes is **where the optics comes from**.

---

# 13. Obtainging rajectory-response

This is the logic implemented in `MeasureTrajectoryResponse.py`.

## 13.1 Excitation
For a few selected quadrupole settings, the application excites correctors as a test:

$$
+\Delta \theta_c,\qquad -\Delta \theta_c.
$$

The quadrupole itself is not the object of the response matrix excitation. The quadrupole scan only defines which optics point you are sitting at when you measure the corrector response.

For each corrector :
- screen centroid response is measured
- BPM orbit response is measured

Finite differences give the response matrices.

## 13.3 What model is fitted?
The measured transport fit uses a model of the form

$$
M_{jc}^{\text{model}}
=
A_c \sqrt{\beta_j}\,\sin\!\big(2\pi(\mu_j-\phi_c)\big),
$$

where:
- \(j\) labels the monitor,
- \(c\) labels the corrector,
- \(A_c\) is a corrector amplitude parameter,
- \(\phi_c\) is a corrector phase parameter,
- \(\beta_j,\mu_j\) are the monitor optics.

The result is:
- fitted \(\beta\), \(\alpha\), \(\mu\) on monitors,
- extracted \(\beta,\alpha,\mu\) on screens,
- then converted into `R11`, `R12`.

# 17. The general equations used

## Beam matrix at reference screen
$$
\Sigma_0(K)=
\varepsilon
\begin{pmatrix}
\beta_0(K) & -\alpha_0(K) \\
-\alpha_0(K) & \gamma_0(K)
\end{pmatrix},
\qquad
\gamma_0(K)=\frac{1+\alpha_0(K)^2}{\beta_0(K)}.
$$

## Propagation
$$
\Sigma_i(K)=R_i\Sigma_0(K)R_i^T.
$$

## Screen beam size formula
$$
\sigma_i^2(K)
=
\varepsilon
\left(
R_{11,i}^2\beta_0(K)
-2R_{11,i}R_{12,i}\alpha_0(K)
+R_{12,i}^2\gamma_0(K)
\right).
$$

## Reference screen beam size
$$
\sigma_0^2(K)=\varepsilon\beta_0(K).
$$

## Model transport from fitted/model Twiss
$$
R_{11}^{0\to i}
=
\sqrt{\frac{\beta_i}{\beta_0}}
\left(
\cos \Delta\mu + \alpha_0 \sin \Delta\mu
\right),
$$

$$
R_{12}^{0\to i}
=
\sqrt{\beta_i\beta_0}\,\sin \Delta\mu.
$$

## Merit function (final fit)
$$
r_{k,i}  =  \frac{  \sigma^2_{\text{model},k,i}-
\sigma^2_{\text{meas},k,i}
}{
\Delta \sigma^2_{k,i}
},
\qquad
\chi^2 = \sum_{k,i} r_{k,i}^2.
$$

