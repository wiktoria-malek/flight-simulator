I = load('input_2000.txt');
O = load('output_2000.txt');

mass = 0.510998950000000; % MeV/c^3
momentum = 1300; % MeV/c

beta_gamma = momentum / mass;

emitt_x = I(:,1) / beta_gamma; % mm.mrad, geometric emittance
emitt_y = I(:,4) / beta_gamma; % mm.mrad, geometric emittance
beta_x = I(:,2);
beta_y = I(:,5);
alpha_x = I(:,3);
alpha_y = I(:,6);

S1_x = O(:,1); % mm
S1_y = O(:,2);
S2_x = O(:,3);
S2_y = O(:,4);
S3_x = O(:,5);
S3_y = O(:,6);
S4_x = O(:,7);
S4_y = O(:,8);

gamma_x = (1 + alpha_x.^2) ./ beta_x;
gamma_y = (1 + alpha_y.^2) ./ beta_y;

I = ones(size(I,1),1);

Cx = [ beta_x .* emitt_x, -alpha_x .* emitt_x, gamma_x .* emitt_x, I ];
Cy = [ beta_y .* emitt_y, -alpha_y .* emitt_y, gamma_y .* emitt_y, I ];

Bx = [ S1_x, S2_x, S3_x, S4_x ].^2;
By = [ S1_y, S2_y, S3_y, S4_y ].^2;

Rx = (Bx') / (Cx');
Ry = (By') / (Cy');