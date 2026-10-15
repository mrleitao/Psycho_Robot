"""
Compute the summary files the website charts read, from public/data/study1-ratings.csv.

Writes
  src/data/trust-in-medical-ai/trust-by-recommender.json   mean, SD and 95% CI of trust, per recommender
  src/data/trust-in-medical-ai/study1-tests.json           the seven preregistered paired tests plus one exploratory test
  src/data/trust-in-medical-ai/study1-outcomes.json        doctor vs AI means and CIs for trust, quantitative reasoning, intuition

Needs: pandas, scipy, numpy.  Run from the repository root.
"""
import json
import numpy as np
import pandas as pd
from scipy import stats

d = pd.read_csv("public/data/study1-ratings.csv")
LABEL = {"doctor": "Doctor", "nurse": "Nurse", "doctor_remote": "Doctor, remote visit", "therapist": "Therapist",
         "personal_trainer": "Personal trainer", "layperson": "Layperson", "doctor_using_ai": "Doctor using AI",
         "ai_general": "AI, general", "ai_diagnostic": "AI diagnostic tool", "ai_chatbot": "AI chatbot",
         "ai_fitness": "AI fitness coach"}
KIND = {k: ("ai" if k.startswith("ai_") else "hybrid" if k == "doctor_using_ai" else "human") for k in LABEL}

rows = []
for k, label in LABEL.items():
    x = d[f"trust_{k}"].dropna().astype(float)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    rows.append(dict(id=k, label=label, kind=KIND[k], n=int(len(x)), mean=round(x.mean(), 2), sd=round(x.std(ddof=1), 2),
                     lo=round(x.mean() - h, 2), hi=round(x.mean() + h, 2)))
rows.sort(key=lambda r: -r["mean"])
json.dump({"source": "Study 1 of the dissertation (N = 188). Trust in each recommender, rated from 0 (not at all) to 10 (completely). "
           "Means with 95% confidence intervals, computed from the released study data.",
           "scale": [0, 10], "rows": rows},
          open("src/data/trust-in-medical-ai/trust-by-recommender.json", "w"), indent=2)

# Test definitions are shared with the website's live table, so both compute the same thing.
DEFS = json.load(open("src/data/trust-in-medical-ai/study1-test-defs.json"))
for name, cols in DEFS["composites"].items():
    d[name] = d[cols].mean(axis=1, skipna=False)   # missing if any item is missing, as in the original script


def paired(a, b):
    x = d[[a, b]].dropna()
    diff = x[a] - x[b]
    n = len(x)
    t, p = stats.ttest_rel(x[a], x[b])
    h = stats.t.ppf(0.975, n - 1) * diff.std(ddof=1) / np.sqrt(n)
    return dict(n=n, meanA=round(x[a].mean(), 2), meanB=round(x[b].mean(), 2), diff=round(diff.mean(), 2),
                lo=round(diff.mean() - h, 2), hi=round(diff.mean() + h, 2), t=round(float(t), 2), df=n - 1,
                p=float(p), d=round(float(diff.mean() / diff.std(ddof=1)), 2))


def mean_ci(col, rows):
    x = d[col].dropna().astype(float)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return dict(mean=round(x.mean(), 2), lo=round(x.mean() - h, 2), hi=round(x.mean() + h, 2), n=int(len(x)))


out = []
for t in DEFS["tests"]:
    r = paired(t["a"], t["b"])
    out.append({**t, **r, "supported": bool(r["p"] < .05 and r["diff"] > 0)})
json.dump({"note": "Paired t tests on the released data (full sample). d is Cohen's d for paired data: the mean difference over the SD of the differences.",
           "tests": out}, open("src/data/trust-in-medical-ai/study1-tests.json", "w"), indent=2)

oc = []
for o in DEFS["outcomes"]:
    pr = paired(o["doctor"], o["ai"])
    oc.append(dict(id=o["id"], label=o["label"], doctor=mean_ci(o["doctor"], d), ai=mean_ci(o["ai"], d), diff=pr["diff"], d=pr["d"], t=pr["t"], df=pr["df"], p=pr["p"], n=pr["n"]))
json.dump({"source": "Study 1 (N = 188), full sample. Means and 95% confidence intervals of each rating, doctor and AI, on a 0 to 10 scale.",
           "scale": [0, 10], "outcomes": oc}, open("src/data/trust-in-medical-ai/study1-outcomes.json", "w"), indent=2)
for o in out: print(o["id"], o["n"], o["diff"], o["t"], o["df"], f'{o["p"]:.3g}', o["d"], o["supported"])
for o in oc: print(o["label"], o["doctor"], o["ai"], o["d"])
