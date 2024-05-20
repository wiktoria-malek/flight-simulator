function state = atf2_get_correctors(state)

[names,Z] = textread('bpmcorr.txt', '%s %f');

indexes = find(fnmatch('Z*', names));

nCorrs = numel(indexes);

system([ 'caget -f 15 ' ...
 strjoin(strcat(names(indexes), ':currentRead'), ' ') ' ' ...
 strjoin(strcat(names(indexes), ':currentWrite'), ' ') ' > /tmp/bba_caget.txt' ]);

[name,value] = textread('/tmp/bba_caget.txt', '%s %f');

state.mags.name = cell(nCorrs,1);
state.mags.Z = zeros(nCorrs,1);
state.mags.BDES = zeros(nCorrs,1);
state.mags.BACT = zeros(nCorrs,1);

%%%

state.mags.name = names(indexes);
state.mags.Z = Z(indexes);

for icorr=1:nCorrs
  state.mags.BACT(icorr) = value(icorr);
  state.mags.BDES(icorr) = value(icorr+nCorrs);
end

[Z,I] = sort(state.mags.Z);
  
state.mags.name = state.mags.name(I);
state.mags.BDES = state.mags.BDES(I);
state.mags.BACT = state.mags.BACT(I);
state.mags.Z = state.mags.Z(I);
 
