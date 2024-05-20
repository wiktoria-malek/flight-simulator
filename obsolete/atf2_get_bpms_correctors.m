function state = atf2_get_bpms_correctors(state,nSamples)

if nargin < 2
    warning('using nSample = 20')
    nSamples = 20;
end

state = atf2_get_correctors(state);
state = atf2_get_bpms(state,nSamples);
