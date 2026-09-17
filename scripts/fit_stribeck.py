#!/usr/bin/env python3
"""Fit steady-state Stribeck parameters from bidirectional velocity holds.

Uses recorded mvel_filt in sign-corrected output-shaft rad/s and iq_fbk in A.
Skips the wrappers' 20-sample pads and an initial settle interval (300 ms).
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

DT = {'f32': '<f4', 'i32': '<i4', 'u32': '<u4', 'i16': '<i2',
      'u16': '<u2', 'i8': 'i1', 'u8': 'u1'}
EDGE = 20


def hold_steady_state(txf_dir, settle_s):
    path = Path(txf_dir)
    meta = json.loads((path / 'metadata.json').read_text())
    data = {}
    for tr in meta['traces']:
        if tr['name'] not in ('mvel_filt', 'iq_fbk'):
            continue
        values = np.fromfile(path / tr['file'], dtype=DT[tr['dtype']]).astype(float)
        values = values * tr.get('vscale', 1.0) + tr.get('voffset', 0.0)
        if tr.get('unit') in ('°', '°/s'):
            values = np.deg2rad(values)
        data[tr['name']] = values
        dt = tr['hscale']
    if 'mvel_filt' not in data:
        raise ValueError(f'{path} lacks mvel_filt; recapture with updated TRACE=MECH firmware and tables')
    n = len(data['mvel_filt'])
    if n <= 2 * EDGE:
        raise ValueError(f'{path} too short ({n} samples)')
    # MATLAB round rounds positive half-integers up, unlike Python round.
    start = EDGE + int(np.floor(settle_s / dt + 0.5))
    end = n - EDGE
    if start >= end - 1:
        raise ValueError(f'{path} hold too short for a {settle_s * 1000:.0f} ms settle skip')
    return np.mean(data['mvel_filt'][start:end]), np.mean(data['iq_fbk'][start:end])


def fit_stribeck(txf_glob, settle_s=0.3):
    """Return parameters, residuals, aligned data, and retained signed pairs."""
    files = sorted(glob.glob(str(txf_glob)))
    if not files:
        raise ValueError(f'no captures matched {txf_glob}')
    pairs = np.array([hold_steady_state(path, settle_s) for path in files])
    signed_w, signed_I = pairs.T
    if np.any(signed_w == 0):
        raise ValueError('zero mean mvel_filt cannot determine motion direction')
    order = np.argsort(np.abs(signed_w), kind='stable')
    signed_w, signed_I = signed_w[order], signed_I[order]
    w = np.abs(signed_w)
    I = signed_I * np.sign(signed_w)

    def residuals(p):
        return p[0] + (p[1] - p[0]) * np.exp(-(w / p[2]) ** 2) + p[3] * w - I

    p0 = [min(I), max(I), np.median(w), 0]
    fit = least_squares(residuals, p0,
                        bounds=([0, 0, np.finfo(float).eps, -np.inf], np.inf))
    if not fit.success:
        raise RuntimeError(f'Stribeck fit failed: {fit.message}')
    result = dict(zip(('Ic', 'Is', 'stribeck_vel', 'sig2'), fit.x.tolist()))
    result.update(resnorm=float(fit.fun @ fit.fun), residual=fit.fun.tolist(),
                  w=w.tolist(), I=I.tolist(), signed_w=signed_w.tolist(),
                  signed_I=signed_I.tolist())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('txf_glob', help='quoted glob matching velocity-hold .txf directories')
    parser.add_argument('--settle-s', type=float, default=0.3)
    args = parser.parse_args()
    try:
        result = fit_stribeck(args.txf_glob, args.settle_s)
    except (ValueError, RuntimeError) as err:
        parser.exit(1, f'{err}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
