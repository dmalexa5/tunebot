# Tunebot

Host-side RTT capture and analysis tools for CNS drive joints; no build step.
Step/ramp/sine Python analyzers use only the standard library. Chirp analysis
requires NumPy and Matplotlib (`.venv/bin/python -m pip install -r requirements.txt`).
Python Stribeck fitting requires SciPy from `requirements.txt`.
MATLAB LuGre fits require Optimization Toolbox.

## Setup

- Sibling `../module-fwpp` supplies RTT tools, tables, and firmware.
  Its `cheatsheet.md` documents the raw protocol; `src/servo.c` implements the PID cascade.
- Before hardware tests, confirm OpenOCD is running; do not start it yourself.
  Use `DEBUG=1`, `TRACE=MECH` firmware and verify non-zero servo gains.
- Run `source env.zsh` for script access; run `startup.m` in MATLAB for its MCP server.
- Captures are `.txf` directories written to the current directory.
  Store them in `traces/<session>/`; write concise results in `reports/`.

See [cheatsheet.md](cheatsheet.md) for commands and capture constraints.
Workflows: [chatter](.claude/skills/tune-chatter/SKILL.md),
[friction](.claude/skills/tune-friction/SKILL.md),
[chirp](.claude/skills/test-chirp/SKILL.md).

## Analysis invariants

- Loaders convert metadata degree units to radians and alias `opos`/`ovel`
  to `pos_fbk`/`vel_fbk` only when those feedback names are absent.
  `vel_fbk` is loop feedback; `ovel` measures output-shaft motion.
- Step/ramp/sine analyzers assume 20 captured samples of baseline and tail,
  matching wrapper pads of `20 * stride` servo ticks.
- Loader logic is repeated across Python analyzers and `txf_load.m`;
  format changes must keep them consistent.
