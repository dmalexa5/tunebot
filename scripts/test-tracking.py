#!/usr/bin/env python3
"""Capture ten 3-second position sines and plot peak/mean absolute error."""
import argparse
import json
import math
from pathlib import Path
import runpy
import signal as signals
import subprocess
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT.parent / 'module-fwpp/tools/rttcmd'
TABLES = ROOT.parent / 'module-fwpp/output/drive/none/drive-none.tables.json'
LOAD = runpy.run_path(str(ROOT / 'scripts/txf-sine.py'))['load']
FREQUENCIES = [0.1 + i * 0.5 / 9 for i in range(10)]
STRIDE = 20
EDGE = 20
DURATION_MS = 3000
COUNT = DURATION_MS * 20 // STRIDE


def signal(frequency):
    # Equal chirp endpoints give a fixed-frequency sine without a uint16 period.
    return dict(test='signal_chirp', signal='pos',
                amplitude=round(0.25 * 4294967296 / (2 * math.pi)),
                f0_hz=frequency, f1_hz=frequency, duration_ms=DURATION_MS,
                log=False, taper=False, start_pad=EDGE * STRIDE,
                end_pad=EDGE * STRIDE, decimation=STRIDE)


def errors(capture):
    data, dt = LOAD(capture)
    cmd, fbk = data['pos_cmd'], data['pos_fbk']
    # The free-running decimation grid adds zero, one, or two closing samples.
    expected = COUNT + 2 * EDGE
    if len(cmd) != len(fbk) or len(cmd) not in (expected, expected + 1, expected + 2):
        raise ValueError(f'{capture}: truncated/unexpected position trace lengths')
    if not math.isclose(dt, STRIDE / 20000, rel_tol=1e-6):
        raise ValueError(f'{capture}: unexpected sample period')
    cmd, fbk = cmd[EDGE:EDGE + COUNT], fbk[EDGE:EDGE + COUNT]
    if not all(math.isfinite(v) for v in cmd + fbk):
        raise ValueError(f'{capture}: non-finite position samples')
    if max(cmd) - min(cmd) < 0.01:
        raise ValueError(f'{capture}: missing position excitation')
    # Align independently unwrapped single-turn angles by shortest difference.
    error = [abs((c - f + math.pi) % (2 * math.pi) - math.pi)
             for c, f in zip(cmd, fbk)]
    return max(error), sum(error) / len(error)


def find_capture(session, trial):
    captures = list(session.glob(f'tracking-{trial:02d}.*.txf'))
    if len(captures) != 1:
        raise ValueError(f'{session}: expected one capture for test {trial}')
    return captures[0]


def plot(session):
    results = [errors(find_capture(session, i)) for i in range(1, 11)]
    fig, ax = plt.subplots(figsize=(8, 5))
    for index, label in enumerate(('Peak absolute error', 'Mean absolute error')):
        ax.plot(FREQUENCIES, [r[index] * 1000 for r in results], 'o-', label=label)
    ax.set(xlabel='Frequency [Hz]', ylabel='Position tracking error [mrad]',
           title='Position tracking: 0.25 rad amplitude, 3 s per frequency\n'
                 'Entire driven window, including startup and partial cycles')
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    output = session / 'tracking.png'
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(f'Saved {output}')


def capture(args):
    args.session.mkdir(parents=True, exist_ok=False)

    def task(command, restart=False):
        subprocess.run([str(TOOLS / 'rtttask'), '-i', args.ip,
                        *(['-r'] if restart else []), json.dumps(command)], check=True)

    def zero():
        failed = False
        for command in (dict(command='Jx_STATUS', action='WRITE', mode='0TQ'),
                        dict(command='Jx_IDQ', action='WRITE', id=0, iq=0, mvel=0, mpos=0)):
            try:
                task(command)
            except (OSError, subprocess.CalledProcessError) as error:
                failed = True
                print(f'Zero-current cleanup failed: {error}', flush=True)
        if failed:
            raise RuntimeError('could not stop motion')

    in_flight = False
    try:
        task(dict(command='Jx_STATUS', action='WRITE', mode='0TQ'), args.restart)
        for trial, frequency in enumerate(FREQUENCIES, 1):
            zero()
            time.sleep(1)
            mode = dict(command='Jx_STATUS', action='WRITE', mode='POS')
            if args.friction:
                mode['ctrl'] = 'FEATURE_FRIC_COMP'
            task(mode)
            print(f'Test {trial}/10: {frequency:.6f} Hz, 0.25 rad, 3 s', flush=True)
            in_flight = True
            subprocess.run([str(TOOLS / 'rtttest'), '-n', '-s', str(TABLES),
                            '-i', args.ip, '-o', f'tracking-{trial:02d}',
                            json.dumps(signal(frequency))], cwd=args.session, check=True)
            zero()
            errors(find_capture(args.session, trial))
            in_flight = False
    finally:
        # A failed host command does not abort the board's bounded waveform.
        try:
            zero()
        finally:
            if in_flight:
                time.sleep(4)
                zero()
    plot(args.session)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=Path, help='new traces/session directory')
    parser.add_argument('-i', '--ip', default='127.0.0.1')
    parser.add_argument('-r', '--restart', action='store_true', help='start RTT server')
    parser.add_argument('-F', '--friction', action='store_true', help='enable friction compensation')
    parser.add_argument('--analyze', action='store_true', help='plot an existing session without hardware')
    args = parser.parse_args()
    args.session = args.session.resolve()
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    signals.signal(signals.SIGTERM, interrupt)
    try:
        if args.analyze:
            plot(args.session)
        else:
            capture(args)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError,
            subprocess.CalledProcessError) as error:
        parser.exit(1, f'test-tracking: {error}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'test-tracking: interrupted\n')


if __name__ == '__main__':
    main()
