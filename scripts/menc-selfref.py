#!/usr/bin/env python3
"""menc-selfref.py -- MA600 angle-error harmonics without a reference encoder.

Constant-torque spin with an inertial load: the true rotor angle is smooth in
time, so a zero-phase low-pass of the unwrapped sensed angle (mpos) is the
reference. err = sensed - reference is regressed onto integer harmonics of the
sensed field angle; asynchronous motion (load/gear oscillation) lands at
non-integer orders and is rejected. The 'floor' is the median amplitude of the
same regression at half-integer orders (what an absent harmonic reads as).

Sign convention matches module-fwpp/scripts/menc-fit2fe.py (err = sensed - ref,
coefficients of sin(k*th)/cos(k*th)), so BCT slopes are comparable.

Usage: menc-selfref.py CAPTURE.txf [CAPTURE.txf ...] [--fc HZ] [--png OUT.png]
"""
import argparse, json, math
import numpy as np
from scipy.signal import butter, filtfilt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

KMAX = 12

def load(d):
	meta = json.load(open(d + "/metadata.json"))
	tr = {t["name"]: t for t in meta["traces"]}
	dt = tr["mpos"]["hscale"]
	mpos = np.fromfile(d + "/" + tr["mpos"]["file"], dtype="<i2")
	iq = np.fromfile(d + "/" + tr["iq_fbk"]["file"], dtype="<f4").astype(float)
	th = np.unwrap(mpos.astype(float) * (2 * np.pi / 65536.0))
	return th, iq, dt

def reference(th, dt, fc):
	b, a = butter(4, fc * 2 * dt)
	t = np.arange(len(th)) * dt
	p = np.polyfit(t, th, 1)            # filter the detrended angle, not a ramp
	return np.polyval(p, t) + filtfilt(b, a, th - np.polyval(p, t), padlen=3 * 512)

def harmfit(th, e, orders):
	cols = [np.ones_like(th)]
	for k in orders:
		cols += [np.sin(k * th), np.cos(k * th)]
	c, *_ = np.linalg.lstsq(np.column_stack(cols), e, rcond=None)
	return c[1::2], c[2::2]   # sin, cos per order [rad]

def analyze(d, fc, trim):
	th, iq, dt = load(d)
	e = th - reference(th, dt, fc)
	sl = slice(trim, len(th) - trim)     # drop filtfilt edge transients
	th, e, iq = th[sl], e[sl], iq[sl]
	ks = np.arange(1, KMAX + 1)
	s, c = harmfit(th, e, ks)
	hs, hc = harmfit(th, e, ks - 0.5)    # half-integer orders: the floor
	return dict(name=d.rstrip("/").split("/")[-1], th=th, e=e, iq=iq, dt=dt,
	            sin=np.degrees(s), cos=np.degrees(c),
	            amp=np.degrees(np.hypot(s, c)),
	            floor=np.degrees(np.median(np.hypot(hs, hc))),
	            fe=(th[-1] - th[0]) / (2 * np.pi) / (len(th) * dt))

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("caps", nargs="+")
	ap.add_argument("--fc", type=float, default=0.0, help="reference cutoff Hz (default fe/2)")
	ap.add_argument("--png", default=None)
	a = ap.parse_args()

	res = []
	for d in a.caps:
		th, _, dt = load(d)
		fe = (th[-1] - th[0]) / (2 * np.pi) / (len(th) * dt)
		fc = a.fc or fe / 2
		trim = int(2.0 / (fc * dt))      # ~2 reference time constants
		r = analyze(d, fc, trim); r["fc"] = fc; res.append(r)
		print(f"{r['name']}: fe={r['fe']:.2f} Hz  fc={fc:.1f} Hz  "
		      f"cycles={(r['th'][-1]-r['th'][0])/2/np.pi:.0f}  floor={r['floor']:.4f} deg")
		print("   k  " + " ".join(f"{k:>6d}" for k in range(1, KMAX + 1)))
		print("  amp " + " ".join(f"{x:6.3f}" for x in r["amp"]))
		print("  sin " + " ".join(f"{x:+6.3f}" for x in r["sin"]))
		print("  cos " + " ".join(f"{x:+6.3f}" for x in r["cos"]))
		print(f"  2fe sin={r['sin'][1]:+.4f}  cos={r['cos'][1]:+.4f} deg (BCT trims sin)")

	# robustness: 2fe vs reference cutoff (first capture)
	th0, _, dt0 = load(a.caps[0]); fe0 = res[0]["fe"]
	fcs = np.linspace(0.15, 0.75, 13) * fe0
	sw = [analyze(a.caps[0], f, int(2.0 / (f * dt0))) for f in fcs]

	fig, ax = plt.subplots(2, 2, figsize=(13, 8.5))
	# 1: speed + iq vs time
	r = res[0]; t = np.arange(len(r["th"])) * r["dt"]
	v = np.gradient(r["th"], r["dt"]) / (2 * np.pi)
	b, aa = butter(2, 200 * 2 * r["dt"]); v = filtfilt(b, aa, v)
	ax[0, 0].plot(t, v, lw=0.6, label="sensed field speed (200 Hz LP)")
	ax[0, 0].set_ylabel("field cycles/s"); ax[0, 0].set_xlabel("s")
	ax2 = ax[0, 0].twinx(); ax2.plot(t, r["iq"], lw=0.4, color="C1", alpha=0.6)
	ax2.set_ylabel("iq_fbk [A]", color="C1")
	ax[0, 0].set_title(f"{r['name']}: speed {r['fe']:.1f} Hz field, iq {r['iq'].mean():.2f} A")
	ax[0, 0].grid(alpha=0.3)
	# 2: error vs sensed angle
	for i, r in enumerate(res):
		ang = np.degrees(np.mod(r["th"], 2 * np.pi))
		ax[0, 1].plot(ang[::7], np.degrees(r["e"][::7]), ".", ms=1, alpha=0.15, color=f"C{i}")
		bins = np.linspace(0, 360, 65); idx = np.digitize(ang, bins) - 1
		bm = [np.degrees(r["e"][idx == j].mean()) for j in range(64)]
		ax[0, 1].plot((bins[:-1] + bins[1:]) / 2, bm, "-", lw=2, color=f"C{i}", label=r["name"])
	ax[0, 1].set_xlabel("sensed field angle [deg]"); ax[0, 1].set_ylabel("error [deg]")
	ax[0, 1].set_title("angle error vs sensed angle (dots: samples, line: 64-bin mean)")
	ax[0, 1].set_xlim(0, 360); ax[0, 1].grid(alpha=0.3); ax[0, 1].legend(fontsize=8)
	# 3: order spectrum
	w = 0.8 / len(res); ks = np.arange(1, KMAX + 1)
	for i, r in enumerate(res):
		ax[1, 0].bar(ks + (i - (len(res) - 1) / 2) * w, r["amp"], w, label=r["name"])
		ax[1, 0].axhline(r["floor"], ls="--", color=f"C{i}", lw=1)
	ax[1, 0].set_yscale("log"); ax[1, 0].set_xticks(ks)
	ax[1, 0].set_xlabel("harmonic of field angle (k fe)"); ax[1, 0].set_ylabel("amplitude [deg]")
	ax[1, 0].set_title("error harmonics (dashed: half-integer-order floor)")
	ax[1, 0].grid(alpha=0.3, which="both"); ax[1, 0].legend(fontsize=8)
	# 4: robustness of 2fe vs reference cutoff
	ax[1, 1].plot(fcs, [s["sin"][1] for s in sw], "o-", label="2fe sin (BCT)")
	ax[1, 1].plot(fcs, [s["cos"][1] for s in sw], "s-", label="2fe cos")
	ax[1, 1].plot(fcs, [s["amp"][0] for s in sw], "^-", label="1fe amp")
	ax[1, 1].axvline(res[0]["fc"], color="k", ls=":", lw=1)
	ax[1, 1].set_xlabel("reference low-pass cutoff [Hz]"); ax[1, 1].set_ylabel("deg")
	ax[1, 1].set_title("reference sensitivity (flat = estimate is not a reference artifact)")
	ax[1, 1].grid(alpha=0.3); ax[1, 1].legend(fontsize=8)
	fig.tight_layout()
	out = a.png or a.caps[0].rstrip("/") + ".png"
	fig.savefig(out, dpi=110); print("wrote", out)

if __name__ == "__main__":
	main()
