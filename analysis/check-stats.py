"""scipy reference values for analysis/check-stats.mjs. Run: python3 analysis/check-stats.py"""
import json
from scipy import stats
import numpy as np
def power(d, n, a):
    df = n - 1; tc = stats.t.ppf(1 - a / 2, df); nc = d * np.sqrt(n)
    return 1 - stats.nct.cdf(tc, df, nc) + stats.nct.cdf(-tc, df, nc)
for d, n, a in [(0.2, 100, .05), (0.5, 34, .05), (0.8, 15, .05), (0.41, 188, .01), (0.07, 609, .05), (0.19, 185, .05)]:
    print(json.dumps({"d": d, "n": n, "a": a, "power": round(power(d, n, a), 5)}))
nn = lambda d: next(n for n in range(3, 5000) if power(d, n, .05) >= .8)
from scipy.optimize import brentq
mde = lambda n: brentq(lambda d: power(d, n, .05) - .8, 1e-4, 8 / np.sqrt(n))
print(json.dumps({"n_for_d05": nn(.5), "n_for_d02": nn(.2), "mde188": round(mde(188), 4), "mde24": round(mde(24), 4)}))
