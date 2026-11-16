#!/usr/bin/env python3
"""menc-cal.py -- MA600 encoder calibration from constant-torque holds, no reference.

Per capture: reference = zero-phase low-pass (fc = fe/2) of the unwrapped sensed
angle; err = sensed - reference; complex harmonics c_k = sin_k + j*cos_k of err
vs sensed angle, k = 1..12 [deg].
Per direction, per k: c_k(fe) = E_k + M_k/fe^2 (least squares over all captures
of that direction) -- E_k is the speed-independent (encoder) part, M_k the real
rotor motion from torque ripple. Encoder estimate = mean of E_k over directions;
the half-difference is reported as its direction uncertainty.

  menc-cal.py fit [-i IP] LABEL CAP.txf...    -> LABEL.fit.json, LABEL.fit.png
      (BCT/CORR in effect are read from the bench via menc-trim.py)
  menc-cal.py bct A.fit.json B.fit.json       -> BCT slope + null (A,B carry "bct")
  menc-cal.py corr FIT.json [--gain G.json] [--kmin 1] [--kmax 6] -> FIT-corr.json
  menc-cal.py gain BEFORE.fit.json AFTER.fit.json     -> measured CORR response
  menc-cal.py compare LABEL A.fit.json B.fit.json...  -> LABEL.png before/after

Sign convention = module-fwpp/scripts/menc-fit2fe.py. CORR LSB = 360/4096 deg.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
import numpy as np
from scipy.signal import butter, filtfilt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

KMAX = 12
LSB = 360.0 / 4096.0
TRIM = Path(__file__).with_name("menc-trim.py")

def load(d):
	meta = json.load(open(d + "/metadata.json"))
	tr = {t["name"]: t for t in meta["traces"]}
	dt = tr["mpos"]["hscale"]
	mpos = np.fromfile(d + "/" + tr["mpos"]["file"], dtype="<i2")
	th = np.unwrap(mpos.astype(float) * (2 * np.pi / 65536.0))
	return th, dt

def harm(th, e, orders):
	cols = [np.ones_like(th)]
	for k in orders:
		cols += [np.sin(k * th), np.cos(k * th)]
	A = np.column_stack(cols)
	c, *_ = np.linalg.lstsq(A, e, rcond=None)
	return c[1::2] + 1j * c[2::2], e - A @ c

def capture(d):
	th, dt = load(d)
	fe = (th[-1] - th[0]) / (2 * np.pi) / ((len(th) - 1) * dt)
	fc = abs(fe) / 2
	t = np.arange(len(th)) * dt
	p = np.polyfit(t, th, 1)
	b, a = butter(4, fc * 2 * dt)
	e = th - (np.polyval(p, t) + filtfilt(b, a, th - np.polyval(p, t), padlen=1536))
	n = int(2.0 / (fc * dt)); th, e = th[n:-n], e[n:-n]
	ks = np.arange(1, KMAX + 1)
	c, r = harm(th, e, ks)
	hc, _ = harm(th, e, ks - 0.5)
	ang = np.mod(th, 2 * np.pi)
	idx = (ang / (2 * np.pi) * 64).astype(int)
	curve = [float(np.degrees(e[idx == j].mean())) for j in range(64)]
	return dict(file=d, fe=float(fe), c=c * 180 / np.pi, floor=float(np.degrees(np.median(np.abs(hc)))),
	            resid_rms=float(np.degrees(r.std())), curve=curve)

def cj(z): return [[float(x.real), float(x.imag)] for x in z]
def jc(l): return np.array([a + 1j * b for a, b in l])

def fit(a):
	caps = [capture(d) for d in a.caps]
	st = json.loads(subprocess.check_output([sys.executable, str(TRIM), "-i", a.ip, "show"]))
	out = dict(label=a.label, bct=st["bct"], corr=st["corr"], caps=[], dirs={})
	for dname, sel in (("f", lambda c: c["fe"] > 0), ("r", lambda c: c["fe"] < 0)):
		cs = [c for c in caps if sel(c)]
		if len(cs) < 2: continue
		X = np.column_stack([np.ones(len(cs)), [1 / c["fe"] ** 2 for c in cs]])
		C = np.array([c["c"] for c in cs])
		sol = np.linalg.lstsq(X, C, rcond=None)[0]      # complex, per k
		res = C - X @ sol
		out["dirs"][dname] = dict(E=cj(sol[0]), M=cj(sol[1]),
		                          scatter=[float(x) for x in np.sqrt((np.abs(res) ** 2).mean(0))])
	for c in caps:
		out["caps"].append(dict(file=c["file"], fe=c["fe"], c=cj(c["c"]), floor=c["floor"],
		                        resid_rms=c["resid_rms"], curve=c["curve"]))
	Es = [jc(v["E"]) for v in out["dirs"].values()]
	E = np.mean(Es, 0)
	out["E"] = cj(E)
	out["E_dirdiff"] = [float(x) for x in (np.abs(Es[0] - Es[1]) / 2 if len(Es) == 2 else np.zeros(KMAX))]
	json.dump(out, open(a.label + ".fit.json", "w"), indent=1)

	print(f"{a.label}: BCT={out['bct']}  CORR={'zero' if not any(out['corr']) else 'set'}")
	print(f"  {'capture':28s} {'fe Hz':>8s} " + " ".join(f"{k:>6d}" for k in range(1, 7)) + "   floor")
	for c in caps:
		print(f"  {Path(c['file']).name:28s} {c['fe']:8.1f} " + " ".join(f"{abs(x):6.3f}" for x in c["c"][:6]) + f"  {c['floor']:.4f}")
	for dn, v in out["dirs"].items():
		print(f"  E[{dn}] amp      " + " " * 9 + " ".join(f"{abs(x):6.3f}" for x in jc(v['E'])[:6]))
		print(f"  M[{dn}]/fe^2@100Hz" + " " * 7 + " ".join(f"{abs(x)/1e4:6.3f}" for x in jc(v['M'])[:6]))
	print(f"  ENCODER amp     " + " " * 9 + " ".join(f"{abs(x):6.3f}" for x in E[:6]))
	print(f"  ENCODER sin     " + " " * 9 + " ".join(f"{x.real:+6.3f}" for x in E[:6]))
	print(f"  ENCODER cos     " + " " * 9 + " ".join(f"{x.imag:+6.3f}" for x in E[:6]))
	print(f"  dir +/-         " + " " * 9 + " ".join(f"{x:6.3f}" for x in out['E_dirdiff'][:6]))
	plot_fit(out, a.label + ".fit.png")

def synth(E, th, kmax=KMAX):
	return sum(E[k - 1].real * np.sin(k * th) + E[k - 1].imag * np.cos(k * th) for k in range(1, kmax + 1))

def plot_fit(out, png):
	E = jc(out["E"])
	fig = plt.figure(figsize=(15, 10))
	gs = fig.add_gridspec(3, 4)
	# speed regressions k=1..6 (sin and cos)
	for k in range(1, 7):
		ax = fig.add_subplot(gs[(k - 1) // 3, (k - 1) % 3])
		for dn, mk in (("f", "o"), ("r", "s")):
			if dn not in out["dirs"]: continue
			cs = [c for c in out["caps"] if (c["fe"] > 0) == (dn == "f")]
			x = np.array([1 / c["fe"] ** 2 for c in cs]) * 1e4
			s = np.array([jc(c["c"])[k - 1] for c in cs])
			Ed, Md = jc(out["dirs"][dn]["E"])[k - 1], jc(out["dirs"][dn]["M"])[k - 1]
			xx = np.linspace(0, x.max() * 1.05, 20)
			ax.plot(x, s.real, mk, color="C0", mfc="none" if dn == "r" else "C0", label=f"sin {dn}")
			ax.plot(x, s.imag, mk, color="C3", mfc="none" if dn == "r" else "C3", label=f"cos {dn}")
			ax.plot(xx, (Ed + Md * xx / 1e4).real, "-" if dn == "f" else "--", color="C0", lw=1)
			ax.plot(xx, (Ed + Md * xx / 1e4).imag, "-" if dn == "f" else "--", color="C3", lw=1)
		ax.plot([0], [E[k - 1].real], "*", color="C0", ms=13, mec="k")
		ax.plot([0], [E[k - 1].imag], "*", color="C3", ms=13, mec="k")
		ax.axhline(0, color="k", lw=0.5)
		ax.set_title(f"{k}fe: encoder sin {E[k-1].real:+.3f} cos {E[k-1].imag:+.3f} deg", fontsize=9)
		ax.set_xlabel("1e4 / fe^2  (0 = infinite speed)", fontsize=8); ax.grid(alpha=0.3)
		if k == 1: ax.legend(fontsize=7, ncol=2)
	# error vs angle: per capture binned curves + encoder synth
	ax = fig.add_subplot(gs[2, 0:2])
	x = (np.arange(64) + 0.5) * 360 / 64
	for c in out["caps"]:
		ax.plot(x, c["curve"], lw=0.6, alpha=0.45, color="C0" if c["fe"] > 0 else "C1")
	th = np.radians(np.linspace(0, 360, 361))
	ax.plot(np.degrees(th), synth(E, th), "k", lw=2, label="encoder estimate (1-12fe)")
	ax.plot([], [], color="C0", label="captures fwd"); ax.plot([], [], color="C1", label="captures rev")
	ax.set_xlim(0, 360); ax.set_xlabel("sensed field angle [deg]"); ax.set_ylabel("error [deg]")
	ax.grid(alpha=0.3); ax.legend(fontsize=8)
	ax.set_title(f"{out['label']}  BCT={out['bct']}  error vs angle")
	# harmonic bars
	ax = fig.add_subplot(gs[2, 2:4])
	ks = np.arange(1, KMAX + 1)
	ax.bar(ks, np.abs(E), 0.6, label="encoder |E_k|", yerr=out["E_dirdiff"], capsize=2)
	ax.axhline(np.median([c["floor"] for c in out["caps"]]), ls="--", color="k", lw=1, label="floor")
	ax.axhline(LSB / 2, ls=":", color="C3", lw=1, label="CORR LSB/2")
	ax.set_yscale("log"); ax.set_xticks(ks); ax.set_xlabel("k fe"); ax.set_ylabel("deg")
	ax.grid(alpha=0.3, which="both"); ax.legend(fontsize=8)
	ax.set_title("encoder harmonics (err bar: direction half-difference)")
	fig.tight_layout(); fig.savefig(png, dpi=100); print("wrote", png)

def bct(a):
	A, B = json.load(open(a.a)), json.load(open(a.b))
	EA, EB = jc(A["E"])[1], jc(B["E"])[1]
	s = (EB - EA) / (B["bct"] - A["bct"])            # complex 2fe per LSB
	u = s / abs(s)                                   # the direction BCT moves 2fe
	# BCT that minimizes |2fe| (project onto the BCT direction)
	n = A["bct"] - (EA * np.conj(u)).real / abs(s)
	rem = EA + s * (n - A["bct"])
	print(f"2fe @BCT{A['bct']}: sin {EA.real:+.3f} cos {EA.imag:+.3f}   @BCT{B['bct']}: sin {EB.real:+.3f} cos {EB.imag:+.3f}")
	print(f"slope per LSB: sin {s.real:+.4f} cos {s.imag:+.4f} deg  (|{abs(s):.4f}| @ {np.degrees(np.angle(s)):+.0f} deg)")
	print(f"null BCT = {n:.2f}  -> round {round(n)}; predicted 2fe there: sin {(EA+s*(round(n)-A['bct'])).real:+.3f} cos {(EA+s*(round(n)-A['bct'])).imag:+.3f} (|{abs(EA+s*(round(n)-A['bct'])):.3f}|), continuous min |{abs(rem):.3f}|")
	if a.png:
		fig, ax = plt.subplots(figsize=(6, 6))
		for F, m in ((A, "o"), (B, "s")):
			e = jc(F["E"])[1]; ax.plot(e.real, e.imag, m, ms=9, label=f"BCT {F['bct']} (encoder est.)")
			for c in F["caps"]:
				z = jc(c["c"])[1]; ax.plot(z.real, z.imag, m, mfc="none", alpha=0.5, color="gray")
		bb = np.linspace(min(A["bct"], n) - 3, max(B["bct"], n) + 3, 50)
		ln = EA + s * (bb - A["bct"]); ax.plot(ln.real, ln.imag, "k--", lw=1, label="BCT line")
		z = EA + s * (round(n) - A["bct"]); ax.plot(z.real, z.imag, "*", ms=15, color="C2", mec="k", label=f"predicted BCT {round(n)}")
		ax.axhline(0, color="k", lw=0.5); ax.axvline(0, color="k", lw=0.5); ax.set_aspect("equal")
		ax.set_xlabel("2fe sin [deg]"); ax.set_ylabel("2fe cos [deg]"); ax.grid(alpha=0.3); ax.legend(fontsize=8)
		ax.set_title("BCT slope (gray: individual captures incl. motion)")
		fig.tight_layout(); fig.savefig(a.png, dpi=100); print("wrote", a.png)
	return n

def corr(a):
	F = json.load(open(a.fit))
	E = jc(F["E"])
	g = np.ones(KMAX, complex)
	if a.gain:
		g = jc(json.load(open(a.gain))["gain"])
	else:   # linear interpolation between 32 points attenuates k by sinc^2(k/32)
		g = np.sinc(np.arange(1, KMAX + 1) / 32) ** 2 + 0j
	th = np.arange(32) * 2 * np.pi / 32
	# command: cancel the encoder harmonics 1..kmax (CORR adds to the output)
	dE = np.zeros(KMAX, complex); dE[a.kmin - 1:a.kmax] = -E[a.kmin - 1:a.kmax] / g[a.kmin - 1:a.kmax]
	base = np.array(F["corr"], float)
	new = base + synth(dE, th) / LSB
	q = np.clip(np.round(new), -128, 127).astype(int)
	out = Path(a.fit).with_name(Path(a.fit).name.replace(".fit.json", "-corr.json"))
	json.dump({"corr": q.tolist(), "from": a.fit, "kmin": a.kmin, "kmax": a.kmax, "cmd_dE": cj(dE)}, open(out, "w"))
	print("CORR", q.tolist()); print("max |corr|", np.abs(q).max(), "LSB; wrote", out)
	return out

def gain(a):
	B, A = json.load(open(a.before)), json.load(open(a.after))
	th = np.arange(32) * 2 * np.pi / 32
	d = (np.array(A["corr"]) - np.array(B["corr"])) * LSB   # commanded table change [deg]
	# commanded harmonic content of the table change (DFT of 32 points)
	ks = np.arange(1, KMAX + 1)
	cmd = np.array([2 / 32 * np.sum(d * np.sin(k * th)) + 2j / 32 * np.sum(d * np.cos(k * th)) for k in ks])
	meas = jc(A["E"]) - jc(B["E"])
	g = meas / np.where(np.abs(cmd) > 1e-9, cmd, np.nan)
	for k in ks:
		print(f"  {k}fe cmd {abs(cmd[k-1]):.3f}  meas {abs(meas[k-1]):.3f}  gain {abs(g[k-1]):.3f} @ {np.degrees(np.angle(g[k-1])):+.0f} deg")
	json.dump({"gain": cj(np.nan_to_num(g, nan=1.0))}, open(a.out, "w")); print("wrote", a.out)

def compare(a):
	Fs = [json.load(open(f)) for f in a.fits]
	fig, ax = plt.subplots(1, 2, figsize=(15, 5))
	th = np.radians(np.linspace(0, 360, 361))
	ks = np.arange(1, KMAX + 1); w = 0.8 / len(Fs)
	for i, F in enumerate(Fs):
		E = jc(F["E"]); rms = np.sqrt(np.mean(synth(E, th) ** 2))
		lab = f"{F['label']} (BCT {F['bct']}, rms {rms:.3f} deg)"
		ax[0].plot(np.degrees(th), synth(E, th), lw=2, label=lab)
		ax[1].bar(ks + (i - (len(Fs) - 1) / 2) * w, np.abs(E), w, label=F["label"])
	ax[1].axhline(np.median([c["floor"] for c in Fs[-1]["caps"]]), ls="--", color="k", lw=1, label="floor")
	ax[1].axhline(LSB / 2, ls=":", color="C3", lw=1, label="CORR LSB/2")
	ax[0].set_xlim(0, 360); ax[0].set_xlabel("sensed field angle [deg]"); ax[0].set_ylabel("encoder error estimate [deg]")
	ax[0].grid(alpha=0.3); ax[0].legend(fontsize=8); ax[0].set_title("encoder error (speed-extrapolated, direction-averaged)")
	ax[1].set_yscale("log"); ax[1].set_xticks(ks); ax[1].set_xlabel("k fe"); ax[1].set_ylabel("|E_k| deg")
	ax[1].grid(alpha=0.3, which="both"); ax[1].legend(fontsize=8); ax[1].set_title("encoder harmonics")
	fig.tight_layout(); fig.savefig(a.label + ".png", dpi=100); print("wrote", a.label + ".png")

def main():
	ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
	p = sp.add_parser("fit"); p.add_argument("-i", dest="ip", default="127.0.0.1"); p.add_argument("label"); p.add_argument("caps", nargs="+"); p.set_defaults(f=fit)
	p = sp.add_parser("bct"); p.add_argument("a"); p.add_argument("b"); p.add_argument("--png"); p.set_defaults(f=bct)
	p = sp.add_parser("corr"); p.add_argument("fit"); p.add_argument("--gain"); p.add_argument("--kmax", type=int, default=6); p.add_argument("--kmin", type=int, default=1); p.set_defaults(f=corr)
	p = sp.add_parser("gain"); p.add_argument("before"); p.add_argument("after"); p.add_argument("out"); p.set_defaults(f=gain)
	p = sp.add_parser("compare"); p.add_argument("label"); p.add_argument("fits", nargs="+"); p.set_defaults(f=compare)
	a = ap.parse_args(); a.f(a)

if __name__ == "__main__":
	main()
