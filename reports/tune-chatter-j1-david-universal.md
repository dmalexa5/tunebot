# j1 chatter tuning, universal arm attached — 2026-09-18

No prior `tune-chatter-j1-*.md` report existed, so the baseline was seeded from
`../cn-seamless/configs/tunables/drive-gains.json` (joint 1, universal-arm
table), not from another session's final gains.

**Mid-session velocity feedback switch.** Partway through tuning, the user
switched the velocity loop's feedback source from the output encoder (`ovel`,
`SERVO_FLAG_VEL_SRC_MENC` clear) to the motor encoder (`mvel`, flag set —
`module-fwpp src/servo.h:68`: "rotor-side, higher bandwidth, blind to the
gear... the two generally want different gains"). Live gains survived the
switch (no RTT reset), but re-running the last-good point (`POS_KI=7.0`,
otherwise stable under `ovel`) immediately showed oscillation (jitter jumped
100→405 mA, err residual 0.35→10.7 mrad), confirming the switch changed loop
dynamics enough to invalidate everything tuned so far. All pre-switch captures
were deleted per user request and the search restarted from a fresh baseline
under `mvel`. Every number below is post-switch (`mvel`) unless noted.

## Conditions

- Target: `100.79.218.29`, j1, **universal arm attached**.
- OpenOCD and the RTT server (`rttlog -r`) already running; `-r` omitted on
  all `run-sine.sh`/`set-gains.sh` calls.
- No friction compensation used (`-F` omitted throughout, per this skill's
  current instructions).
- Position sines at 0.138 rad amplitude, stride 20 (default for `pos`).
  Command amplitude verified at 137.998 mrad (138.034 at 0.75 Hz) on every
  capture; no truncated captures.
- `VEL_TQC_LIM = 5.0 A` and `POS_VEL_LIM = π rad/s` held fixed throughout.
- Search captures: 3 cycles at 1 Hz, 1 cycle at 0.5 Hz (stride-20 timeline
  cap); the analyzer drops the first cycle as an acquisition transient, so
  1 Hz results reflect 2 analyzed cycles.
- Captures: `traces/j1-david-universal/`.

## Baseline (post-switch, `mvel`)

Live gains read 0 over RTT at session start (RAM-only, expected). Seeded from
tunables: `VEL_KP=13.0  VEL_KI=0.3  POS_KP=60.0  POS_KI=1.0  VEL_TQC_LIM=5.0
POS_VEL_LIM=π`.

| freq | jitter | err rms |
|---|---|---|
| 0.5 Hz | 115.0 mA | 1.289 mrad (0.93%) |
| 1 Hz | 216.3 mA | 3.725 mrad (2.70%) |

## Search

Jitter in mA/samp, error as rms mrad (% of command amplitude), all at 1 Hz
unless noted. One gain varied at a time, others held at their best tested
values.

### 1. `VEL_KP`, with `VEL_KI=0.3`, `POS=(60, 1.0)`

| VEL_KP | jitter | err |
|---|---|---|
| 4 | 502.7 | 2.95% |
| 6 | 418.3 | 2.81% |
| 7 | 394.4 | 2.77% |
| 8 | 226.5 | 2.71% |
| **9** | **169.6** | **2.70%** |
| 10 | 170.1 | 2.70% |
| 11 | 184.6 | 2.70% |
| 13 (baseline) | 215.0 | 2.70% |
| 15 | 248.9 | 2.70% |
| 20 | 348.4 | 2.70% |
| 27 | 518.6 | 2.70% |
| 33 | 700.3 | 2.70% |

Tracking is flat once `VEL_KP >= 8`; jitter has a narrow notch at 9–10, not a
smooth monotonic trend, with a steep wall on both sides. Took 9.

### 2. `VEL_KI`, with `VEL_KP=9`, `POS=(60, 1.0)`

| VEL_KI | jitter | err |
|---|---|---|
| 0.0 | 129.3 | 3.76% |
| 0.05 | 130.8 | 2.73% |
| **0.1** | **135.1** | **2.71%** |
| 0.2 | 143.6 | 2.70% |
| 0.5 | 511.3 | 2.75% |

`VEL_KI=0.0` regresses tracking (loses steady-state velocity accuracy); 0.1
is the lowest value that fully preserves baseline tracking, at less than
two-thirds of the baseline's jitter. Took 0.1 — no ambiguous trade here, it
dominates baseline on both axes.

### 3. `POS_KP`, with `VEL=(9, 0.1)`, `POS_KI=1.0`

| POS_KP | jitter | err |
|---|---|---|
| 30 | 133.0 | 2.87% |
| **60 (baseline)** | **134.2** | **2.71%** |
| 90 | 134.7 | 2.50% |
| 120 | 136.1 | 2.28% |
| 150 | 139.8 | 2.07% |

Jitter is essentially flat across this whole range (133–140); `POS_KP` mainly
trades tracking error, not jitter. Kept baseline 60 — it already matches
baseline tracking at the lowest jitter in the set. (Going higher is a nearly-free
tracking improvement if wanted; not required by the "preserve tracking"
constraint, so not taken.)

### 4. `POS_KI`, with `VEL=(9, 0.1)`, `POS_KP=60`

| POS_KI | jitter | err |
|---|---|---|
| 0.15 | 133.0 | 7.09% |
| 0.5 | 136.3 | 4.68% |
| 1.0 (baseline) | 134.2 | 2.71% |
| 1.5 | 133.8 | 1.87% |
| 2.0 | 133.4 | 1.42% |
| 3.0 | 135.8 | 1.00% |
| 4.0 | 149.9 | 0.90% |
| 5.0 | 361.2 | 10.47% |
| 6.0 | 373.0 | 12.30% |

Jitter is flat (~133–136) from 0.15 to 3.0, then rises as `POS_KI` approaches
an instability cliff: stable and clean through 4.0, collapsed by 5.0 (jitter
+140%, err residual dominated by non-linear/oscillatory content). Below 1.0
the loop under-tracks from lack of integral action; above 3.0 the loop
improves tracking further but is progressively closer to the cliff.

### 5. `VEL_KP` recheck, with `VEL_KI=0.1`, `POS=(60, 3.0)`

| VEL_KP | jitter | err |
|---|---|---|
| 6 | 155.2 | 1.30% |
| 7 | 129.7 | 1.11% |
| **8** | **126.8** | **1.03%** |
| 9 | 136.2 | 1.00% |
| 10 | 148.6 | 0.99% |

The optimum shifted from 9 down to 8 once `POS_KI` moved to 3.0 — the
instruction to recheck velocity gains after position tuning mattered here.
Took 8.

### 6. `VEL_KI` recheck, with `VEL_KP=8`, `POS=(60, 3.0)`

| VEL_KI | jitter | err |
|---|---|---|
| 0.05 | 123.2 | 1.17% |
| **0.1** | **127.0** | **1.03%** |
| 0.2 | 136.9 | 0.95% |

0.1 remains the balanced pick: 0.05 saves a little jitter for worse tracking,
0.2 the reverse. Kept 0.1.

### 7. `POS_KI` final candidates, with `VEL=(8, 0.1)`, `POS_KP=60`

| POS_KI | jitter | err |
|---|---|---|
| **3.0** | **127.0** | **1.03%** |
| 4.0 | 144.5 | 0.95% |
| 4.5 | 182.6 | 1.14% |

4.5 already degrades in *both* jitter and tracking — past the sweet spot,
close to the 5.0 instability cliff found in step 4. Presented 3.0 (lower
jitter) vs. 4.0 (better tracking) to the user; **user chose 3.0.**

## Final gains

`VEL_KP=8.0  VEL_KI=0.1  POS_KP=60.0  POS_KI=3.0  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

Verified at 0.5, 0.75, and 1 Hz (1, 2, and 3 cycles; realized 0.75 Hz was
0.749991 Hz):

| freq | jitter | vs. baseline | err rms | vs. baseline |
|---|---|---|---|---|
| 0.5 Hz | 81.3 mA | −29.3% (was 115.0) | 0.965 mrad (0.70%) | −24.7% (was 0.93%) |
| 0.75 Hz | 90.0 mA | — (no baseline capture) | 0.833 mrad (0.60%) | — |
| 1 Hz | 127.0 mA | −41.3% (was 216.3) | 1.422 mrad (1.03%) | −61.9% (was 2.70%) |

Final gains beat the `mvel` baseline on both jitter and tracking at every
frequency tested — no regression trade needed at the chosen operating point.

Universal arm was attached, so `../cn-seamless/configs/tunables/drive-gains.json`
joint 1 was updated: `VEL_KP` 13.0→8.0, `VEL_KI` 0.3→0.1, `POS_KP` unchanged
at 60.0, `POS_KI` 1.0→3.0. `VEL_TQC_LIM`/`POS_VEL_LIM` left unchanged
(5.0/π). j1 was left live at the final gains above.

## Captures

`traces/j1-david-universal/` — all post-`mvel`-switch (pre-switch captures
were deleted mid-session at user request to avoid confusion):

- `psine_mvel_base_{1hz,0p5hz}` — baseline (`VEL=13/0.3`, `POS=60/1.0`) under `mvel`
- `psine_mvelcheck_1hz` — spot check that confirmed the switch changed dynamics
  (captured at the pre-switch `POS_KI=7.0` point)
- `psine_m_vkp{4,5,6,7,8,9,10,11,13,15,17,20,27,33}_1hz` — `VEL_KP` sweep
- `psine_m_vki{0.0,0.05,0.1,0.2,0.5}_1hz` — `VEL_KI` sweep at `VEL_KP=9`
- `psine_m_pkp{30,60,90,120,150}_1hz` — `POS_KP` sweep
- `psine_m_pki{0.15,0.5,1.5,2.0,3.0,4.0,4.5,5.0,6.0}_1hz` — `POS_KI` sweep
- `psine_m_rc_vkp{6,7,8,9,10}_1hz` — `VEL_KP` recheck at `POS=(60,3.0)`
- `psine_m_rc_vki{0.05,0.1,0.2}_1hz` — `VEL_KI` recheck at `VEL_KP=8`
- `psine_m_final_pki{4.0,4.5}_1hz` — final `POS_KI` candidate table at `VEL=(8,0.1)`
- `psine_final_{0p5hz,0p75hz}`, `psine_m_rc_vki0.1_1hz` (1 Hz) — final-gain verification
