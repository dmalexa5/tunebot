# j1 friction identification

Target: `100.79.218.29`. Historical session; slow ramps and 20-cycle low-frequency
dithers exceed today's ~3.27 s capture limit.

| Parameter | Result |
|---|---|
| Ic | 1.1738 A |
| Is | 1.0675 A; weakly constrained |
| stribeck_vel | 0.0159 rad/s; weakly constrained |
| sig2 | 0.5872 A/(rad/s) |
| sig0, sig1 | Not identified |

13 velocity holds (0.01–0.875 rad/s, 1000 ms, stride 12) showed no Stribeck knee;
Is < Ic. Fit resnorm: 0.00196. A 300 ms settle skip was needed; sig2 is the
most reliable result. Initial zero servo gains invalidated the first test round.

Breakaway currents were 1.10–1.68 A across 0.1–100 A/s ramps, without a clean
rate trend below 100 A/s. Velocity noise (~3 mrad/s standard deviation, spikes to 14 mrad/s)
caused false triggers; a 20 mrad/s threshold sustained for 3 samples resolved them.

The joint LuGre fit to presliding and 0.15 A dithers (1–100 Hz) returned
nonphysical values: sig0≈0, sig1≈93, sig2≈-116. Velocity was indistinguishable
from noise. Use position-derived velocity or stronger sub-breakaway excitation
before retrying; these data do not identify sig0/sig1.

Captures: `traces/j1-friction-tune/` — `vstep.0000.txf`, `tramp.0000.txf`,
`tstep.0000.txf`, `tsine.0000.txf` represent each test type.
