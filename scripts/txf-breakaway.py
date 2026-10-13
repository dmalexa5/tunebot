#!/usr/bin/env python3
"""Breakaway detection for a .txf capture of signal_ramp on iq
(run-ramp.sh torque), for tune-friction Test 2/3.

Reports the loading rate (A/s), the current and elapsed time at breakaway
(first run of sustain_n consecutive samples with |mvel_filt| over a threshold
set above measured baseline noise), and writes the pre-breakaway segment
(t, w, iq) for the LuGre fit. mvel_filt is the recorded filtered motor velocity,
sign-corrected into output-shaft rad/s; no additional gearing is applied.
The default threshold is 0.05 rad/s; measure noise before choosing it.

.txf is a directory: metadata.json lists "traces", each with a dtype,
scaling, and a traceN.bin of raw little-endian samples.
"""
import csv, json, math, os, struct, sys

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
# side through a 500 Hz biquad when ctrl sets VEL_USE_MENC, and only
# equals ovel in the default output-encoder configuration.
FBK_ALIASES = {'opos': 'pos_fbk', 'ovel': 'vel_fbk'}

# run-ramp.sh's start_pad/end_pad: fixed-length baseline/tail around the
# ramp, same convention as txf-ramp.py.
EDGE = 20


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
    return out, hscale


def analyze(txf, vel_threshold=0.05, sustain_n=3):
    d, dt = load(txf)
    iq_cmd, iq_fbk = d['iq_cmd'], d.get('iq_fbk', d['iq_cmd'])
    if 'mvel_filt' not in d:
        raise ValueError('capture lacks mvel_filt; recapture with updated TRACE=MECH firmware and tables')
    mvel_filt = d['mvel_filt']
    n = len(iq_cmd)
    if n <= 2 * EDGE:
        raise ValueError(f"capture too short ({n} samples) for a {EDGE}-sample baseline+tail")

    ramp = slice(EDGE, n - EDGE)
    ramp_cmd, ramp_fbk, ramp_vel = iq_cmd[ramp], iq_fbk[ramp], mvel_filt[ramp]
    nramp = len(ramp_cmd)
    dur = nramp * dt
    rate = (ramp_cmd[-1] - ramp_cmd[0]) / dur if dur else float('nan')

    breakaway_i = None
    for i in range(len(ramp_vel) - sustain_n + 1):
        if all(abs(v) > vel_threshold for v in ramp_vel[i:i + sustain_n]):
            breakaway_i = i
            break
    if breakaway_i is None:
        raise ValueError(
            f"no breakaway detected (|mvel_filt| never sustained {vel_threshold} rad/s "
            f"for {sustain_n} consecutive samples)")

    presliding_t = [i * dt for i in range(breakaway_i + 1)]
    presliding_i = ramp_fbk[:breakaway_i + 1]
    presliding_w = ramp_vel[:breakaway_i + 1]

    return dict(
        rate=rate, dt=dt,
        breakaway_time=breakaway_i * dt,
        breakaway_current=ramp_cmd[breakaway_i],
        presliding_t=presliding_t, presliding_w=presliding_w, presliding_i=presliding_i,
    )


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} capture.txf [vel_threshold] [out.csv] [sustain_n]", file=sys.stderr)
        sys.exit(1)
    txf = sys.argv[1]
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
    out_csv = sys.argv[3] if len(sys.argv) > 3 else None
    sustain_n = int(sys.argv[4]) if len(sys.argv) > 4 else 3

    r = analyze(txf, threshold, sustain_n)
    print(f"{os.path.basename(txf)}  rate {r['rate']:.4f} A/s")
    print(f"  breakaway at t={r['breakaway_time']*1e3:.3f} ms, iq={r['breakaway_current']:.4f} A")
    print(f"  presliding segment: {len(r['presliding_t'])} samples")

    if out_csv:
        with open(out_csv, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['t', 'w', 'iq'])
            for t, vel, iq in zip(r['presliding_t'], r['presliding_w'], r['presliding_i']):
                w.writerow([t, vel, iq])
        print(f"  wrote {out_csv}")
