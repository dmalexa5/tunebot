#!/usr/bin/env python3
"""menc-calibration.py -- end-to-end MA600 calibration for one joint.

  menc-calibration [-i IP] --joint {0,1}

Needs OpenOCD and RTT up. Flashes module-fwpp (DEBUG=1) three times:
TRACE=MECH, TRACE=ILOOP for the offset, then TRACE=MECH again.

  1. BCT: CORR zero, holds at the joint's start BCT and at start+6, solve the
     2fe null (menc-cal.py bct), set it, holds again.
  2. CORR: table from that fit, holds, measure the CORR gain, refined table,
     holds. Keeps whichever of {zero, first, refined} has the lowest error rms,
     then HIZ and SAVE BCT + CORR to MA600 NVM (no prompt): some boards reset
     the chip on reflash, which reloads the trim from NVM.
  3. MENC_OFFSET (ILOOP): vd-null across offsets around the booted value,
     iterated to the zero crossing (menc-offset.py method).
  4. Reflash MECH, set the offset, verify holds, then on y: HIZ and SAVE
     MENC_OFFSET (board nvdata).

Step 0 ramps iq open-loop each way to find breakaway; holds run at 1.2/1.3/1.4x
the larger value, and the offset holds at 1.4x. Holds are open-loop torque, +I then -I at each level, so net rotation stays near
zero. Captures and report.md go to traces/<date-time>-j<N>-menc/.
"""
import argparse, importlib.util, json, os, re, shutil, subprocess, sys, time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
FW = ROOT.parent / "module-fwpp"
RTT = FW / "tools/rttcmd"
TABLES = FW / "output/drive/none/drive-none.tables.json"

START_BCT = {0: 43, 1: 40}     # module-fwpp tune commits (see set-menc-default)
BCT_STEP = 6                   # second BCT point for the slope
LEVEL_MULT = (1.2, 1.3, 1.4)   # hold currents as multiples of breakaway, each +I then -I
BKW_RAMP_A = 1.0               # breakaway ramp: 0 to ±BKW_RAMP_A over BKW_RAMP_MS
BKW_RAMP_MS = 2000
BKW_VEL = 0.05                 # breakaway threshold on |mvel_filt| [rad/s, output]
OFF_STEP = 250                 # initial offset bracket [counts]
OFF_TOL = 10                   # offset convergence [counts]
SETTLE_S = 2                   # spin-up before a capture (short: limits cable wind-up)
RUNDOWN_S = 3                  # coast-down after zeroing torque
CAPTURE_MS = 1000              # hold capture length
STRIDE = 8                     # stride 4 truncates; 1 s at stride 8 = 2500 records
RECORDS = CAPTURE_MS * 20 // STRIDE

def load(name):
	spec = importlib.util.spec_from_file_location(name.replace("-", "_"), SCRIPTS / f"{name}.py")
	m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
	return m

mc = load("menc-cal")
mo = load("menc-offset")
mb = load("txf-breakaway")
IP = "127.0.0.1"
levels = []                    # LEVEL_MULT x breakaway, set in main()
off_level = 0.0                # top hold level, set in main()
board_id = 0                   # build guess; flash() corrects it from the board
report = []

def log(s=""):
	print(s, flush=True); report.append(s)

def die(msg):
	log(f"\n**ABORT:** {msg}")
	Path("report.md").write_text("\n".join(report) + "\n")
	sys.exit(msg)

# --- drive I/O --------------------------------------------------------------

def task(req):
	r = json.loads(subprocess.check_output([str(RTT / "rtttask"), "-i", IP, json.dumps(req)]))
	if r.get("action") == "ERR":
		die(f"{req} -> {r}")
	return r

def cfg(action, addr, val=0):
	return task({"command": "Jx_CFG", "action": action, "addr": addr, "val": val})["data"]["val"]

def status(ctrl=None):
	if ctrl is None:
		return task({"command": "Jx_STATUS", "action": "READ"})["data"]
	return task({"command": "Jx_STATUS", "action": "WRITE", "ctrl": ctrl, "mode": "FOC"})["data"]

def power_on():
	status(["CLR_FAULT"]); time.sleep(1)
	st = status()
	if st["outp"] != "ON":
		die(f"power stage not ON: {st}")

def hiz():
	st = status(["SET_HIZ"])
	if st["outp"] != "HIZ":
		die(f"drive not in HIZ: {st}")

def read_trim():
	bct = cfg("READ", "MA600A_REG_BCT")
	corr = [cfg("READ", "MA600A_REG_CORR", i << 8) & 0xFF for i in range(32)]
	return bct, [v - 256 if v > 127 else v for v in corr]

def write_trim(bct, corr):
	"""Shadow registers only (HIZ while the angle stream pauses), then ON."""
	hiz()
	cfg("WRITE", "MA600A_REG_BCT", bct)
	for i, v in enumerate(corr):
		cfg("WRITE", "MA600A_REG_CORR", (i << 8) | (v & 0xFF))
	if read_trim() != (bct, list(corr)):
		die(f"trim readback mismatch: wrote BCT {bct} CORR {corr}, read {read_trim()}")
	power_on()

def read_board_id():
	"""BOARD_ID the firmware read from the ID pins (RAM, via the openocd console)."""
	nm = subprocess.check_output(["arm-none-eabi-nm", str(FW / "output/drive/none/drive-none.elf")], text=True)
	addr = next(l.split()[0] for l in nm.splitlines() if l.endswith(" BOARD_ID"))
	out = subprocess.run(["nc", "-w", "3", IP, "4444"], input=f"mdb 0x{addr} 1\nexit\n".encode(),
	                     capture_output=True).stdout.decode("latin-1")
	m = re.search(r"0x[0-9a-fA-F]+:\s+([0-9a-fA-F]{2})", out)
	if not m:
		die(f"could not read BOARD_ID: {out!r}")
	return int(m.group(1), 16)

def flash(trace):
	"""A binary built for the wrong board ID mis-scales vbus (latched FAULT_OV)
	and drives the wrong OENC chip select, so check and rebuild once."""
	global board_id
	print(f"\n== flash TRACE={trace} BOARD_ID={board_id}", flush=True)
	env = os.environ | {"TRACE": trace, "BOARD_ID": str(board_id)}
	r = subprocess.run(["zsh", str(SCRIPTS / "menc-flash.sh"), "-i", IP], env=env)
	found = read_board_id()
	if found != board_id:
		print(f"board reports BOARD_ID {found}, binary built for {board_id}: rebuilding", flush=True)
		board_id = found
		r = subprocess.run(["zsh", str(SCRIPTS / "menc-flash.sh"), "-i", IP], env=env | {"BOARD_ID": str(found)})
		if read_board_id() != board_id:
			die("BOARD_ID still mismatched after rebuild")
	if r.returncode:
		die(f"menc-flash.sh TRACE={trace} BOARD_ID={board_id} failed")
	want = {"MECH": "mech_trace", "ILOOP": "foc_trace"}[trace]
	if json.load(open(TABLES))["rtttrace"]["name"] != want:
		die(f"tables.json is not {want}")

# --- captures ---------------------------------------------------------------

def zero():
	subprocess.run([str(RTT / "rtttask"), "-i", IP, json.dumps(
		{"command": "Jx_TQC", "action": "WRITE", "pos": 0, "vel": 0, "trq": 0, "ctrl": ["ENABLE"]})],
		capture_output=True)

def holds(label, levels):
	"""Constant-torque holds, +I then -I per level; returns capture dirs."""
	status(["ENABLE"]); zero(); time.sleep(RUNDOWN_S)
	try:
		for I in levels:
			for d, s in (("f", 1), ("r", -1)):
				for attempt in (1, 2):   # RTT drops the odd capture; retry once
					subprocess.run([str(RTT / "rtttest"), "-i", IP, "-s", str(TABLES), json.dumps(
						{"test": "signal_ramp", "signal": "iq", "step": s * I, "slope_samples": 10000,
						 "duration": 10000, "flags": 0})], check=True, capture_output=True)
					time.sleep(SETTLE_S)
					out = subprocess.run([str(SCRIPTS / "run-trace.sh"), "-i", IP, "torque", str(STRIDE),
					                      f"{label}_{d}{I}", str(CAPTURE_MS)], capture_output=True, text=True)
					last = (out.stdout + out.stderr).strip().splitlines()[-1:] or [""]
					print("  " + last[0], flush=True)
					zero(); time.sleep(RUNDOWN_S)
					if f"({RECORDS} records)" in last[0] or f"({RECORDS + 1} records)" in last[0]:
						break
					if attempt == 2:
						die(f"short capture {label}_{d}{I} twice: {last[0]}")
					for c in Path().glob(f"{label}_{d}{I}.*.txf"):
						shutil.rmtree(c)
					print("  short capture removed; retrying", flush=True)
	finally:
		zero()
	return sorted(str(p) for p in Path().glob(f"{label}_*.txf"))

def fitset(label):
	print(f"\n== holds {label}", flush=True)
	mc.fit(NS(ip=IP, label=label, caps=holds(label, levels)))
	return label + ".fit.json"

def summary(fit):
	F = json.load(open(fit)); E = mc.jc(F["E"])
	th = np.linspace(0, 2 * np.pi, 360, endpoint=False)
	rms = float(np.sqrt(np.mean(mc.synth(E, th) ** 2)))
	return rms, f"| {F['label']} | {F['bct']} | {'zero' if not any(F['corr']) else 'set'} | " \
	            f"{abs(E[0]):.3f} | {abs(E[1]):.3f} | {abs(E[3]):.3f} | {rms:.3f} |"

def log_fits(fits):
	log("| set | BCT | CORR | 1fe ° | 2fe ° | 4fe ° | rms ° |")
	log("|---|---|---|---|---|---|---|")
	for f in fits:
		log(summary(f)[1])

def breakaway():
	"""Open-loop iq ramp each way; returns the larger |iq| at breakaway [A]."""
	out = []
	for d, s in (("f", 1), ("r", -1)):
		r = subprocess.run([str(SCRIPTS / "run-ramp.sh"), "-i", IP, "torque", str(s * BKW_RAMP_A),
		                    str(BKW_RAMP_MS), "0", str(STRIDE), f"bkw_{d}"], capture_output=True, text=True)
		zero(); time.sleep(RUNDOWN_S)
		cap = sorted(Path().glob(f"bkw_{d}.*.txf"))
		if r.returncode or not cap:
			die(f"breakaway ramp {d} failed: {(r.stdout + r.stderr).strip()[-300:]}")
		try:
			ib = abs(mb.analyze(str(cap[-1]), BKW_VEL)["breakaway_current"])
		except ValueError as e:
			die(f"breakaway {d}: {e}")
		log(f"| {'+' if s > 0 else '−'} | {ib:.3f} |")
		out.append(ib)
	return max(out)

# --- offset -----------------------------------------------------------------

def offset_point(o):
	if not -32768 <= o <= 32767:
		die(f"MENC_OFFSET {o} out of int16 range")
	print(f"\n== offset {o}", flush=True)
	cfg("WRITE", "MENC_OFFSET", o)
	caps = holds(f"off{o}", [off_level])
	f, r = (mo.means(next(c for c in caps if f"_{d}" in c)) for d in "fr")
	s = f["vd"] / abs(f["mvel"]) - r["vd"] / abs(r["mvel"])
	log(f"| {o} | {s * 1e6:+.3f} | {f['mvel']:+.0f} | {r['mvel']:+.0f} |")
	return s

def find_offset(o0):
	log("| MENC_OFFSET | odd vd/|mvel| [1e-6] | mvel + | mvel − |")
	log("|---|---|---|---|")
	pts = {o: offset_point(o) for o in (o0 - OFF_STEP, o0, o0 + OFF_STEP)}
	est = o0
	for _ in range(4):
		near = sorted(pts, key=lambda o: abs(o - est))[:3]
		p = np.polyfit(near, [pts[o] for o in near], 1)
		if p[0] <= 0:   # measured positive on j0 and j1; negative is the wrong null
			die(f"vd-odd slope not positive near {est}: {sorted(pts.items())}")
		est = int(round(-p[1] / p[0]))
		if min(abs(est - o) for o in pts) <= OFF_TOL:
			return est
		pts[est] = offset_point(est)
	die(f"offset did not converge: {sorted(pts.items())}")

# --- main -------------------------------------------------------------------

def main():
	global IP, levels, off_level
	ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	ap.add_argument("-i", dest="ip", default="127.0.0.1")
	ap.add_argument("--joint", type=int, required=True, choices=sorted(START_BCT))
	a = ap.parse_args()
	IP = a.ip
	sess = ROOT / "traces" / f"{datetime.now():%Y-%m-%d-%H%M}-j{a.joint}-menc"
	sess.mkdir(parents=True)
	os.chdir(sess)
	log(f"# j{a.joint} MA600 calibration — {datetime.now():%Y-%m-%d %H:%M}\n")
	log(f"Drive {IP}; holds at {LEVEL_MULT} x breakaway, {SETTLE_S} s settle, "
	    f"{CAPTURE_MS / 1000:g} s at stride {STRIDE}.\n")

	flash("MECH")
	bct0, corr0 = read_trim()
	off0 = cfg("READ", "MENC_OFFSET")
	json.dump({"bct": bct0, "corr": corr0, "menc_offset": off0}, open("start.json", "w"))
	log(f"Board ID {board_id}.")
	log(f"Start (chip/booted): BCT {bct0}, CORR {'zero' if not any(corr0) else corr0}, MENC_OFFSET {off0}\n")

	# 0. breakaway -> hold levels
	log(f"## Breakaway (0 to ±{BKW_RAMP_A} A over {BKW_RAMP_MS} ms, |mvel_filt| > {BKW_VEL} rad/s)\n")
	log("| dir | iq [A] |"); log("|---|---|")
	ib = breakaway()
	levels = [round(k * ib, 2) for k in LEVEL_MULT]
	off_level = levels[-1]
	log(f"\nBreakaway {ib:.3f} A -> holds ±{levels} A, offset holds ±{off_level} A.\n")

	# 1. BCT
	b0, zeros = START_BCT[a.joint], [0] * 32
	write_trim(b0, zeros); fa = fitset(f"b{b0}")
	write_trim(b0 + BCT_STEP, zeros); fb = fitset(f"b{b0 + BCT_STEP}")
	bn = int(round(mc.bct(NS(a=fa, b=fb, png="bct-slope.png"))))
	if not 0 <= bn <= 255 or abs(bn - b0) > 25:
		die(f"BCT null {bn} is implausible (start {b0})")
	write_trim(bn, zeros)
	fn = {b0: fa, b0 + BCT_STEP: fb}.get(bn) or fitset(f"b{bn}")

	# 2. CORR
	c1 = json.load(open(mc.corr(NS(fit=fn, gain=None, kmin=1, kmax=6))))["corr"]
	write_trim(bn, c1); f1 = fitset("c1")
	mc.gain(NS(before=fn, after=f1, out="gain.json"))
	c2 = json.load(open(mc.corr(NS(fit=f1, gain="gain.json", kmin=1, kmax=6))))["corr"]
	write_trim(bn, c2); f2 = fitset("c2")
	mc.compare(NS(label="corr-compare", fits=[fa, fn, f1, f2]))
	cands = [(summary(f)[0], f, c) for f, c in ((fn, zeros), (f1, c1), (f2, c2))]
	_, fbest, cbest = min(cands, key=lambda x: x[0])
	if fbest != f2:
		write_trim(bn, cbest)
	log(f"## BCT / CORR\n\nBCT null {bn} (slope from {b0}, {b0 + BCT_STEP}). Kept CORR from `{fbest}`.\n")
	log_fits([fa, fb, fn, f1, f2] if fn not in (fa, fb) else [fa, fb, f1, f2])
	hiz()
	cfg("SAVE", "MA600A_REG_BCT", bn)                              # NVM block 0
	cfg("SAVE", "MA600A_REG_CORR", (31 << 8) | (cbest[31] & 0xFF))  # stores all of block 1
	if read_trim() != (bn, cbest):
		die(f"trim readback mismatch after SAVE (drive left in HIZ): {read_trim()}")
	power_on()
	log("\nSaved BCT + CORR to MA600 NVM (checked by the reflash readback below).\n")

	# 3. MENC_OFFSET
	flash("ILOOP")
	if read_trim() != (bn, cbest):
		die(f"trim lost across reflash: {read_trim()}")
	o0 = cfg("READ", "MENC_OFFSET")
	log(f"\n## MENC_OFFSET (vd-null, ±{off_level} A)\n")
	off = find_offset(o0)
	log(f"\nNull {off} (booted {o0}).\n")

	# 4. verify on MECH
	flash("MECH")
	if read_trim() != (bn, cbest):
		die(f"trim lost across reflash: {read_trim()}")
	cfg("WRITE", "MENC_OFFSET", off)
	ff = fitset("final")
	mc.compare(NS(label="final-compare", fits=[fa, ff]))
	log("## Verify (MECH, final offset)\n")
	log_fits([fa, ff])
	log(f"\nResult: BCT {bn}, MENC_OFFSET {off}, CORR {cbest}\n")

	# 5. save
	if input("\nHIZ and SAVE MENC_OFFSET to board nvdata? [y/N] ").strip().lower() != "y":
		log("MENC_OFFSET not saved: live only until reset.")
	else:
		hiz()
		cfg("SAVE", "MENC_OFFSET", off)
		if cfg("READ", "MENC_OFFSET") != off:
			die("MENC_OFFSET readback mismatch after SAVE (drive left in HIZ)")
		power_on()
		log("Saved MENC_OFFSET in board nvdata.")
	Path("report.md").write_text("\n".join(report) + "\n")
	print(f"\nwrote {sess / 'report.md'}")

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:   # holds() has already zeroed the torque
		die("interrupted (Ctrl-C); torque zeroed, trim/offset left live and unsaved")
