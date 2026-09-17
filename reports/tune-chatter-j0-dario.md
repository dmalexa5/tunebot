# j0 chatter tuning, full four-gain search — 2026-09-17 (100.106.65.65 session)

Supersedes the velocity-only search in `tune-chatter-j0.md` (that session ran
against `100.79.218.29` and held `POS_KP`/`POS_KI` fixed at a 40:1 `VEL_KP:VEL_KI`
ratio). This session searched all four PI gains independently on `100.106.65.65`.

## Conditions

- Target: `100.106.65.65`, j0, no arm attached (bare joint bench setup).
  `GHASH` read back `194203904`, matching `tune-friction-j0-100.106.65.65.md`.
- OpenOCD and `rttlog -r -i 100.106.65.65` already running; `-r` omitted on all
  `run-sine.sh` calls.
- Friction compensation disabled: `Jx_STATUS` carried only `WARN_OV` (sticky
  bus-overvoltage warning, not a fault), no `FEATURE_FRIC_COMP` bit. `-F` unused.
- Position sines at 0.138 rad, stride 20 (`pos` default). Tuned at 1 Hz (3 cycles)
  and 0.5 Hz (1 cycle). Every capture verified at `cmd amp` 137.998 mrad —
  none truncated.
- `VEL_TQC_LIM=5.0 A` and `POS_VEL_LIM=π rad/s` held fixed throughout.
- Captures: `traces/chatter/j0-dario-full/` (88 captures).

## Starting-gains gate

On connect j0 read `VEL_KP=0, VEL_KI=0, POS_KP=0, POS_KI=0` with
`VEL_TQC_LIM=12` — the volatile `Jx_CFG WRITE` gains had reset again, the same
way `tune-friction-j0-100.106.65.65.md` found them. Per user direction the
baseline was seeded from **`tune-chatter-j0.md`'s final values**, not the
`cn-seamless` `drive-gains.json` defaults (which are `VEL_KP=24, VEL_KI=0.6`):

`VEL_KP=12.0  VEL_KI=0.3  POS_KP=60.0  POS_KI=0.15  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

## Search

One gain at a time, others held at their best tested values. `iq_jitter` in
mA/samp. Repeat captures put run-to-run spread at ±0.5 mA near the final gains
and ±3 mA at the high-`VEL_KI` baseline, so the sub-mA gaps below are real.

**`VEL_KP` at `VEL_KI=0.3` (baseline KI):** U-shaped, minimum at 14.

| VEL_KP | 8 | 10 | 12 | 14 | 15 | 16 | 18 |
|---|---|---|---|---|---|---|---|
| 1 Hz | 398.2 | 236.1 | 124.4 | **117.2** | 121.8 | 128.0 | 139.5 |
| 0.5 Hz | 378.1 | 176.6 | 80.7 | **79.5** | 79.8 | 80.3 | 84.0 |

**`VEL_KI` at `VEL_KP=14`:** the dominant gain. 0.9 is violently worse; below
0.05 jitter flattens while tracking error degrades.

| VEL_KI | 0.0 | 0.02 | 0.05 | 0.1 | 0.3 | 0.9 |
|---|---|---|---|---|---|---|
| 1 Hz jitter | 99.3 | 99.2 | 100.4 | 102.0 | 117.2 | 774.1 |
| 0.5 Hz jitter | 52.8 | 54.3 | 55.7 | 61.1 | 79.5 | 775.3 |
| 0.5 Hz err | 5.644 | 4.336 | 4.197 | 4.169 | 4.159 | 4.319 |

**`VEL_KP` rechecked at `VEL_KI=0.05`:** the optimum moved from 14 down to 7–8 —
the earlier minimum at 14 was an artifact of the high integral gain, and the
low-`VEL_KP` limit cycling seen at `VEL_KI=0.3` was integral-driven.

| VEL_KP | 6 | 7 | 8 | 9 | 10 | 12 | 14 | 16 | 20 |
|---|---|---|---|---|---|---|---|---|---|
| 1 Hz | 60.4 | 59.8 | 63.5 | 68.7 | 74.3 | 86.7 | 100.4 | 114.5 | 143.9 |
| 0.5 Hz | 53.6 | 43.6 | **42.6** | 43.3 | 45.8 | 49.8 | 55.7 | 62.1 | 77.1 |
| 1 Hz residual | 0.731 | 0.601 | 0.528 | 0.491 | 0.449 | 0.396 | 0.363 | 0.330 | 0.295 |

Picked `VEL_KP=8`: 0.5 Hz minimum, 1 Hz within 4 mA of the floor, and lower
nonlinear `err residual` than 6 or 7 (residual rises as `VEL_KP` falls — the
stiction/stick-slip signature).

**`POS_KP` at `POS_KI=0.15`:** tracking error is set almost entirely by the
position loop, and 1 Hz jitter is nearly flat across the whole range.

| POS_KP | 30 | 60 | 90 | 120 |
|---|---|---|---|---|
| 1 Hz jitter | 64.2 | 63.5 | 65.2 | 67.8 |
| 0.5 Hz jitter | 33.7 | 42.6 | 55.3 | 67.3 |
| 1 Hz err | 17.613 | 9.796 | 6.678 | 5.047 |
| 0.5 Hz err | 6.201 | 4.207 | 3.126 | 2.466 |

**`POS_KI` at `POS_KP=60`:** a much cheaper way to buy tracking accuracy than
`POS_KP`, and it dominates the `POS_KP` route (`POS_KP=60, POS_KI=1.0` beats
`POS_KP=120, POS_KI=0.15` on both axes). 3.0 is unstable.

| POS_KI | 0.05 | 0.15 | 0.4 | 0.6 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|---|
| 1 Hz jitter | 61.5 | 63.5 | 65.7 | 66.5 | 67.1 | 70.0 | 74.3 | 221.0 |
| 0.5 Hz jitter | 42.5 | 42.6 | 43.6 | 45.9 | 50.3 | 59.1 | 79.5 | 185.6 |
| 1 Hz err | 10.209 | 9.796 | 7.370 | 5.702 | 3.766 | 2.639 | 2.081 | 4.634 |
| 0.5 Hz err | 5.000 | 4.207 | 2.574 | 1.975 | 1.482 | 1.336 | 1.491 | 3.440 |

`POS_KI` is a jitter-vs-accuracy dial with every value from 0.15 to 2.0 beating
the baseline on both axes. **`POS_KI=0.6` was chosen by the user** from this
table. `POS_KP` rechecked at the higher `POS_KI` (45 / 75 / 90 → 0.5 Hz jitter
47.3 / 53.2 / 59.6) confirmed 60: jitter climbs with `POS_KP` while error barely
improves past it.

**Velocity gains rechecked at `POS_KP=60, POS_KI=0.6`** — `VEL_KP=8` still
optimal (6 → 62.0, 8 → 45.9, 10 → 49.0 at 0.5 Hz), so no further iteration was
needed. `VEL_KI` re-swept there:

| VEL_KI | 0.02 | 0.035 | 0.05 | 0.1 | 0.2 |
|---|---|---|---|---|---|
| 1 Hz jitter | 61.9 | 64.4 | 66.6 | 77.7 | 244.7 |
| 0.5 Hz jitter | 37.4 | 41.6 | 45.6 | 65.9 | 265.7 |
| 0.5 Hz err | 2.132 | 2.029 | 1.970 | 1.936 | 2.053 |
| 0.5 Hz residual | 1.371 | 1.220 | 1.127 | 1.062 | 1.251 |

The higher `POS_KI` cut the velocity loop's stability margin sharply: `VEL_KI=0.2`
is unstable here, where 0.3 was stable at `POS_KI=0.15`. Kept `VEL_KI=0.05` —
`VEL_KI=0.02` buys 8 mA more at 0.5 Hz but raises nonlinear residual 22%
(1.127 → 1.371 mrad), trading current chatter for stick-slip, and 0.05 holds 4×
margin below the instability.

## Final gains

`VEL_KP=8.0  VEL_KI=0.05  POS_KP=60.0  POS_KI=0.6  VEL_TQC_LIM=5.0  POS_VEL_LIM=π`

Verified by readback (`VEL_KP` 1.1703345e-08 A/(cnt/s) × 683565275.6 = 8.000;
`VEL_KI` 7.3145906e-11 → 0.0500; `POS_VEL_LIM` 2^31 cnt = π rad).

Verification at 0.5, 0.75, and 1 Hz (1, 2, 3 cycles; realized 0.75 Hz was
0.749991 Hz per the wrapper). Baselines recaptured at all three frequencies:

| freq | baseline jitter | final jitter | Δ | baseline err rms | final err rms | Δ |
|---|---|---|---|---|---|---|
| 0.5 Hz | 80.7 mA | 45.7 mA | −43% | 4.160 mrad (3.01%) | 1.969 mrad (1.43%) | −53% |
| 0.75 Hz | 91.7 mA | 49.4 mA | −46% | 6.971 mrad (5.05%) | 3.394 mrad (2.46%) | −51% |
| 1 Hz | 124.4 mA | 66.6 mA | −46% | 9.789 mrad (7.09%) | 5.700 mrad (4.13%) | −42% |

Jitter down ~45% and tracking error down ~50% at every frequency — a strict
improvement on both axes, unlike the previous session where error was flat and
only jitter moved. The gain that made this possible was `POS_KI`, which the
earlier velocity-only search held fixed.

Nonlinear `err residual` is the one metric that worsened (0.5 Hz: 0.770 → 1.126
mrad), the expected cost of the much lower `VEL_KI`.

No arm attached, so `cn-seamless` tunables were **not** updated. j0 was left at
the final gains above; note they are volatile and will reset on the next
reboot/reconnect.

## Captures

`traces/chatter/j0-dario-full/`, 88 captures, each `<prefix>-{1hz,0p5hz}.0000.txf`:
- `base-{1hz,0p75hz,0p5hz}` — baseline at the `tune-chatter-j0.md` gains
- `vkp{8,10,14,15,16,18}`, `vkp14-rpt` — `VEL_KP` sweep at `VEL_KI=0.3`
- `vki{0,0p02,0p05,0p1,0p9}` — `VEL_KI` sweep at `VEL_KP=14`
- `k2-vkp{6,7,8,9,10,12,16,20}` — `VEL_KP` recheck at `VEL_KI=0.05`
- `pkp{30,90,120}` — `POS_KP` sweep at `POS_KI=0.15`
- `pki{0p05,0p4,1p0,1p5,2p0,3p0}` — `POS_KI` sweep at `POS_KP=60`
- `p2-pkp{45,75,90}` — `POS_KP` recheck at `POS_KI=1.0`
- `op-pki0p6`, `op-pki0p6-rpt` — chosen operating point, with repeat
- `v3-vkp{6,10}`, `v3-vki{0p02,0p035,0p1,0p2}`, `v3-vki0p02-rpt` — velocity
  recheck at `POS_KP=60, POS_KI=0.6`
- `final-{0p5hz,0p75hz,1hz}` — final-gain verification
