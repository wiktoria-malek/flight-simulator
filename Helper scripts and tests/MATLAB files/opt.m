%% Load RF_Track
RF_Track;

%% Define reference particle, and rigidity
Part.mass = RF_Track.electronmass; % MeV/c^2
Part.P = 100; % MeV/c
Part.Q = -1; % e+
B_rho = Part.P / Part.Q; % MV/c, reference rigidity

%% FODO cell with Lcell = 2 m, Lq = 24 cm, Ld = 76 cm, mu = 90 degress
Lcell = 2; % m
Lquad = 0.01; % m
mu = 90; % deg

% focusing params
k1L = sind(mu/2) / (Lcell/4); % 1/m
strength = k1L * B_rho; % MeV/m
gradient = strength / Lquad * 1e6 / RF_Track.clight; % T/m = V/m/m/c

%% Lattice
Qf = Quadrupole(Lquad/2,  strength/2);
QD = Quadrupole(Lquad, -strength);
D  = Drift(Lcell/2 - Lquad);

FODO = Lattice();
FODO.append(Qf);
FODO.append(Screen());
FODO.append(D);
FODO.append(QD);
FODO.append(Screen());
FODO.append(D);
FODO.append(Qf);
FODO.append(Screen());

%% Bunch
Nparticles = 10000;
Twiss = Bunch6d_twiss();
Twiss.emitt_x = 1; % mm.mrad normalised emittance
Twiss.emitt_y = 1; % mm.mrad
Twiss.beta_x = Lcell * (1 + sind(mu/2)) / sind(mu); % m
Twiss.beta_y = Lcell * (1 - sind(mu/2)) / sind(mu); % m
Twiss.alpha_x = 0;
Twiss.alpha_y = 0;
B0 = Bunch6d_QR (Part.mass, 0.0, Part.Q, Part.P, Twiss, Nparticles, -1);

B1 = FODO.track(B0);

function S_ = eval_response(FODO, B0)
    Q = FODO.get_quadrupoles();
    S_ = [];
    for s = Q{1}.get_strength() * linspace(0.8, 1.2, 11)
        s0 = Q{1}.get_strength();
        Q{1}.set_strength(s);
        B1 = FODO.track(B0);
        S = Q{1}.get_strength();
        for B = FODO.get_bunch_at_screens()
            S(end+1) = B{1}.get_info().sigma_x;
            S(end+1) = B{1}.get_info().sigma_y;
        end
        S_(end+1,:) = S;
        Q{1}.set_strength(s0);
    end
endfunction

S_ref = eval_response(FODO, B0)

%% Part 1, measures the twiss parameters and emittances

function M = merit(X, S_ref, FODO)
    
    RF_Track;
    
    emitt = constrain(X(1), 0, 5);
    betax = constrain(X(2), 0, 5);
    betay = constrain(X(3), 0, 5);
    alphax = constrain(X(4), -5, 5);
    alphay = constrain(X(5), -5, 5);
    
    %% Define reference particle, and rigidity
    Part.mass = RF_Track.electronmass; % MeV/c^2
    Part.P = 100; % MeV/c
    Part.Q = -1; % e+
    B_rho = Part.P / Part.Q; % MV/c, reference rigidity
    
    Nparticles = 10000;
    Twiss = Bunch6d_twiss();
    Twiss.emitt_x = emitt; % mm.mrad normalised emittance
    Twiss.emitt_y = emitt; % mm.mrad
    Twiss.beta_x = betax; % m
    Twiss.beta_y = betay; % m
    Twiss.alpha_x = alphax;
    Twiss.alpha_y = alphay;
    B0 = Bunch6d_QR (Part.mass, 0.0, Part.Q, Part.P, Twiss, Nparticles, -1);
    
    S = eval_response(FODO, B0);
    
    M = sumsq(S(:) - S_ref(:))
    
end

X = fminsearch(@(X) merit(X, S_ref, FODO), zeros(1,5));

emitt = constrain(X(1), 0, 5)
betax = constrain(X(2), 0, 5)
betay = constrain(X(3), 0, 5)
alphax = constrain(X(4), -5, 5)
alphay = constrain(X(5), -5, 5)

%% Part 2, infers also the first quadrupole strength

function M = merit(X, S_ref, FODO)
    
    RF_Track;
    
    emitt = constrain(X(1), 0, 5);
    betax = constrain(X(2), 0, 5);
    betay = constrain(X(3), 0, 5);
    alphax = constrain(X(4), -5, 5);
    alphay = constrain(X(5), -5, 5);
    strength = constrain(X(6), -200, 0)

    %% Define reference particle, and rigidity
    Part.mass = RF_Track.electronmass; % MeV/c^2
    Part.P = 100; % MeV/c
    Part.Q = -1; % e+
    B_rho = Part.P / Part.Q; % MV/c, reference rigidity
    
    Nparticles = 10000;
    Twiss = Bunch6d_twiss();
    Twiss.emitt_x = emitt; % mm.mrad normalised emittance
    Twiss.emitt_y = emitt; % mm.mrad
    Twiss.beta_x = betax; % m
    Twiss.beta_y = betay; % m
    Twiss.alpha_x = alphax;
    Twiss.alpha_y = alphay;
    B0 = Bunch6d_QR (Part.mass, 0.0, Part.Q, Part.P, Twiss, Nparticles, -1);
    
    Q = FODO.get_quadrupoles();
    Q{1}.set_strength(strength);
        
    S = eval_response(FODO, B0);
    
    M = sumsq(S(:) - S_ref(:))
    
end

X = fminsearch(@(X) merit(X, S_ref, FODO), zeros(1,6));

expected_strength = strength/2

emitt = constrain(X(1), 0, 5)
betax = constrain(X(2), 0, 5)
betay = constrain(X(3), 0, 5)
alphax = constrain(X(4), -5, 5)
alphay = constrain(X(5), -5, 5)
strength = constrain(X(6), -200, 0)
