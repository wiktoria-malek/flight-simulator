function state = atf2_get_bpms(state,nSamples)

if nargin < 2
    warning('using nSample = 20')
    nSamples = 20;
end

%nSamples = 1;
nBpms = 57;
chargeCutValue = 100; % REFC1:amp
nrCutPulses = 0; % counter

system(['caget -# ' num2str(nBpms) ' atf2:name > /tmp/bba_caget.txt']);
line = textread('/tmp/bba_caget.txt', '%s', 'delimiter', '');
line = line{1};
[token,line] = strtok(line);
[token,line] = strtok(line);

[names,Z] = textread('bpmcorr.txt', '%s %f');

if strcmp(token, num2str(nBpms))

  state.bpms.name = cell(nBpms,1);
  state.bpms.X = zeros(nBpms, nSamples);
  state.bpms.Y = zeros(nBpms, nSamples);
  state.bpms.Z = zeros(nBpms, 1);
  state.bpms.TMIT = zeros(nBpms, nSamples);

  %% get bpm names
  for ibpm = 1:nBpms
    [name,line] = strtok(line);
    index = find(fnmatch(name, names));
    if numel(index) == 0
        error(['bpm ''' name ''' not found in file bpmcorr.txt!'])
    end
    state.bpms.name{ibpm} = name;
    state.bpms.Z(ibpm) = Z(index);
  end

  for isample = 1:nSamples
    system(['caget -# ' num2str(nBpms) ' -f 8 REFC1:amp BIM:EXT:nparticles atf2:xpos atf2:ypos > /tmp/bba_caget.txt']);
    line = textread('/tmp/bba_caget.txt', '%s', 'delimiter', '');
    line1 = line{1}; % REFC1:amp
    line2 = line{2}; % BIM:EXT:nparicles
    line3 = line{3}; % atf2:xpos
    line4 = line{4}; % atf2:ypos
    [token,line1] = strtok(line1);
    [token,line1] = strtok(line1);
    [token,line2] = strtok(line2);
    [token,line2] = strtok(line2);
    [token,line3] = strtok(line3);
    [token,line3] = strtok(line3);
    [token,line4] = strtok(line4);
    [token,line4] = strtok(line4);

    [token,line1] = strtok(line1);
    charge = str2num(token);

    if (charge < chargeCutValue) %Charge Cut 
        if (nrCutPulses < 10)
            warning('beam was lost, skipping pulse!');
            nSamples = nSamples + 1;
            nrCutPulses = nrCutPulses + 1;
            continue
        else
            warning('beam was lost again, but giving up on skipping pulses');
        end
    end
        
    for ibpm = 1:nBpms
      [token3,line3] = strtok(line3);
      [token4,line4] = strtok(line4);
      state.bpms.TMIT(ibpm, isample) = charge;
      state.bpms.X(ibpm, isample) = str2num(token3);
      state.bpms.Y(ibpm, isample) = str2num(token4);
    end
  end
  
  [Z,I] = sort(state.bpms.Z);
  
  state.bpms.name = state.bpms.name(I);
  state.bpms.X = state.bpms.X(I,:);
  state.bpms.Y = state.bpms.Y(I,:);
  state.bpms.Z = state.bpms.Z(I);
  state.bpms.TMIT = state.bpms.TMIT(I,:);  

else
  error('uncorrect number of bpms read from caget!');
end
