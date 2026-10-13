"""Tracking checks with synthetic captures; never contacts hardware."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tracking', ROOT / 'scripts/test-tracking.py')
tracking = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracking)


def write_capture(path, frequency, truncate=False):
    path.mkdir()
    n = tracking.COUNT + 2 * tracking.EDGE + 1
    command = np.full(n, 3.1)
    t = np.arange(tracking.COUNT) * .001
    command[20:3020] += .25 * np.sin(2 * np.pi * frequency * t)
    feedback = command + .02
    # Independently wrap both traces to exercise the encoder boundary.
    traces = []
    for i, (name, values) in enumerate((('pos_cmd', command), ('opos', feedback))):
        values = np.rad2deg((values + np.pi) % (2 * np.pi) - np.pi)
        if truncate:
            values = values[:-100]
        filename = f'trace{i}.bin'
        values.astype('<f4').tofile(path / filename)
        traces.append(dict(name=name, file=filename, dtype='f32', unit='°', hscale=.001))
    (path / 'metadata.json').write_text(json.dumps(dict(traces=traces)))


class TrackingTests(unittest.TestCase):
    def test_error_across_wrap_and_reject_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / 'valid.txf'
            write_capture(capture, .1)
            peak, average = tracking.errors(capture)
            self.assertAlmostEqual(peak, .02, places=6)
            self.assertAlmostEqual(average, .02, places=6)
            capture = Path(tmp) / 'short.txf'
            write_capture(capture, .1, truncate=True)
            with self.assertRaisesRegex(ValueError, 'truncated'):
                tracking.errors(capture)

    def test_ten_fixed_frequencies_and_single_plot(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / 'session'
            args = SimpleNamespace(session=session, ip='mock', restart=True, ctrl=[])
            calls = []

            def run(command, **kwargs):
                payload = json.loads(command[-1])
                calls.append((command, payload))
                if payload.get('test'):
                    prefix = command[command.index('-o') + 1]
                    write_capture(session / f'{prefix}.0000.txf', payload['f0_hz'])

            with patch.object(tracking.subprocess, 'run', side_effect=run), \
                    patch.object(tracking.time, 'sleep'):
                tracking.capture(args)
            waveforms = [p for _, p in calls if p.get('test')]
            self.assertEqual(len(waveforms), 10)
            np.testing.assert_allclose([p['f0_hz'] for p in waveforms], np.linspace(.1, .6, 10))
            for payload in waveforms:
                self.assertEqual(payload['test'], 'signal_chirp')
                self.assertEqual(payload['signal'], 'pos')
                self.assertEqual(payload['f0_hz'], payload['f1_hz'])
                self.assertFalse(payload['log'])
                self.assertFalse(payload['taper'])
                self.assertEqual(payload['duration_ms'], 3000)
                self.assertAlmostEqual(payload['amplitude'] * 2 * np.pi / 4294967296, .25)
            self.assertEqual(sum('-r' in c for c, _ in calls), 1)
            self.assertEqual(calls[-1][1]['iq'], 0)
            self.assertEqual(len(list(session.glob('*.txf'))), 10)
            self.assertEqual(list(session.glob('*.png')), [session / 'tracking.png'])
            self.assertTrue((session / 'tracking.png').read_bytes().startswith(b'\x89PNG'))

    def test_failure_stops_and_waits_for_waveform(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = SimpleNamespace(session=Path(tmp) / 'session', ip='mock',
                                   restart=False, ctrl=[])
            calls = []

            def run(command, **kwargs):
                payload = json.loads(command[-1])
                calls.append(payload)
                if payload.get('test'):
                    raise tracking.subprocess.CalledProcessError(1, command)

            with patch.object(tracking.subprocess, 'run', side_effect=run), \
                    patch.object(tracking.time, 'sleep') as sleep:
                with self.assertRaises(tracking.subprocess.CalledProcessError):
                    tracking.capture(args)
            self.assertEqual(sum('test' in p for p in calls), 1)
            sleep.assert_any_call(4)
            self.assertEqual(calls[-1]['iq'], 0)


if __name__ == '__main__':
    unittest.main()
