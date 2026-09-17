"""Synthetic capture checks for the production Python Stribeck fitter."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from test_friction import write_capture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stribeck', ROOT / 'scripts/fit_stribeck.py')
stribeck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stribeck)


class StribeckTests(unittest.TestCase):
    def test_bidirectional_motor_curve_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            parameters = [1.2, 2.0, 0.08, 0.7]
            speeds = np.array([.01, .02, .04, .08, .15, .3, .6, .875])
            for direction in (-1, 1):
                for k, speed in enumerate(speeds):
                    current = direction * (1.2 + .8 * np.exp(-(speed / .08)**2) + .7 * speed)
                    # Corrupt pads and initial transient: neither belongs in the mean.
                    motor = [9] * 320 + [direction * speed] * 700 + [9] * 20
                    iq = [-9] * 320 + [current] * 700 + [-9] * 20
                    write_capture(Path(tmp) / f'hold{direction}_{k}.txf',
                                  dict(mvel_filt=motor, iq_fbk=iq,
                                       ovel=[9] * 1040, vel_fbk=[-9] * 1040,
                                       mvel=[99] * 1040))
            pattern = str(Path(tmp) / '*.txf')
            result = stribeck.fit_stribeck(pattern)
            np.testing.assert_allclose([result[key] for key in
                                        ('Ic', 'Is', 'stribeck_vel', 'sig2')],
                                       parameters, atol=1e-4)
            np.testing.assert_allclose(sorted(result['signed_w']), sorted(np.r_[-speeds, speeds]), atol=1e-7)
            np.testing.assert_allclose(result['I'], np.array(result['signed_I']) * np.sign(result['signed_w']))
            completed = subprocess.run([sys.executable, stribeck.__file__, pattern],
                                       capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(completed.stdout), result)

    def test_missing_motor_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_capture(Path(tmp) / 'old.txf', dict(iq_fbk=[1] * 1040,
                          ovel=[.1] * 1040, vel_fbk=[.1] * 1040, mvel=[99] * 1040))
            with self.assertRaisesRegex(ValueError, 'lacks mvel_filt; recapture'):
                stribeck.fit_stribeck(str(Path(tmp) / '*.txf'))

    def test_invalid_hold_windows_and_zero_motion(self):
        for n, speed, message in ((40, .1, 'too short'),
                                  (100, .1, 'settle skip'),
                                  (1040, 0, 'cannot determine motion direction')):
            with self.subTest(n=n, speed=speed), tempfile.TemporaryDirectory() as tmp:
                write_capture(Path(tmp) / 'hold.txf', dict(mvel_filt=[speed] * n, iq_fbk=[1] * n))
                with self.assertRaisesRegex(ValueError, message):
                    stribeck.fit_stribeck(str(Path(tmp) / '*.txf'))


if __name__ == '__main__':
    unittest.main()
