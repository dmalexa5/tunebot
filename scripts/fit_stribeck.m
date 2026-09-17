function result = fit_stribeck(txfGlob, settle_s)
%FIT_STRIBECK Fit the steady-state Stribeck curve to a set of velocity-hold
%captures (tune-friction Test 1).
%   result = FIT_STRIBECK('traces/j1-friction-tune/vstep.*.txf')
%
%   Each match is a signal_step capture (mode=vel) from run-step.sh: pad,
%   hold at a commanded velocity, fall back. At steady state (dz/dt = 0)
%   the LuGre ODE's z term reduces to g(w)/sigma0, so the measured current
%   collapses to
%       I_ss(w) = Ic + (Is - Ic)*exp(-(w/ws)^2) + sig2*w
%   independent of sig0 -- consistent with Test 1 not targeting sig0.
%   Fit via lsqcurvefit (nonlinear least squares).
%
%   Steady-state velocity/current per capture are the mean of vel_fbk/
%   iq_fbk over the hold window (skipping the fixed 20-sample
%   baseline/tail run-step.sh's start_pad/end_pad produce), after
%   discarding an initial SETTLE_S of the hold to clear the velocity loop's
%   transient -- empirically ~300 ms on j1 (a 100 mrad/s probe showed 51%
%   overshoot and a slowly-decaying oscillation, not a clean fast settle),
%   not the fixed-length baseline/tail's few-sample edge.

if nargin < 2 || isempty(settle_s), settle_s = 0.3; end

files = dir(txfGlob);
assert(~isempty(files), 'fit_stribeck: no captures matched %s', txfGlob);

w = zeros(numel(files), 1);
I = zeros(numel(files), 1);
for k = 1:numel(files)
    txfDir = fullfile(files(k).folder, files(k).name);
    [w(k), I(k)] = hold_steady_state(txfDir, settle_s);
end
[w, order] = sort(w);
I = I(order);

model = @(p, w) p(1) + (p(2) - p(1)) .* exp(-(w ./ p(3)) .^ 2) + p(4) .* w;
p0 = [min(I), max(I), median(abs(w(w ~= 0))), 0];
lb = [0, 0, eps, -Inf];
ub = [Inf, Inf, Inf, Inf];

opts = optimoptions('lsqcurvefit', 'Display', 'off');
[p, resnorm, residual] = lsqcurvefit(model, p0, w, I, lb, ub, opts);

result = struct('Ic', p(1), 'Is', p(2), 'stribeck_vel', p(3), 'sig2', p(4), ...
    'resnorm', resnorm, 'residual', residual, 'w', w, 'I', I);

fprintf('Ic           = %.6f A\n', result.Ic);
fprintf('Is           = %.6f A\n', result.Is);
fprintf('stribeck_vel = %.6f rad/s\n', result.stribeck_vel);
fprintf('sig2         = %.6f A/(rad/s)\n', result.sig2);
fprintf('resnorm      = %.6g (n=%d captures)\n', result.resnorm, numel(w));
end

function [vel_ss, iq_ss] = hold_steady_state(txfDir, settle_s)
[data, dt] = txf_load(txfDir);
n = numel(data.vel_fbk);
EDGE = 20;
assert(n > 2 * EDGE, 'hold_steady_state: %s too short (%d samples)', txfDir, n);
holdStart = EDGE + 1;
holdEnd = n - EDGE;
idxStart = holdStart + round(settle_s / dt);
assert(idxStart < holdEnd, ...
    'hold_steady_state: %s hold too short for a %.0f ms settle skip', txfDir, settle_s * 1e3);
idx = idxStart:holdEnd;
vel_ss = mean(data.vel_fbk(idx));
iq_ss = mean(data.iq_fbk(idx));
end
