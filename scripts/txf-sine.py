#!/usr/bin/env python3
"""Numeric metrics from a .txf capture of test_servo_sine (or servo_step).

.txf is a directory: metadata.json lists "traces", each with a dtype,
scaling, and a traceN.bin of raw little-endian samples.
"""
import json, math, os, struct, sys

DT = {'f32': ('<f', 4), 'i32': ('<i', 4), 'u32': ('<I', 4),
      'i16': ('<h', 2), 'u16': ('<H', 2), 'i8': ('<b', 1), 'u8': ('<B', 1)}

# pos_cmd/pos_fbk/pos_rx are wrapped to [-pi, pi) by the firmware (single-turn
# encoder), but the arm's rest position drifts test-to-test and can sit close
# enough to the wrap boundary that a 0.2 rad sine crosses it -- unwrap so a
# crossing doesn't show up as a spurious ~2*pi step in the recorded trace.
POS_KEYS = ('pos_cmd', 'pos_fbk', 'pos_rx')

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

def dft1(x, dt, f):
    """Complex amplitude of x at frequency f (peak, not rms)."""
    n = len(x)
    re = sum(v * math.cos(2 * math.pi * f * i * dt) for i, v in enumerate(x))
    im = sum(v * math.sin(2 * math.pi * f * i * dt) for i, v in enumerate(x))
    return (2.0 / n) * re, (2.0 / n) * im

def run_window(cmd, edge=20):
    """Indices [lo,hi) of the driven part.

    test_servo_sine holds the command at its baseline for
    TEST_SERVO_STEP_EDGE_SAMPLES*stride ISR ticks before and after the run,
    and pushes one trace sample every `stride` ticks -- so the baseline and
    tail are always exactly 20 pushed samples, whatever the stride. Detecting
    the edges from the data instead would throw away a cycle in VELOCITY
    mode, where the sine both starts and ends at zero and is therefore
    indistinguishable from the baseline for the first and last setpoint.
    """
    return edge, len(cmd) - edge

def analyze(txf, freq, mode='pos', cycles=None):
    d, hscale = load(txf)
    dt = hscale
    cmd_k, fbk_k = ('pos_cmd', 'pos_fbk') if mode == 'pos' else ('vel_cmd', 'vel_fbk')
    cmd, fbk = d[cmd_k], d[fbk_k]
    lo, hi = run_window(cmd)

    # Trim to a whole number of cycles so the DFT sees no leakage, and drop
    # the first cycle: the loop is still acquiring the trajectory there.
    per = int(round(1.0 / (freq * dt)))
    avail = hi - lo
    ncyc = avail // per
    if ncyc >= 2:
        lo += per            # skip first cycle (acquisition transient)
        ncyc -= 1
    hi = lo + ncyc * per if ncyc >= 1 else hi

    c, f = cmd[lo:hi], fbk[lo:hi]
    dcc = sum(c) / len(c)
    dcf = sum(f) / len(f)
    err = [a - b for a, b in zip(c, f)]

    cre, cim = dft1([v - dcc for v in c], dt, freq)
    fre, fim = dft1([v - dcf for v in f], dt, freq)
    cmag = math.hypot(cre, cim)
    fmag = math.hypot(fre, fim)
    # re ~ sin(phi), im ~ cos(phi) with this DFT pair, so atan2(im,re) is
    # (90 - phi) and the difference comes out sign-flipped. Negate so the
    # reported number follows the usual convention: negative = fbk lags cmd.
    ph = -math.degrees(math.atan2(fim, fre) - math.atan2(cim, cre))
    while ph > 180: ph -= 360
    while ph < -180: ph += 360

    ere, eim = dft1([v - sum(err) / len(err) for v in err], dt, freq)
    efund = math.hypot(ere, eim)                 # peak amplitude at fundamental
    etot = rms(err)
    efund_rms = efund / math.sqrt(2)
    eresid = math.sqrt(max(0.0, etot * etot - efund_rms * efund_rms))

    iq = d.get('iq_fbk', d.get('iq_cmd', []))
    iqw = iq[lo:hi] if iq else []
    # Chatter detector. iq_cmd is the velocity loop's own output, so its
    # sample-to-sample jitter is loop activity with no measurement noise
    # mixed in; a first difference is a crude high-pass that rises sharply
    # once the loop starts ringing against the geartrain.
    iqc = d.get('iq_cmd', [])[lo:hi]
    iqj = rms([b - a for a, b in zip(iqc, iqc[1:])]) if len(iqc) > 1 else 0.0

    return dict(
        n=len(c), ncyc=ncyc, dt=dt, dur=len(c) * dt,
        cmd_amp=cmag, fbk_amp=fmag,
        gain=(fmag / cmag if cmag else float('nan')),
        gain_db=(20 * math.log10(fmag / cmag) if cmag and fmag else float('nan')),
        phase_deg=ph,
        err_rms=etot, err_max=max(abs(v) for v in err),
        err_fund=efund, err_resid_rms=eresid,
        err_bias=sum(err) / len(err),
        err_rms_pct=100 * etot / cmag if cmag else float('nan'),
        iq_rms=rms(iqw), iq_max=(max(abs(v) for v in iqw) if iqw else 0.0),
        iq_jitter=iqj,
        vel_pk=(max(abs(v) for v in d['vel_fbk'][lo:hi]) if 'vel_fbk' in d else 0.0),
    )

if __name__ == '__main__':
    txf, freq = sys.argv[1], float(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) > 3 else 'pos'
    r = analyze(txf, freq, mode)
    unit = 'mrad' if mode == 'pos' else 'mrad/s'
    print(f"{os.path.basename(txf)}  {mode} f={freq}Hz  "
          f"{r['ncyc']} cyc, {r['n']} samp, {r['dur']:.2f}s @ {1/r['dt']:.0f}Hz")
    print(f"  cmd amp      {r['cmd_amp']*1e3:9.3f} {unit}")
    print(f"  fbk amp      {r['fbk_amp']*1e3:9.3f} {unit}   "
          f"gain {r['gain']:.4f} ({r['gain_db']:+.2f} dB)  phase {r['phase_deg']:+.2f} deg")
    print(f"  err rms      {r['err_rms']*1e3:9.3f} {unit}   ({r['err_rms_pct']:.2f}% of cmd amp)")
    print(f"  err max      {r['err_max']*1e3:9.3f} {unit}")
    print(f"  err @fund    {r['err_fund']*1e3:9.3f} {unit}  (peak; linear lag/gain)")
    print(f"  err residual {r['err_resid_rms']*1e3:9.3f} {unit}  (rms; nonlinear/stiction+noise)")
    print(f"  err bias     {r['err_bias']*1e3:9.3f} {unit}")
    print(f"  iq rms {r['iq_rms']:.3f} A  max {r['iq_max']:.3f} A  "
          f"jitter {r['iq_jitter']*1e3:.1f} mA/samp   vel pk {r['vel_pk']:.3f} rad/s")
