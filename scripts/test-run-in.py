#!/usr/bin/env python3
"""Run-in a joint: 5x (20 s 3 A torque hold each direction, then 0.5/1/2 Hz
position sine captures), and plot sine metrics across repeats for drift."""
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
ANALYZE = runpy.run_path(str(ROOT / 'scripts/txf-sine.py'))['analyze']

FREQUENCIES = [0.5, 1.0, 2.0]
AMPLITUDE_RAD = 0.138
REPEATS = 5
HOLD_A = 3.0
HOLD_S = 20
STRIDE = 20
EDGE = 20
DURATION_MS = 3000


def signal(frequency):
    # Equal chirp endpoints give a fixed-frequency sine without a uint16 period,
    # so all three frequencies share one duration/pad budget (test-tracking.py).
    return dict(test='signal_chirp', signal='pos',
                amplitude=round(AMPLITUDE_RAD * 4294967296 / (2 * math.pi)),
                f0_hz=frequency, f1_hz=frequency, duration_ms=DURATION_MS,
                log=False, taper=False, start_pad=EDGE * STRIDE,
                end_pad=EDGE * STRIDE, decimation=STRIDE)


def find_capture(session, findex, rep):
    captures = list(session.glob(f'runin-f{findex}-{rep:02d}.*.txf'))
    if len(captures) != 1:
        raise ValueError(f'{session}: expected one capture for f{findex} rep {rep}')
    return captures[0]


def plot(session):
    metrics = ('gain', 'phase_deg', 'err_rms', 'iq_jitter')
    labels = ('Gain [fbk/cmd]', 'Phase [deg]', 'Err RMS [mrad]', 'iq_cmd jitter [mA/samp]')
    scale = (1, 1, 1e3, 1e3)
    results = {findex: [ANALYZE(find_capture(session, findex, rep), freq, 'pos')
                         for rep in range(1, REPEATS + 1)]
               for findex, freq in enumerate(FREQUENCIES)}
    reps = list(range(1, REPEATS + 1))
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, metric, label, s in zip(axes.flat, metrics, labels, scale):
        for findex, freq in enumerate(FREQUENCIES):
            ax.plot(reps, [r[metric] * s for r in results[findex]], 'o-', label=f'{freq:g} Hz')
        ax.set(xlabel='Repeat', ylabel=label)
        ax.grid(True, alpha=0.3)
        ax.legend()
    fig.suptitle(f'Run-in drift: {AMPLITUDE_RAD} rad sine after {HOLD_A} A holds, x{REPEATS}')
    fig.tight_layout()
    output = session / 'run-in.png'
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

    def hold(iq_a):
        # Raw Jx_IDQ in 0TQ: unclamped by VEL_TQC_LIM/the signal engine, only
        # FOC_I_TRIP limits it. No capture -- rtttrace never arms.
        task(dict(command='Jx_STATUS', action='WRITE', mode='0TQ'))
        task(dict(command='Jx_IDQ', action='WRITE', id=0, iq=round(iq_a * 1000), mvel=0, mpos=0))
        time.sleep(HOLD_S)

    in_flight = False
    try:
        task(dict(command='Jx_STATUS', action='WRITE', mode='0TQ'), args.restart)
        for rep in range(1, REPEATS + 1):
            zero()
            print(f'Repeat {rep}/{REPEATS}: {HOLD_A} A hold, {HOLD_S} s each direction', flush=True)
            hold(HOLD_A)
            zero()
            time.sleep(1)
            hold(-HOLD_A)
            zero()
            for findex, freq in enumerate(FREQUENCIES):
                time.sleep(1)
                task(dict(command='Jx_STATUS', action='WRITE', mode='POS'))
                print(f'  {freq:g} Hz sine, {AMPLITUDE_RAD} rad', flush=True)
                in_flight = True
                subprocess.run([str(TOOLS / 'rtttest'), '-n', '-s', str(TABLES),
                                '-i', args.ip, '-o', f'runin-f{findex}-{rep:02d}',
                                json.dumps(signal(freq))], cwd=args.session, check=True)
                zero()
                ANALYZE(find_capture(args.session, findex, rep), freq, 'pos')
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
        parser.exit(1, f'test-run-in: {error}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'test-run-in: interrupted\n')


if __name__ == '__main__':
    main()
