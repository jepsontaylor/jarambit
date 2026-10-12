#!/usr/bin/env python3
"""Grid-convergence index (Roache / ASME V&V20, PR-0.30.3) for three systematically refined meshes.
gci(f1, f2, f3, r) with f1 = finest: observed order p = ln((f3 - f2) / (f2 - f1)) / ln r, Richardson f_ext, and
GCI_fine = Fs |(f1 - f2) / f1| / (r^p - 1), Fs = 1.25. Non-monotone (oscillatory) triples are reported, not fitted."""
import math


def gci(f1, f2, f3, r, fs=1.25):
    e21, e32 = f2 - f1, f3 - f2
    if e21 == 0: return dict(p=float('inf'), f_ext=f1, gci_fine=0.0, monotone=True)
    if e32 == 0 or e32 / e21 <= 0:
        return dict(p=None, f_ext=None, gci_fine=fs * abs(e21 / f1) * 3.0, monotone=False)  # conservative (Fs=3 style) bound
    p = math.log(abs(e32 / e21)) / math.log(r)
    f_ext = f1 + (f1 - f2) / (r ** p - 1)
    return dict(p=p, f_ext=f_ext, gci_fine=fs * abs(e21 / f1) / (r ** p - 1), monotone=True)
