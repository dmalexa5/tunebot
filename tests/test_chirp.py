"""Synthetic analysis and isolated RTT-wrapper checks; never contacts hardware."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('chirp', ROOT / 'scripts/txf-chirp.py')
chirp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chirp)


def write_capture(path, signals, dt=0.0001):
    path.mkdir()
    traces = []
    for i, (name, vals) in enumerate(signals.items()):
        filename = f'trace{i}.bin'
        np.asarray(vals, dtype='<f4').tofile(path / filename)
        unit = 'A' if name.startswith('iq') else ('°/s' if 'vel' in name else '°')
        traces.append(dict(name=name, dtype='f32', file=filename, unit=unit,
                           vscale=1, voffset=0, hscale=dt))
    (path / 'metadata.json').write_text(json.dumps(dict(traces=traces)))


class AnalysisTests(unittest.TestCase):
    def test_individual_capture_gain_and_phase(self):
        rng = np.random.default_rng(13)
        x = rng.normal(size=512)
        response = chirp.estimate(np.stack((x, 2 * x)))
        np.testing.assert_allclose(response, 2, atol=1e-12)
        delayed = chirp.estimate(np.stack((x, 3 * np.roll(x, 7))))
        expected = 3 * np.exp(-2j * np.pi * np.fft.rfftfreq(len(x)) * 7)
        np.testing.assert_allclose(delayed[0], expected, atol=1e-12)

    def test_wrapped_positions_and_motor_scaling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'wrapped.txf'
            angles = [170, 179, -175, -165]
            signals = {name: angles for name in chirp.SIGNALS}
            write_capture(path, signals)
            data, dt = chirp.load(path)
            expected = np.deg2rad([170, 179, 185, 195])
            np.testing.assert_allclose(data['opos'], expected)
            np.testing.assert_allclose(data['mpos'], expected / -509.7)
            np.testing.assert_allclose(data['mvel'], np.deg2rad(angles) / -509.7)
            np.testing.assert_allclose(data['iq_cmd'], angles)
            self.assertEqual(dt, 0.0001)

    def test_invalid_capture_rejection(self):
        args = SimpleNamespace(duration_ms=10, stride=2, rest_threshold=0.05)
        with tempfile.TemporaryDirectory() as tmp:
            signals = {name: np.zeros(142) for name in chirp.SIGNALS}
            signals['iq_cmd'][20:120] = np.sin(np.arange(100))
            for issue in ('missing', 'truncated', 'sampling', 'lengths', 'moving', 'partial'):
                with self.subTest(issue=issue):
                    data = {k: v.copy() for k, v in signals.items()}
                    dt = 0.0001
                    if issue == 'missing':
                        del data['mpos']
                    elif issue == 'truncated':
                        data = {k: v[:-5] for k, v in data.items()}
                    elif issue == 'sampling':
                        dt = 0.0002
                    elif issue == 'lengths':
                        data['opos'] = data['opos'][:-1]
                    elif issue == 'moving':
                        data['ovel'][:20] = 10
                    path = Path(tmp) / f'{issue}.txf'
                    write_capture(path, data, dt)
                    if issue == 'partial':
                        with (path / 'trace0.bin').open('ab') as stream:
                            stream.write(b'x')
                    with self.assertRaises(ValueError):
                        chirp.prepare(path, args)
            for n in (141, 142):
                path = Path(tmp) / f'valid-{n}.txf'
                write_capture(path, {k: v[:n] for k, v in signals.items()})
                traces, _ = chirp.prepare(path, args)
                self.assertEqual(traces.shape, (6, 100))


MOCK = '''#!{python}
import json, os, signal, sys
from pathlib import Path
import numpy as np
tool = Path(sys.argv[0]).name
with open(os.environ['MOCK_LOG'], 'a') as stream:
    stream.write(json.dumps(dict(tool=tool, args=sys.argv[1:])) + '\\n')
if tool != 'rtttest':
    sys.exit(0)
if os.environ.get('MOCK_MODE') == 'interrupt':
    os.kill(os.getppid(), signal.SIGTERM)
    sys.exit(1)
if os.environ.get('MOCK_MODE') == 'fail':
    sys.exit(2)
prefix = sys.argv[sys.argv.index('-o') + 1]
command = json.loads(sys.argv[-1])
assert command['signal'] == 'iq' and command['log'] and not command['taper']
n = 142
if os.environ.get('MOCK_MODE') == 'truncate' and prefix == 'chirp-002':
    n = 130
path = Path(prefix + '.0000.txf')
path.mkdir()
traces = []
x = np.zeros(n)
x[20:120] = command['amplitude'] * np.sin(np.arange(100))
for i, name in enumerate(('iq_cmd', 'iq_fbk', 'mvel', 'ovel', 'mpos', 'opos')):
    filename = 'trace%d.bin' % i
    (x * (i + 1)).astype('<f4').tofile(path / filename)
    unit = 'A' if name.startswith('iq') else ('°/s' if 'vel' in name else '°')
    traces.append(dict(name=name, dtype='f32', file=filename, unit=unit,
                       hscale=0.0001))
(path / 'metadata.json').write_text(json.dumps(dict(traces=traces)))
'''


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo = root / 'tunebot'
        scripts = self.repo / 'scripts'
        scripts.mkdir(parents=True)
        for name in ('run-chirp.sh', 'txf-chirp.py'):
            shutil.copy2(ROOT / 'scripts' / name, scripts / name)
        (self.repo / '.venv').symlink_to(ROOT / '.venv', target_is_directory=True)
        tools = root / 'module-fwpp/tools/rttcmd'
        tools.mkdir(parents=True)
        for name in ('rtttest', 'rtttask', 'sleep'):
            file = tools / name
            file.write_text(MOCK.format(python=sys.executable))
            file.chmod(0o755)
        self.log = root / 'calls.jsonl'
        self.env = dict(os.environ, MOCK_LOG=str(self.log),
                        PATH=str(tools) + os.pathsep + os.environ['PATH'])
        self.command = ['zsh', str(scripts / 'run-chirp.sh'), '-i', 'mock-host', '-r',
                        '.3', '10', '2000', '10', '3', '2', 'traces/session']

    def run_wrapper(self, mode=''):
        return subprocess.run(self.command, cwd=self.repo, env=dict(self.env, MOCK_MODE=mode),
                              capture_output=True, text=True, timeout=30)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_repeated_commands_plot_and_cleanup(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        captures = [c for c in calls if c['tool'] == 'rtttest']
        self.assertEqual(len(captures), 3)
        commands = [json.loads(c['args'][-1]) for c in captures]
        self.assertTrue(all(c == commands[0] for c in commands))
        self.assertEqual(commands[0]['start_pad'], 40)
        self.assertEqual(commands[0]['end_pad'], 40)
        self.assertEqual(sum('-r' in c['args'] for c in calls), 1)
        self.assertEqual(json.loads(calls[-1]['args'][-1])['iq'], 0)
        session = self.repo / 'traces/session'
        for trial in range(1, 4):
            png = session / f'chirp-{trial:03d}.0000.png'
            self.assertTrue(png.read_bytes().startswith(b'\x89PNG'))
        self.assertFalse((session / 'chirp.png').exists())

    def test_truncation_stops_and_preserves_raw_captures(self):
        result = self.run_wrapper('truncate')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('truncated', result.stderr)
        calls = self.calls()
        self.assertEqual(sum(c['tool'] == 'rtttest' for c in calls), 2)
        self.assertIn(dict(tool='sleep', args=['4']), calls)
        session = self.repo / 'traces/session'
        self.assertEqual(len(list(session.glob('*.txf'))), 2)
        self.assertFalse(list(session.glob('*.png')))
        self.assertEqual(json.loads(calls[-1]['args'][-1])['iq'], 0)

    def test_failure_and_interruption_cleanup(self):
        for mode in ('fail', 'interrupt'):
            with self.subTest(mode=mode):
                self.command[-1] = f'traces/{mode}'
                result = self.run_wrapper(mode)
                self.assertNotEqual(result.returncode, 0)
                calls = self.calls()
                self.assertIn(dict(tool='sleep', args=['4']), calls)
                self.assertEqual(json.loads(calls[-1]['args'][-1])['iq'], 0)

    def test_invalid_settings_do_not_touch_hardware(self):
        self.command[-3] = '1'
        result = self.run_wrapper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
