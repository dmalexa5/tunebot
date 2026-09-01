function result = fit_lugre_joint(csvFiles, Ic, Is, stribeck_vel, p0, fs_ode)
%FIT_LUGRE_JOINT Jointly fit sig0, sig1, sig2 by simulating the LuGre ODE
%against the Test 2 presliding traces and Test 3 dither data
%(tune-friction Test 3), via lsqnonlin.
%   result = FIT_LUGRE_JOINT(csvFiles, Ic, Is, stribeck_vel)
%
%   csvFiles: cellstr of (t, w, iq) CSV paths -- the presliding segments
%   from txf-breakaway.py and the dither captures from txf-export-csv.py.
%   Ic, Is, stribeck_vel come from fit_stribeck (Test 1) and are held
%   fixed here.

if nargin < 5 || isempty(p0), p0 = [1, 0.01, 0.001]; end
if nargin < 6 || isempty(fs_ode), fs_ode = 20e3; end

trials = cell(numel(csvFiles), 1);
for k = 1:numel(csvFiles)
    tbl = readtable(csvFiles{k});
    trials{k} = struct('t', tbl.t, 'w', tbl.w, 'iq', tbl.iq);
end

resFun = @(p) residuals(p, trials, Ic, Is, stribeck_vel, fs_ode);
lb = [0, 0, -Inf];
ub = [Inf, Inf, Inf];
opts = optimoptions('lsqnonlin', 'Display', 'iter');
[p, resnorm] = lsqnonlin(resFun, p0, lb, ub, opts);

result = struct('sig0', p(1), 'sig1', p(2), 'sig2', p(3), 'resnorm', resnorm);
fprintf('sig0 = %.6f\n', result.sig0);
fprintf('sig1 = %.6f\n', result.sig1);
fprintf('sig2 = %.6f  (refined jointly with sig0/sig1)\n', result.sig2);
fprintf('resnorm = %.6g (n=%d trials)\n', result.resnorm, numel(trials));
end

function r = residuals(p, trials, Ic, Is, ws, fs_ode)
sig0 = p(1); sig1 = p(2); sig2 = p(3);
r = [];
for k = 1:numel(trials)
    tr = trials{k};
    I_pred = lugre_predict(tr.t, tr.w, sig0, sig1, sig2, Ic, Is, ws, fs_ode);
    r = [r; I_pred - tr.iq]; %#ok<AGROW>
end
end
