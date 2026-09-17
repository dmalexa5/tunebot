#!/usr/bin/env python3
"""Plot each current chirp's frequency-response magnitude and phase."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

SERVO_HZ = 20000
EDGE = 20
GEAR_RATIO = -509.7
SIGNALS = ('iq_cmd', 'iq_fbk', 'mvel', 'ovel', 'mpos', 'opos')
DT = {'f32': '<f4', 'i32': '<i4', 'u32': '<u4', 'i16': '<i2',
      'u16': '<u2', 'i8': 'i1', 'u8': 'u1'}


def validate_settings(args):
    values = (args.amplitude, args.f0, args.f1, args.delay, args.rest_threshold)
    if not all(np.isfinite(v) for v in values):
        raise ValueError('settings must be finite')
    if args.amplitude <= 0 or not 0 < args.f0 < args.f1:
        raise ValueError('require amplitude > 0 and 0 < f0 < f1')
    if args.duration_ms < 1 or not 1 <= args.stride <= 255:
        raise ValueError('duration must be positive integer ms; stride must be 1..255')
    if args.repeats < 2 or args.delay < 0 or args.rest_threshold <= 0:
        raise ValueError('require repeats >= 2, delay >= 0, and rest threshold > 0')
    if args.f1 >= SERVO_HZ / args.stride / 4:
        raise ValueError('f1 must be below one-quarter of the capture sample rate')
    if args.duration_ms * 20 + 2 * EDGE * args.stride > 65534:
        raise ValueError('chirp plus baseline/tail exceeds the 65534-tick timeline')
    if args.duration_ms * 20 // args.stride < 2:
        raise ValueError('chirp needs at least two captured samples')


def load(txf):
    meta = json.loads((Path(txf) / 'metadata.json').read_text())
    data, intervals, offsets = {}, [], []
    for tr in meta['traces']:
        name = tr['name']
        if name not in SIGNALS:
            continue
        dtype = np.dtype(DT[tr['dtype']])
        raw = (Path(txf) / tr['file']).read_bytes()
        if len(raw) % dtype.itemsize:
            raise ValueError(f'{txf}: incomplete binary sample in {name}')
        vals = np.frombuffer(raw, dtype=dtype).astype(float)
        vals = vals * tr.get('vscale', 1.0) + tr.get('voffset', 0.0)
        if tr.get('unit') in ('°', '°/s'):
            vals = np.deg2rad(vals)
        if name in ('mpos', 'opos'):
            vals = np.unwrap(vals)
        if name in ('mpos', 'mvel'):
            vals /= GEAR_RATIO
        data[name] = vals
        intervals.append(tr['hscale'])
        offsets.append(tr.get('hoffset', 0.0))
    missing = set(SIGNALS) - data.keys()
    if missing:
        raise ValueError(f'{txf}: missing traces: {", ".join(sorted(missing))}')
    if not all(np.isfinite(intervals)) or intervals[0] <= 0:
        raise ValueError(f'{txf}: invalid sample period')
    if not np.allclose(intervals, intervals[0], rtol=1e-6, atol=0):
        raise ValueError(f'{txf}: inconsistent sample periods')
    if not np.allclose(offsets, offsets[0], rtol=0, atol=1e-12):
        raise ValueError(f'{txf}: inconsistent time offsets')
    if len({len(v) for v in data.values()}) != 1:
        raise ValueError(f'{txf}: inconsistent trace lengths')
    if not all(np.all(np.isfinite(v)) for v in data.values()):
        raise ValueError(f'{txf}: non-finite samples')
    return data, intervals[0]


def prepare(txf, args):
    data, dt = load(txf)
    if not np.isclose(dt, args.stride / SERVO_HZ, rtol=1e-6, atol=0):
        raise ValueError(f'{txf}: sample period does not match requested stride')
    ticks = args.duration_ms * 20 + 2 * EDGE * args.stride
    # Trace starts on the free-running decimation grid, and includes the
    # first sample after the signal becomes inactive (board-drive.c).
    minimum = (ticks + 1) // args.stride + 1
    maximum = (ticks + args.stride) // args.stride + 1
    n = len(data['iq_cmd'])
    if not minimum <= n <= maximum:
        raise ValueError(f'{txf}: truncated/unexpected length {n}; expected {minimum}..{maximum}')
    rest = np.sqrt(np.mean(data['ovel'][:EDGE] ** 2))
    if rest >= args.rest_threshold:
        raise ValueError(f'{txf}: baseline ovel RMS {rest:.6g} rad/s is not below {args.rest_threshold:g}')
    count = (args.duration_ms * 20 + args.stride - 1) // args.stride
    traces = np.stack([data[name][EDGE:EDGE + count] for name in SIGNALS])
    traces -= traces.mean(axis=-1, keepdims=True)
    if not np.any(traces[0]):
        raise ValueError(f'{txf}: current command contains no excitation')
    return traces, dt


def estimate(traces):
    spectra = np.fft.rfft(traces, axis=-1)
    x, y = spectra[:1], spectra[1:]
    response = np.full(y.shape, np.nan, dtype=complex)
    np.divide(y, x, out=response, where=abs(x) > 0)
    return response


def plot(traces, dt, args, capture):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    response = estimate(traces)
    freq = np.fft.rfftfreq(traces.shape[-1], dt)
    band = (freq >= args.f0) & (freq <= args.f1)
    if not np.any(band):
        raise ValueError('no FFT bins in requested sweep band; increase duration')
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(11, 8),
                             gridspec_kw={'height_ratios': [3, 1]})
    units = ('A/A', '(rad/s)/A out', '(rad/s)/A out', 'rad/A out', 'rad/A out')
    for i, (name, unit) in enumerate(zip(SIGNALS[1:], units)):
        valid = band & np.isfinite(response[i]) & (abs(response[i]) > 0)
        mag = np.full(freq.shape, np.nan)
        mag[valid] = 20 * np.log10(abs(response[i, valid]))
        phase = np.full(freq.shape, np.nan)
        phase[valid] = np.angle(response[i, valid], deg=True)
        axes[0].plot(freq[band], mag[band], label=f'{name} [{unit}]')
        axes[1].plot(freq[band], phase[band], label=name)
    axes[0].set_title(f'{capture.name}: iq chirp {args.f0:g}–{args.f1:g} Hz, DC=0, {args.amplitude:g} A\n'
                      f'{args.duration_ms} ms, stride {args.stride}, ratio {GEAR_RATIO:g}')
    axes[0].set_ylabel('Response vs iq_cmd [dB]')
    axes[0].legend()
    axes[1].set_ylabel('Phase [deg]')
    axes[1].set_xlabel('f [Hz]')
    axes[1].set_ylim(-180, 180)
    for ax in axes:
        ax.set_xscale('log')
        ax.set_xlim(args.f0, args.f1)
        ax.grid(True, which='both', alpha=0.3)
    fig.tight_layout()
    output = (args.output_dir or capture.parent) / f'{capture.stem}.png'
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(f'Saved {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures', nargs='*', type=Path)
    parser.add_argument('--amplitude', required=True, type=float)
    parser.add_argument('--f0', required=True, type=float)
    parser.add_argument('--f1', required=True, type=float)
    parser.add_argument('--duration-ms', required=True, type=int)
    parser.add_argument('--repeats', required=True, type=int)
    parser.add_argument('--stride', required=True, type=int)
    parser.add_argument('--delay', default=1.0, type=float)
    parser.add_argument('--rest-threshold', default=0.05, type=float)
    parser.add_argument('--output-dir', type=Path, help='directory for per-capture PNGs')
    parser.add_argument('--validate-settings', action='store_true')
    parser.add_argument('--signal-json', action='store_true', help='print the RTT chirp command')
    parser.add_argument('--check', action='store_true', help='validate a single capture without plotting')
    args = parser.parse_args()
    try:
        validate_settings(args)
        if args.signal_json:
            print(json.dumps(dict(test='signal_chirp', signal='iq', amplitude=args.amplitude,
                                  f0_hz=args.f0, f1_hz=args.f1, duration_ms=args.duration_ms,
                                  log=True, taper=False, start_pad=EDGE * args.stride,
                                  end_pad=EDGE * args.stride, decimation=args.stride)))
            return
        if args.validate_settings:
            return
        expected = 1 if args.check else args.repeats
        if len(args.captures) != expected or len(set(args.captures)) != expected:
            raise ValueError(f'require {expected} distinct capture paths')
        prepared = [prepare(path, args) for path in args.captures]
        if args.check:
            print(f'Validated {args.captures[0]}')
            return
        print(f'{args.repeats} repeats: {args.amplitude:g} A, {args.f0:g}–{args.f1:g} Hz, '
              f'{args.duration_ms} ms, stride {args.stride}, log sweep, no taper, DC=0')
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
        for path, (traces, dt) in zip(args.captures, prepared):
            print(f'Capture: {path}')
            plot(traces, dt, args, path)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'txf-chirp: {error}\n')


if __name__ == '__main__':
    main()
