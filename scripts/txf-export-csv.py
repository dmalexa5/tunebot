#!/usr/bin/env python3
"""Dump named traces from a .txf capture to a CSV (t, <trace>, ...).

Used for tune-friction Test 3 to hand the dither-sweep captures (servo_sine,
mode=torque) to the MATLAB joint LuGre fit as plain (t, w, iq) data,
mirroring the presliding CSVs txf-breakaway.py writes for Test 2.
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
# the firmware's own names stay available too.
FBK_ALIASES = {'opos': 'pos_fbk', 'ovel': 'vel_fbk'}


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
        if tr['name'] in FBK_ALIASES:
            out[FBK_ALIASES[tr['name']]] = scaled
        hscale = tr.get('hscale', hscale)
    return out, hscale


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(f"usage: {sys.argv[0]} capture.txf trace1,trace2,... out.csv", file=sys.stderr)
        sys.exit(1)
    txf, trace_names, out_csv = sys.argv[1], sys.argv[2].split(','), sys.argv[3]

    d, dt = load(txf)
    n = len(d[trace_names[0]])
    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['t'] + trace_names)
        for i in range(n):
            w.writerow([i * dt] + [d[name][i] for name in trace_names])
    print(f"wrote {out_csv} ({n} samples, {trace_names})")
