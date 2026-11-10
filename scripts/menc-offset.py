#!/usr/bin/env python3
"""menc-offset.py -- MENC_OFFSET (vd-null) and bemf_ff fits from foc_trace holds.

Needs TRACE=ILOOP captures (vd, vq, iq_fbk, id_fbk, mvel raw counts), from
constant-torque holds in both directions.

  menc-offset.py offset OUT.png PREFIX_OFFSET... (captures <prefix><offset>_{f,r}*.txf)
      vd(+)/|mvel+| - vd(-)/|mvel-| is linear in the offset error (inductive
      and lag terms are even in direction and cancel); fit its zero crossing.
  menc-offset.py bemf OUT.png CAP.txf...
      vq = R*iq + k*mvel  ->  k = bemf_ff (v-norm per raw mvel count).
"""
import glob, json, re, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def means(d):
	m = json.load(open(d + "/metadata.json")); tr = {t["name"]: t for t in m["traces"]}
	raw = lambda n: np.fromfile(d + "/" + tr[n]["file"], {"f32": "<f4", "i16": "<i2", "i32": "<i4"}[tr[n]["dtype"]]).astype(float)
	return {n: raw(n).mean() for n in ("vd", "vq", "iq_fbk", "id_fbk", "mvel")} | {"vd_std": raw("vd").std()}

def offset(png, prefixes):
	rows = []
	for p in prefixes:
		O = int(re.search(r"(\d+)$", p).group(1))
		f = [means(d) for d in sorted(glob.glob(p + "_f*.txf"))]
		r = [means(d) for d in sorted(glob.glob(p + "_r*.txf"))]
		mf = {k: np.mean([x[k] for x in f]) for k in f[0]}; mr = {k: np.mean([x[k] for x in r]) for k in r[0]}
		s = mf["vd"] / abs(mf["mvel"]) - mr["vd"] / abs(mr["mvel"])
		e = mf["vd"] / abs(mf["mvel"]) + mr["vd"] / abs(mr["mvel"])
		rows.append((O, s, e, mf, mr))
		print(f"offset {O}: vd+ {mf['vd']:+.5f} vd- {mr['vd']:+.5f}  mvel+ {mf['mvel']:+.0f} mvel- {mr['mvel']:+.0f}"
		      f"  (|+|/|-| {abs(mf['mvel']/mr['mvel']):.3f})  odd {s*1e6:+.3f}e-6  even {e*1e6:+.3f}e-6 /count")
	O = np.array([r[0] for r in rows], float); S = np.array([r[1] for r in rows])
	p = np.polyfit(O, S, 1); null = -p[1] / p[0]
	print(f"odd slope {p[0]:.3e}/offset-count; null at {null:.1f} -> {round(null)}")
	fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
	ax[0].plot(O, S * 1e6, "o", ms=8); oo = np.linspace(O.min() - 50, O.max() + 50, 10)
	ax[0].plot(oo, np.polyval(p, oo) * 1e6, "k--", lw=1); ax[0].axhline(0, color="k", lw=0.5)
	ax[0].axvline(null, color="C2", label=f"null {null:.0f}"); ax[0].axvline(26190, color="C3", ls=":", label="old 26190")
	ax[0].set_xlabel("MENC_OFFSET"); ax[0].set_ylabel("vd+/|w+| - vd-/|w-|  [1e-6 v-norm/count]")
	ax[0].set_title("offset error (direction-odd vd)"); ax[0].legend(); ax[0].grid(alpha=0.3)
	ax[1].plot(O, [abs(r[3]["mvel"]) for r in rows], "o-", label="|mvel| fwd")
	ax[1].plot(O, [abs(r[4]["mvel"]) for r in rows], "s-", label="|mvel| rev")
	ax[1].axvline(null, color="C2"); ax[1].set_xlabel("MENC_OFFSET"); ax[1].set_ylabel("raw mvel counts")
	ax[1].set_title("speed at +/-1.2 A (symmetric at the null)"); ax[1].legend(); ax[1].grid(alpha=0.3)
	fig.tight_layout(); fig.savefig(png, dpi=100); print("wrote", png)

def bemf(png, caps):
	M = [means(d) for d in caps]
	iq = np.array([m["iq_fbk"] for m in M]); w = np.array([m["mvel"] for m in M]); vq = np.array([m["vq"] for m in M])
	A = np.column_stack([iq, w]); (R, k), *_ = np.linalg.lstsq(A, vq, rcond=None)
	res = vq - A @ [R, k]
	for d, m, rr in zip(caps, M, res):
		print(f"  {d.split('/')[-1]:24s} iq {m['iq_fbk']:+.3f} mvel {m['mvel']:+7.0f} vq {m['vq']:+.4f} resid {rr:+.5f}")
	for sgn, nm in ((1, "fwd"), (-1, "rev")):
		s = np.sign(w) == sgn; (Rs, ks), *_ = np.linalg.lstsq(A[s], vq[s], rcond=None)
		print(f"  {nm} only: R {Rs:.4f}  bemf {ks:.4e}")
	print(f"fit: R {R:.4f} v-norm/A  bemf_ff {k:.4e} v-norm/count  resid rms {res.std():.5f}")
	fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
	ax[0].plot(w, vq - R * iq, "o"); ww = np.linspace(w.min(), w.max(), 10)
	ax[0].plot(ww, k * ww, "k--", label=f"bemf_ff {k:.4e}"); ax[0].plot(ww, 1.53e-4 * ww, "C3:", label="old 1.53e-4")
	ax[0].set_xlabel("mvel [raw counts]"); ax[0].set_ylabel("vq - R*iq [v-norm]"); ax[0].legend(); ax[0].grid(alpha=0.3)
	ax[0].set_title("back-EMF")
	ax[1].plot(w, res * 1e3, "o"); ax[1].axhline(0, color="k", lw=0.5)
	ax[1].set_xlabel("mvel [raw counts]"); ax[1].set_ylabel("fit residual [1e-3 v-norm]"); ax[1].grid(alpha=0.3)
	ax[1].set_title(f"residual (R = {R:.4f} v-norm/A)")
	fig.tight_layout(); fig.savefig(png, dpi=100); print("wrote", png)

if __name__ == "__main__":
	if sys.argv[1] == "offset": offset(sys.argv[2], sys.argv[3:])
	else: bemf(sys.argv[2], sys.argv[3:])
