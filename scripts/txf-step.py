#!/usr/bin/env python3
"""Numeric metrics from a .txf capture of test_servo_step.

.txf is a directory: metadata.json lists "traces", each with a dtype,
scaling, and a traceN.bin of raw little-endian samples.
"""
import json, math, os, struct, sys

DT = {'f32': ('<f', 4), 'i32': ('<i', 4), 'u32': ('<I', 4),
      'i16': ('<h', 2), 'u16': ('<H', 2), 'i8': ('<b', 1), 'u8': ('<B', 1)}

# pos_cmd/pos_fbk/pos_rx are wrapped to [-pi, pi) by the firmware (single-turn
# encoder); unwrap so a wrap crossing doesn't show up as a spurious ~2*pi step.
POS_KEYS = ('pos_cmd', 'pos_fbk', 'pos_rx')

# TEST_SERVO_STEP_EDGE_SAMPLES (board-drive.c): the baseline before the step
# and the tail after it falls back are always exactly this many pushed
# samples, whatever the stride -- so the step edges sit at fixed indices.
EDGE = 20

MODE_KEYS = {'pos': ('pos_cmd', 'pos_fbk'), 'vel': ('vel_cmd', 'vel_fbk'),
             'torque': ('iq_cmd', 'iq_fbk')}

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
        out[tr['name']] = [v * vs + vo for v in vals]
        hscale = tr.get('hscale', hscale)
    for k in POS_KEYS:
        if k in out and len(out[k]) > 1:
            out[k] = unwrap(out[k])
    return out, hscale

def rms(x):
    return math.sqrt(sum(v * v for v in x) / len(x)) if x else 0.0

def mean(x):
    return sum(x) / len(x) if x else 0.0

def edge_metrics(seg, dt, initial, target, band=0.02):
    """Rise time (10-90%), overshoot (% of step size), and settling time
    (time until `seg` stays within `band` of `target`) for a step response
    segment `seg` that starts at `initial` and is commanded to `target`."""
    delta = target - initial
    if delta == 0 or not seg:
        return dict(rise_time=float('nan'), overshoot_pct=0.0, settle_time=None)

    t10 = t90 = None
    for i, v in enumerate(seg):
        f = (v - initial) / delta
        if t10 is None and f >= 0.1: t10 = i
        if t90 is None and f >= 0.9: t90 = i
        if t10 is not None and t90 is not None: break
    rise_time = (t90 - t10) * dt if (t10 is not None and t90 is not None) else float('nan')

    overshoot = max(0.0, (max(seg) - target) if delta > 0 else (target - min(seg)))
    overshoot_pct = 100 * overshoot / abs(delta)

    tol = abs(band * delta)
    settle_i = 0
    for i, v in enumerate(seg):
        if abs(v - target) > tol:
            settle_i = i + 1
    settle_time = settle_i * dt if settle_i < len(seg) else None

    return dict(rise_time=rise_time, overshoot_pct=overshoot_pct, settle_time=settle_time)

def analyze(txf, mode='pos'):
    d, hscale = load(txf)
    dt = hscale
    cmd_k, fbk_k = MODE_KEYS[mode]
    cmd, fbk = d[cmd_k], d[fbk_k]
    n = len(cmd)
    if n <= 2 * EDGE:
        raise ValueError(f"capture too short ({n} samples) for a {EDGE}-sample baseline+tail")

    base = mean(cmd[:EDGE])
    target = mean(cmd[EDGE:-EDGE])
    step_amp = target - base
    fbk_pre = mean(fbk[:EDGE])
    fbk_post = mean(fbk[-EDGE:])
    # steady-state feedback at the end of the hold, just before the fall
    tail_n = max(1, (n - 2 * EDGE) // 5)
    fbk_hold = mean(fbk[n - EDGE - tail_n:n - EDGE])

    rise = edge_metrics(fbk[EDGE:n - EDGE], dt, fbk_pre, target)
    fall = edge_metrics(fbk[n - EDGE:], dt, fbk[n - EDGE - 1], base)

    ss_err = fbk_hold - target

    hold = slice(EDGE, n - EDGE)
    iq_cmd, iq_fbk = d.get('iq_cmd', []), d.get('iq_fbk', [])
    iqw = (iq_fbk or iq_cmd)[hold]
    # Chatter detector: iq_cmd is the velocity loop's own output, so its
    # sample-to-sample jitter is loop activity with no measurement noise.
    iqc = iq_cmd[hold]
    iqj = rms([b - a for a, b in zip(iqc, iqc[1:])]) if len(iqc) > 1 else 0.0

    return dict(
        n=n, dt=dt, dur=n * dt,
        base=base, target=target, step_amp=step_amp,
        fbk_pre=fbk_pre, fbk_hold=fbk_hold, fbk_post=fbk_post,
        ss_err=ss_err, ss_err_pct=(100 * ss_err / step_amp if step_amp else float('nan')),
        rise_time=rise['rise_time'], overshoot_pct=rise['overshoot_pct'], settle_time=rise['settle_time'],
        fall_settle_time=fall['settle_time'],
        iq_rms=rms(iqw), iq_max=(max(abs(v) for v in iqw) if iqw else 0.0),
        iq_jitter=iqj,
    )

if __name__ == '__main__':
    txf = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'pos'
    r = analyze(txf, mode)
    unit = {'pos': 'mrad', 'vel': 'mrad/s', 'torque': 'mA'}[mode]
    def fmt(v, suffix=unit): return f"{v*1e3:9.3f} {suffix}" if v is not None else "     n/a"
    def fmt_ms(v): return f"{v*1e3:.3f} ms" if v is not None else "never"
    print(f"{os.path.basename(txf)}  {mode} step  {r['n']} samp, {r['dur']*1e3:.1f} ms @ {1/r['dt']:.0f}Hz")
    print(f"  base -> target  {r['base']*1e3:9.3f} -> {r['target']*1e3:9.3f} {unit}  (step {r['step_amp']*1e3:+.3f} {unit})")
    print(f"  fbk pre/hold/post  {r['fbk_pre']*1e3:9.3f} / {r['fbk_hold']*1e3:9.3f} / {r['fbk_post']*1e3:9.3f} {unit}")
    print(f"  rise time (10-90%)   {r['rise_time']*1e3:9.3f} ms")
    print(f"  overshoot            {r['overshoot_pct']:9.3f} %")
    print(f"  settle time (2% band) {fmt_ms(r['settle_time']):>10}")
    print(f"  fall settle time      {fmt_ms(r['fall_settle_time']):>10}")
    print(f"  steady-state err     {fmt(r['ss_err'])}  ({r['ss_err_pct']:.2f}% of step)")
    print(f"  iq rms {r['iq_rms']:.3f} A  max {r['iq_max']:.3f} A  jitter {r['iq_jitter']*1e3:.1f} mA/samp")
