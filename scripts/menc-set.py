#!/usr/bin/env python3
"""menc-set.py -- write MENC_BCT and the CORR0..31 table into board-drive.c.

Usage:
    menc-set.py --bct N [--corr FILE.json | --corr-zero]
    menc-set.py --show

FILE.json holds {"corr": [32 signed ints, LSB 360/4096 deg]} as written by
menc-cal.py. Only the MENC_BCT define and the 32 CORR table lines change.
"""
import argparse, json, re, sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "module-fwpp/board/board-drive.c"
CORR_RE = re.compile(r"(\{ \.addr = MA600A_REG_CORR0 \+ (\d+)u,\s+\.data = )0x([0-9A-Fa-f]{2})u( \},)")

def read():
	txt = SRC.read_text()
	bct = int(re.search(r"#define MENC_BCT (\d+)u", txt).group(1))
	corr = [0] * 32
	for m in CORR_RE.finditer(txt):
		v = int(m.group(3), 16)
		corr[int(m.group(2))] = v - 256 if v > 127 else v
	return txt, bct, corr

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--bct", type=int)
	ap.add_argument("--corr")
	ap.add_argument("--corr-zero", action="store_true")
	ap.add_argument("--show", action="store_true")
	a = ap.parse_args()
	txt, bct, corr = read()
	if a.show or (a.bct is None and not a.corr and not a.corr_zero):
		print(json.dumps({"bct": bct, "corr": corr}))
		return
	if a.bct is not None:
		if not 0 <= a.bct <= 255: sys.exit("bct out of range")
		txt = re.sub(r"#define MENC_BCT \d+u", f"#define MENC_BCT {a.bct}u", txt)
	if a.corr or a.corr_zero:
		new = [0] * 32 if a.corr_zero else json.load(open(a.corr))["corr"]
		if len(new) != 32 or any(not -128 <= v <= 127 for v in new):
			sys.exit("corr must be 32 values in -128..127")
		txt = CORR_RE.sub(lambda m: f"{m.group(1)}0x{new[int(m.group(2))] & 0xFF:02X}u{m.group(4)}", txt)
	SRC.write_text(txt)
	_, bct, corr = read()
	print(json.dumps({"bct": bct, "corr": corr}))

if __name__ == "__main__":
	main()
