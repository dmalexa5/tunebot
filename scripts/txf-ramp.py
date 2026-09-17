#!/usr/bin/env python3
"""Numeric metrics from a .txf capture of signal_ramp (run-ramp.sh).

.txf is a directory: metadata.json lists "traces", each with a dtype,
scaling, and a traceN.bin of raw little-endian samples.
"""
import json, math, os, struct, sys

DT = {'f32': ('<f', 4), 'i32': ('<i', 4), 'u32': ('<I', 4),
      'i16': ('<h', 2), 'u16': ('<H', 2), 'i8': ('<b', 1), 'u8': ('<B', 1)}

# The firmware traces angles in degrees (board-drive.c @signal vscale) while
# everything below works in rad. metadata.json states each trace's unit, so
# key the conversion off that rather than off a name list.
DEG_UNITS = ('°', '°/s')

# mech_trace names the feedback traces after the encoders they come from
# (opos/ovel, output shaft). Alias them onto the cmd/fbk pairing used below;
# the firmware's own names stay available too. An alias never overwrites a
# trace the firmware publishes under that name: mech_trace now carries its own
# vel_fbk -- the velocity the loop actually closes on, which is the *rotor*
# side through a 500 Hz biquad when SERVO_FLAGS selects VEL_SRC_MENC, and only
# equals ovel in the default output-encoder configuration.
FBK_ALIASES = {'opos': 'pos_fbk', 'ovel': 'vel_fbk'}

# pos_cmd/pos_fbk/pos_rx are wrapped to [-pi, pi) by the firmware (single-turn
# encoder); unwrap so a wrap crossing doesn't show up as a spurious ~2*pi step.
POS_KEYS = ('pos_cmd', 'pos_fbk', 'pos_rx')

# The run-*.sh wrappers ask signal_ramp for start_pad = end_pad =
# EDGE*decimation servo ticks, so the baseline before the ramp and the tail
# after it are always exactly this many pushed samples, whatever the stride.
# Unlike a step, the tail holds at the ramp's *target*, not back at the start
# value: signal_ramp ramps TO its target and stays there (test-signal.c).
EDGE = 20

MODE_KEYS = {'pos': ('pos_cmd', 'pos_fbk'), 'vel': ('vel_cmd', 'vel_fbk'),
             'torque': ('iq_cmd', 'iq_fbk')}
RATE_UNIT = {'pos': 'mrad/s', 'vel': 'mrad/s^2', 'torque': 'mA/s'}

def unwrap(x, period=2 * math.pi):
    out = [x[0]]
    off = 0.0
    for a, b in zip(x, x[1:]):
        d = b - a
        if d > period / 2: off -= period
        elif d < -period / 2: off += period
        out.append(b + off)
    return out

def load(txf):
    meta = json.load(open(os.path.join(txf, 'metadata.json')))
    out, hscale = {}, None
    for tr in meta['traces']:
        fmt, w = DT[tr['dtype']]
        raw = open(os.path.join(txf, tr['file']), 'rb').read()
        n = len(raw) // w
        vals = [v[0] for v in struct.iter_unpack(fmt, raw[:n * w])]
        vs, vo = tr.get('vscale', 1.0), tr.get('voffset', 0.0)
        scaled = [v * vs + vo for v in vals]
        if tr.get('unit') in DEG_UNITS:
            scaled = [v * math.pi / 180.0 for v in scaled]
        out[tr['name']] = scaled
        hscale = tr.get('hscale', hscale)
    for src, dst in FBK_ALIASES.items():
        if src in out and dst not in out:
            out[dst] = out[src]
    for k in POS_KEYS:
        if k in out and len(out[k]) > 1:
            out[k] = unwrap(out[k])
    return out, hscale

def rms(x):
    return math.sqrt(sum(v * v for v in x) / len(x)) if x else 0.0

def mean(x):
    return sum(x) / len(x) if x else 0.0

def edge_metrics(seg, dt, initial, target, band=0.02):
    """Overshoot (% of step size) and settling time (time until `seg` stays
    within `band` of `target`) for a segment `seg` that starts at `initial`
    and is commanded to (held at) `target`."""
    delta = target - initial
    if delta == 0 or not seg:
        return dict(overshoot_pct=0.0, settle_time=None)

    overshoot = max(0.0, (max(seg) - target) if delta > 0 else (target - min(seg)))
    overshoot_pct = 100 * overshoot / abs(delta)

    tol = abs(band * delta)
    settle_i = 0
    for i, v in enumerate(seg):
        if abs(v - target) > tol:
            settle_i = i + 1
    settle_time = settle_i * dt if settle_i < len(seg) else None

    return dict(overshoot_pct=overshoot_pct, settle_time=settle_time)

def analyze(txf, mode='pos'):
    d, hscale = load(txf)
    dt = hscale
    cmd_k, fbk_k = MODE_KEYS[mode]
    cmd, fbk = d[cmd_k], d[fbk_k]
    n = len(cmd)
    if n <= 2 * EDGE:
        raise ValueError(f"capture too short ({n} samples) for a {EDGE}-sample baseline+tail")

    start = mean(cmd[:EDGE])
    target = mean(cmd[-EDGE:])
    ramp = slice(EDGE, n - EDGE)
    ramp_cmd, ramp_fbk = cmd[ramp], fbk[ramp]
    nramp = len(ramp_cmd)
    dur = nramp * dt
    ramp_rate = (target - start) / dur if dur else float('nan')

    # Steady-slope tracking error: skip the transient at each end of the ramp
    # (acquisition lag going in, target landing coming out) and look at the
    # constant-lag middle portion.
    skip = max(1, nramp // 5)
    mid_cmd, mid_fbk = ramp_cmd[skip:-skip], ramp_fbk[skip:-skip]
    err_mid = [c - f for c, f in zip(mid_cmd, mid_fbk)]
    lag_err = mean(err_mid) if err_mid else float('nan')
    lag_time = lag_err / ramp_rate if ramp_rate else float('nan')

    err_all = [c - f for c, f in zip(ramp_cmd, ramp_fbk)]
    err_rms = rms(err_all)
    err_max = max(abs(v) for v in err_all) if err_all else 0.0

    post = edge_metrics(fbk[n - EDGE:], dt, fbk[n - EDGE - 1], target)

    iq_cmd, iq_fbk = d.get('iq_cmd', []), d.get('iq_fbk', [])
    iqw = (iq_fbk or iq_cmd)[ramp]
    # Chatter detector: iq_cmd is the velocity loop's own output, so its
    # sample-to-sample jitter is loop activity with no measurement noise --
    # useful here since a constant-slope ramp is a closer analog to a real
    # move than a sine, and can excite chatter a sine sweep misses.
    iqc = iq_cmd[ramp]
    iqj = rms([b - a for a, b in zip(iqc, iqc[1:])]) if len(iqc) > 1 else 0.0

    return dict(
        n=n, dt=dt, dur=dur,
        start=start, target=target, ramp_rate=ramp_rate,
        lag_err=lag_err, lag_time=lag_time,
        err_rms=err_rms, err_max=err_max,
        post_overshoot_pct=post['overshoot_pct'], post_settle_time=post['settle_time'],
        iq_rms=rms(iqw), iq_max=(max(abs(v) for v in iqw) if iqw else 0.0),
        iq_jitter=iqj,
    )

if __name__ == '__main__':
    txf = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'pos'
    r = analyze(txf, mode)
    unit = {'pos': 'mrad', 'vel': 'mrad/s', 'torque': 'mA'}[mode]
    rate_unit = RATE_UNIT[mode]
    def fmt_ms(v): return f"{v*1e3:.3f} ms" if v is not None else "never"
    print(f"{os.path.basename(txf)}  {mode} ramp  {r['n']} samp, {r['dur']*1e3:.1f} ms ramp @ {1/r['dt']:.0f}Hz")
    print(f"  start -> target  {r['start']*1e3:9.3f} -> {r['target']*1e3:9.3f} {unit}  (rate {r['ramp_rate']*1e3:+.3f} {rate_unit})")
    print(f"  tracking lag     {r['lag_err']*1e3:9.3f} {unit}  ({r['lag_time']*1e3:+.3f} ms of ramp_rate)")
    print(f"  err rms/max      {r['err_rms']*1e3:9.3f} / {r['err_max']*1e3:9.3f} {unit}")
    print(f"  post-ramp overshoot {r['post_overshoot_pct']:9.3f} %   settle {fmt_ms(r['post_settle_time'])}")
    print(f"  iq rms {r['iq_rms']:.3f} A  max {r['iq_max']:.3f} A  jitter {r['iq_jitter']*1e3:.1f} mA/samp")
