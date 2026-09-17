"""Friction input selection checks using synthetic captures; no hardware."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('breakaway', ROOT / 'scripts/txf-breakaway.py')
breakaway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(breakaway)


def write_capture(path, signals):
    path.mkdir()
    traces = []
    for i, (name, values) in enumerate(signals.items()):
        filename = f'trace{i}.bin'
        (path / filename).write_bytes(struct.pack('<' + 'f' * len(values), *values))
        traces.append(dict(name=name, dtype='f32', file=filename,
                           unit='rad/s' if 'vel' in name else 'A', hscale=0.001))
    (path / 'metadata.json').write_text(json.dumps(dict(traces=traces)))


class FrictionTests(unittest.TestCase):
    def test_motor_input_and_presliding_values_in_both_directions(self):
        for direction in (1, -1):
            with self.subTest(direction=direction), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'ramp.txf'
                motor = [direction * v for v in [0, .01, .02, .1, .2, .3]]
                signals = dict(iq_cmd=[0] * 20 + list(range(6)) + [0] * 20,
                               iq_fbk=[0] * 20 + [direction * .5] * 6 + [0] * 20,
                               mvel_filt=[0] * 20 + motor + [0] * 20,
                               ovel=[9] * 46, vel_fbk=[-9] * 46, mvel=[99] * 46)
                write_capture(path, signals)
                result = breakaway.analyze(str(path))
                self.assertAlmostEqual(result['breakaway_time'], .003)
                for actual, expected in zip(result['presliding_w'], motor[:4]):
                    self.assertAlmostEqual(actual, expected)
                self.assertEqual(result['presliding_i'], [direction * .5] * 4)

    def test_missing_motor_input_rejected_despite_other_channels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'old.txf'
            write_capture(path, dict(iq_cmd=[0] * 46, ovel=[1] * 46,
                                     vel_fbk=[1] * 46, mvel=[1] * 46))
            with self.assertRaisesRegex(ValueError, 'lacks mvel_filt; recapture'):
                breakaway.analyze(str(path))

    def test_output_motion_does_not_trigger_motor_breakaway(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'still.txf'
            write_capture(path, dict(iq_cmd=[0] * 46, mvel_filt=[0] * 46,
                                     ovel=[10] * 46, vel_fbk=[10] * 46))
            with self.assertRaisesRegex(ValueError, 'no breakaway detected'):
                breakaway.analyze(str(path))


if __name__ == '__main__':
    unittest.main()
