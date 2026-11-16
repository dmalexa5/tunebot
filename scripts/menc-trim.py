#!/usr/bin/env python3
"""menc-trim.py -- read/write the MA600A trim (BCT, CORR0..31) over Jx_CFG.

  menc-trim.py [-i IP] show                       -> {"bct": N, "corr": [32]}
  menc-trim.py [-i IP] write [--bct N] [--corr FILE.json | --corr-zero]

Write puts the drive in HIZ first, then Jx_CFG WRITE (chip shadow registers
only). It never SAVEs: nothing reaches the MA600A NVM. FILE.json holds
{"corr": [32 signed ints, LSB 360/4096 deg]} as written by menc-cal.py corr.
"""
import argparse, json, subprocess, sys
from pathlib import Path

RTT = Path(__file__).resolve().parents[2] / "module-fwpp/tools/rttcmd/rtttask"

def task(ip, req):
	r = json.loads(subprocess.check_output([str(RTT), "-i", ip, json.dumps(req)]))
	if r.get("action") == "ERR":
		sys.exit(f"{req} -> {r}")
	return r

def show(ip):
	bct = task(ip, {"command": "Jx_CFG", "action": "READ", "addr": "MA600A_REG_BCT"})["data"]["val"]
	corr = []
	for i in range(32):
		v = task(ip, {"command": "Jx_CFG", "action": "READ", "addr": "MA600A_REG_CORR", "val": i << 8})["data"]["val"] & 0xFF
		corr.append(v - 256 if v > 127 else v)
	return {"bct": bct, "corr": corr}

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("-i", dest="ip", default="127.0.0.1")
	sp = ap.add_subparsers(dest="cmd", required=True)
	sp.add_parser("show")
	p = sp.add_parser("write")
	p.add_argument("--bct", type=int)
	p.add_argument("--corr")
	p.add_argument("--corr-zero", action="store_true")
	a = ap.parse_args()
	if a.cmd == "write":
		st = task(a.ip, {"command": "Jx_STATUS", "action": "WRITE", "ctrl": ["SET_HIZ"], "mode": "FOC"})
		if st["data"]["outp"] != "HIZ":
			sys.exit(f"drive not in HIZ: {st}")
		if a.bct is not None:
			if not 0 <= a.bct <= 255: sys.exit("bct out of range")
			task(a.ip, {"command": "Jx_CFG", "action": "WRITE", "addr": "MA600A_REG_BCT", "val": a.bct})
		if a.corr or a.corr_zero:
			new = [0] * 32 if a.corr_zero else json.load(open(a.corr))["corr"]
			if len(new) != 32 or any(not -128 <= v <= 127 for v in new):
				sys.exit("corr must be 32 values in -128..127")
			for i, v in enumerate(new):
				task(a.ip, {"command": "Jx_CFG", "action": "WRITE", "addr": "MA600A_REG_CORR", "val": (i << 8) | (v & 0xFF)})
	print(json.dumps(show(a.ip)))

if __name__ == "__main__":
	main()
