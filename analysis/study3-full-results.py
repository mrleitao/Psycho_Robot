"""
Compute every Study 3 table and figure from the released file.

Reads   public/data/study3-ratings.csv
Writes  src/data/trust-in-medical-ai/study3-full.json    tables, tests and models
        src/data/trust-in-medical-ai/study3-points.json  per-person values for the jittered plots

Study 3: 609 adults each read one of three vignettes about an app that tracks their health for a month and then
gives a recommendation. The recommender was a standard AI (called JO76N), a humanlike AI (called Jordan, described
with human verbs) or a doctor (Jordan). The advice was identical. Everyone rated trust and belief, and how warm and
competent the recommender seemed. The preregistration is public/docs/study3-preregistration.pdf.

Differences are reported as the first group minus the second, with the doctor, or the humanlike AI, first, so a positive
number means more trust in the doctor or the humanlike AI. The dissertation reports the opposite sign.
Cohen's d is the mean difference over the pooled SD. The dissertation's d came from the t statistic (2t over the square
root of the degrees of freedom), which matches this when the groups are the same size and runs larger when they are not,
as in the comparison of the doctor with the two AI conditions combined.
Age enters models as the age group number (1 = 18 to 44, 4 = 70 and over), because the public file does not hold age in years.

Needs: pandas, numpy, scipy, statsmodels.  Run from the repository root.
"""
import json
import sys
import warnings

import numpy as np
import pandas as pd
from statsmodels.stats.power import TTestIndPower

sys.path.insert(0, "analysis")
from trust_stats import r2, desc, anova1, tukey, welch, ols, series, DEMO, sample_table  # noqa: E402

warnings.filterwarnings("ignore")
OUT = "src/data/trust-in-medical-ai/"
d = pd.read_csv("public/data/study3-ratings.csv")
COND = ["Humanlike AI", "Standard AI", "Doctor"]
KEY = {"Humanlike AI": "humanlike", "Standard AI": "standard", "Doctor": "doctor"}
d["std"] = (d.condition == "Standard AI").astype(int)
d["doc"] = (d.condition == "Doctor").astype(int)
d["man"] = (d.gender == "Man").astype(float).where(d.gender.notna())
d["age"] = d.age_group.map({"18-44": 1, "45-59": 2, "60-69": 3, "70+": 4})
G = {c: d[d.condition == c] for c in COND}
AI = pd.concat([G["Humanlike AI"], G["Standard AI"]])
OUTCOMES = [("trust", "Trust", "-3 to 3"), ("belief", "Belief", "-3 to 3"), ("warmth", "Warmth", "0 to 4"), ("competence", "Competence", "0 to 4"), ("humanlike", "Humanlike", "0 to 4")]

full = {}
full["sample"] = sample_table(d, DEMO)
full["design"] = dict(n=len(d), groups=[dict(condition=c, n=len(G[c])) for c in COND])

# ---------------------------------------------------------------- descriptives
full["descriptives"] = [dict(id=k, label=lab, scale=sc, cells={KEY[c]: desc(G[c][k]) for c in COND}, ai=desc(AI[k]) if k != "humanlike" else None) for k, lab, sc in OUTCOMES]
for row in full["descriptives"]:
    if row["id"] == "humanlike":
        row["cells"].pop("doctor")
        row["cells"] = {k: v for k, v in row["cells"].items() if v["n"] > 0}

# ---------------------------------------------------------------- omnibus tests and planned or exploratory comparisons
PAIRS = [  # id, label, first, second, role
    ("ai-doc", "Doctor versus the two AI conditions combined", "Doctor", "AI", "planned"),
    ("hum-std", "Humanlike AI versus standard AI", "Humanlike AI", "Standard AI", "planned"),
    ("doc-std", "Doctor versus standard AI", "Doctor", "Standard AI", "additional"),
    ("doc-hum", "Doctor versus humanlike AI", "Doctor", "Humanlike AI", "additional"),
]


def grp(name):
    return AI if name == "AI" else G[name]


anovas, tests = {}, {}
for k in ("trust", "belief", "warmth", "competence"):
    groups = {c: G[c][k] for c in COND}
    a = anova1(groups)
    tk = tukey(groups)
    a["tukey"] = {f"{x}|{y}": tk[(x, y)]["p"] for x, y in [("Doctor", "Standard AI"), ("Doctor", "Humanlike AI"), ("Humanlike AI", "Standard AI")]}
    anovas[k] = a
    rows = []
    for pid, lab, f, s, role in PAIRS:
        r = welch(grp(f)[k], grp(s)[k], lab, id=pid, role=role, first=f, second=s)
        if (f, s) in [("Doctor", "Standard AI"), ("Doctor", "Humanlike AI"), ("Humanlike AI", "Standard AI")]:
            r["pTukey"] = tk[(f, s)]["p"]
        rows.append(r)
    tests[k] = rows
full["anova"] = anovas
full["tests"] = tests
# does the humanlike description make the AI seem more humanlike? (asked in the AI conditions only)
full["manipulationCheck"] = welch(G["Humanlike AI"]["humanlike"], G["Standard AI"]["humanlike"], "How humanlike the AI seemed: humanlike AI versus standard AI", id="check", role="check",
                                  first="Humanlike AI", second="Standard AI")

# ---------------------------------------------------------------- what the study could detect
pw = TTestIndPower()
full["sensitivity"] = [dict(id=pid, label=lab, nA=int(len(grp(f))), nB=int(len(grp(s))),
                            minD=r2(float(np.ravel(pw.solve_power(nobs1=len(grp(f)), ratio=len(grp(s)) / len(grp(f)), alpha=0.05, power=0.8))[0]), 2)) for pid, lab, f, s, role in PAIRS]

# ---------------------------------------------------------------- regressions (humanlike AI is the reference)
SPEC = [[("std", "Standard AI (versus humanlike AI)"), ("doc", "Doctor (versus humanlike AI)")],
        [("std", "Standard AI (versus humanlike AI)"), ("doc", "Doctor (versus humanlike AI)"), ("man", "Man (versus woman)"), ("age", "Age group (1 to 4)")],
        [("std", "Standard AI (versus humanlike AI)"), ("doc", "Doctor (versus humanlike AI)"), ("man", "Man (versus woman)"), ("age", "Age group (1 to 4)"), ("warmth", "Warmth"), ("competence", "Competence")]]
LAB = ["Condition only", "Add gender and age", "Add warmth and competence"]
full["models"] = {k: [ols(d, k, SPEC[i], LAB[i]) for i in range(3)] for k in ("trust", "belief")}

# ---------------------------------------------------------------- correlations
cols = ["trust", "belief", "warmth", "competence"]
full["correlations"] = dict(labels=["Trust", "Belief", "Warmth", "Competence"], r=[[r2(d[a].corr(d[b]), 3) for b in cols] for a in cols], n=int(d[cols].dropna().shape[0]))
full["trustBelieve"] = dict(r=r2(d.trust.corr(d.belief), 3), n=int(d[["trust", "belief"]].dropna().shape[0]))

json.dump(full, open(OUT + "study3-full.json", "w"))

# ---------------------------------------------------------------- figures
points = {}
grid7 = np.linspace(-3, 3, 61)
grid5 = np.linspace(0, 4, 41)
points["gridTrust"] = [float(v) for v in grid7]
points["gridScale4"] = [float(v) for v in grid5]
kind = {"Humanlike AI": "hybrid", "Standard AI": "ai", "Doctor": "human"}
for k, lab, sc in OUTCOMES[:4]:
    grid = grid7 if k in ("trust", "belief") else grid5
    points[k] = [series(c, KEY[c], G[c][k], grid, dict(kind=kind[c])) for c in ["Doctor", "Humanlike AI", "Standard AI"]]
points["humanlike"] = [series(c, KEY[c], G[c]["humanlike"], grid5, dict(kind=kind[c])) for c in ["Humanlike AI", "Standard AI"]]
json.dump(points, open(OUT + "study3-points.json", "w"))
print("wrote study3-full.json and study3-points.json")
