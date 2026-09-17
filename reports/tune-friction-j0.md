# j0 friction identification — 48 V

Target: `100.79.218.29`; unloaded continuous-rotation joint, `TRACE=MECH`.
Historical session: slow ramps below 1 A/s exceed today's ~3.27 s capture limit.

| Parameter | Result |
|---|---|
| Ic | 1.7063 A |
| Is | 2.1286 A |
| stribeck_vel | 0.1246 rad/s; 95% CI [0.005, 0.245] |
| sig2 | 1.1957 A/(rad/s) |
| sig0 | 16174 A/rad, output-referred; effective ±20%, roughly 1–10 A/s |
| sig1 | Not identified |

13 velocity holds (0.010–0.875 rad/s, 1000 ms, stride 12) showed a Stribeck knee.
Presliding fits used 14 motor-position segments at 0.33–10 A/s, both directions,
with steady-state parameters fixed. Measured motor/output gear ratio: -509.7.
Position-derived velocity was 828× quieter than `vel_fbk`.

Per-rate sig0 fits ranged 12216–17673 A/rad; gearbox windup and creep limit
interpretation as a single bristle stiffness. Residual RMS: 0.24–0.34 A.
The 2 A step broke away in only 1/5 trials; 100 A/s detections were duration-limited
and excluded. Stride 1 overflowed; stride 2 worked. One high-velocity hold clipped.
Use `set-gains.sh`: VEL_KP=24 in rad units reads back as ~3.511e-08 in counts.

Captures: `traces/j0-48V-friction-tune/` — `vhold.0000–0012.txf`,
`br{0p1,0p33,1,3p3,10,33,100}{p,n}.0000–0004.txf`,
`bstep{p,n}.0000–0004.txf`; `vstep.0000/0001.txf` show the gain fix.
