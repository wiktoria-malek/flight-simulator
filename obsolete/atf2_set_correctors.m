function state = atf2_set_correctors(corr_names, corr_values)

[names,Z] = textread('bpmcorr.txt', '%s %f');

indexes = [];
for i=1:numel(corr_names)
  index = find(strcmp(names, corr_names(i)));
  if numel(index) == 0
    error(['corrector ''' corr_names{i} ''' not found']);
  end
  indexes = [ indexes ; index ];
end

nCorrs = numel(indexes);

if numel(indexes) ~= numel(corr_names)
   error('some corrector names not found!'); 
end

% set correctors
for icorr=1:nCorrs
    pv_name = strcat(names(indexes(icorr)), ':currentWrite ');
    system(strjoin(['caput' pv_name num2str(corr_values(icorr))], ' '));
    pause(0.5);
end

pause(1);
