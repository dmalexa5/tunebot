function I_pred = lugre_predict(t, w, sig0, sig1, sig2, Ic, Is, ws, fs_ode)
%LUGRE_PREDICT Simulate the LuGre friction ODE at a fixed-rate step and
%predict current at the measurement times T, given measured velocity W(T).
%   I_pred = LUGRE_PREDICT(t, w, sig0, sig1, sig2, Ic, Is, ws, fs_ode)
%
%       zdot = w - sig0*|w|/g(w)*z,   g(w) = Ic + (Is-Ic)*exp(-(w/ws)^2)
%       I_f  = sig0*z + sig1*zdot + sig2*w
%
%   W is interpolated onto a uniform fs_ode grid (default 20 kHz, per the
%   tune-friction skill), integrated forward with explicit Euler from
%   z(1)=0, then the predicted current is interpolated back onto T.

if nargin < 9 || isempty(fs_ode), fs_ode = 20e3; end

t = t(:);
w = w(:);
dt_ode = 1 / fs_ode;
t_ode = (t(1):dt_ode:t(end))';
if t_ode(end) < t(end)
    t_ode(end + 1) = t(end);
end
w_ode = interp1(t, w, t_ode, 'linear', 'extrap');

n = numel(t_ode);
z = zeros(n, 1);
zdot = zeros(n, 1);
for k = 1:n - 1
    g = Ic + (Is - Ic) * exp(-(w_ode(k) / ws) ^ 2);
    zdot(k) = w_ode(k) - sig0 * abs(w_ode(k)) / g * z(k);
    z(k + 1) = z(k) + dt_ode * zdot(k);
end
g_end = Ic + (Is - Ic) * exp(-(w_ode(n) / ws) ^ 2);
zdot(n) = w_ode(n) - sig0 * abs(w_ode(n)) / g_end * z(n);

I_ode = sig0 .* z + sig1 .* zdot + sig2 .* w_ode;
I_pred = interp1(t_ode, I_ode, t, 'linear', 'extrap');
end
