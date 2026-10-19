"""
Compute every Study 4 table and figure from the released file.

Reads   public/data/study4-ratings.csv
Writes  src/data/trust-in-medical-ai/study4-full.json    tables, tests and models
        src/data/trust-in-medical-ai/study4-points.json  per-person values for the jittered plots

Study 4 repeated Study 3 with a voice recording added to every condition (a natural voice for the doctor and the
humanlike AI, a chopped and filtered one for the standard AI), and added a within-person part. 559 adults first read one
randomly assigned vignette and rated it (the between-subjects part, columns ending _first). They then rated all
three recommenders in a counterbalanced order (the within-subjects part). The preregistration is
public/docs/study4-preregistration.pdf.

Differences are the first group minus the second, with the doctor, or the humanlike AI, first: a positive number means
more trust in the doctor or the humanlike AI. The dissertation reports the opposite sign.
Cohen's d: pooled SD for two groups; d_z (the mean difference over the SD of the differences) for pairs of ratings.
The omnibus test across the three ratings is a repeated-measures ANOVA on the 493 people who gave all three. The
dissertation reports F(2, 1573) = 1.65 for this test, which cannot be reproduced and does not fit its own paired tests;
the dissertation value is kept next to the corrected one.
Age enters models as the age group number (1 = 18 to 44, 4 = 70 and over).

Needs: pandas, numpy, scipy, statsmodels.  Run from the repository root.
"""
import json
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.power import TTestIndPower

sys.path.insert(0, "analysis")
from trust_stats import r2, desc, anova1, tukey, welch, paired, ols, lmm, series, DEMO, sample_table  # noqa: E402

warnings.filterwarnings("ignore")
OUT = "src/data/trust-in-medical-ai/"
d = pd.read_csv("public/data/study4-ratings.csv")
COND = ["Humanlike AI", "Standard AI", "Doctor"]
KEY = {"Humanlike AI": "humanlike", "Standard AI": "standard", "Doctor": "doctor"}
d["std"] = (d.first_recommender == "Standard AI").astype(int)
d["doc"] = (d.first_recommender == "Doctor").astype(int)
d["man"] = (d.gender == "Man").astype(float).where(d.gender.notna())
d["age"] = d.age_group.map({"18-44": 1, "45-59": 2, "60-69": 3, "70+": 4})
G = {c: d[d.first_recommender == c] for c in COND}
AI = pd.concat([G["Humanlike AI"], G["Standard AI"]])
OUTCOMES = [("trust", "Trust", "-3 to 3"), ("belief", "Belief", "-3 to 3"), ("warmth", "Warmth", "0 to 4"), ("competence", "Competence", "0 to 4")]

full = {}
full["sample"] = sample_table(d, DEMO)
full["design"] = dict(n=len(d), groups=[dict(condition=c, n=len(G[c])) for c in COND],
                      orders=[dict(order=o, n=int((d.order == o).sum())) for o in ["HDN", "HND", "DHN", "NHD", "DNH", "NDH"]])

# ================================================================ between subjects: the first vignette
d["warmth"], d["competence"] = d["warmth_first"], d["competence_first"]
d["trust"], d["belief"] = d["trust_first"], d["belief_first"]
for k, _, _ in OUTCOMES:
    for c in COND:
        pass
full["betweenDescriptives"] = [dict(id=k, label=lab, scale=sc, cells={KEY[c]: desc(G[c][f"{k}_first"]) for c in COND}, ai=desc(AI[f"{k}_first"])) for k, lab, sc in OUTCOMES]
PAIRS = [("ai-doc", "Doctor versus the two AI conditions combined", "Doctor", "AI", "planned"),
         ("hum-std", "Humanlike AI versus standard AI", "Humanlike AI", "Standard AI", "planned"),
         ("doc-std", "Doctor versus standard AI", "Doctor", "Standard AI", "additional"),
         ("doc-hum", "Doctor versus humanlike AI", "Doctor", "Humanlike AI", "additional")]


def grp(name):
    return AI if name == "AI" else G[name]


anovas, tests = {}, {}
for k, _, _ in OUTCOMES:
    groups = {c: G[c][f"{k}_first"] for c in COND}
    a = anova1(groups)
    tk = tukey(groups)
    a["tukey"] = {f"{x}|{y}": tk[(x, y)]["p"] for x, y in [("Doctor", "Standard AI"), ("Doctor", "Humanlike AI"), ("Humanlike AI", "Standard AI")]}
    anovas[k] = a
    rows = []
    for pid, lab, f, s, role in PAIRS:
        r = welch(grp(f)[f"{k}_first"], grp(s)[f"{k}_first"], lab, id=pid, role=role, first=f, second=s)
        if (f, s) in [("Doctor", "Standard AI"), ("Doctor", "Humanlike AI"), ("Humanlike AI", "Standard AI")]:
            r["pTukey"] = tk[(f, s)]["p"]
        rows.append(r)
    tests[k] = rows
full["betweenAnova"] = anovas
full["betweenTests"] = tests
full["manipulationCheck"] = welch(G["Humanlike AI"]["humanlike_first"], G["Standard AI"]["humanlike_first"], "How humanlike the AI seemed: humanlike AI versus standard AI", id="check", role="check", first="Humanlike AI", second="Standard AI")
pw = TTestIndPower()
full["sensitivity"] = [dict(id=pid, label=lab, nA=int(len(grp(f))), nB=int(len(grp(s))),
                            minD=r2(float(np.ravel(pw.solve_power(nobs1=len(grp(f)), ratio=len(grp(s)) / len(grp(f)), alpha=0.05, power=0.8))[0]), 2)) for pid, lab, f, s, role in PAIRS]
SPEC = [[("std", "Standard AI (versus humanlike AI)"), ("doc", "Doctor (versus humanlike AI)")],
        [("std", "Standard AI (versus humanlike AI)"), ("doc", "Doctor (versus humanlike AI)"), ("man", "Man (versus woman)"), ("age", "Age group (1 to 4)")],
        [("std", "Standard AI (versus humanlike AI)"), ("doc", "Doctor (versus humanlike AI)"), ("man", "Man (versus woman)"), ("age", "Age group (1 to 4)"), ("warmth", "Warmth"), ("competence", "Competence")]]
LAB = ["Condition only", "Add gender and age", "Add warmth and competence"]
full["betweenModels"] = {k: [ols(d, k, SPEC[i], LAB[i]) for i in range(3)] for k in ("trust", "belief")}

# ================================================================ within subjects: everyone rated all three
REC = ["humanlike", "standard", "doctor"]
RECLAB = {"humanlike": "Humanlike AI", "standard": "Standard AI", "doctor": "Doctor"}
full["withinDescriptives"] = [dict(id=k, label=lab, scale=sc, cells={r: desc(d[f"{k}_{r}"]) for r in REC}) for k, lab, sc in OUTCOMES]
WP = [("hum-std", "Humanlike AI versus standard AI", "humanlike", "standard"),
      ("doc-std", "Doctor versus standard AI", "doctor", "standard"),
      ("doc-hum", "Doctor versus humanlike AI", "doctor", "humanlike")]


def rm_anova(k):
    c = d[[f"{k}_{r}" for r in REC]].dropna()
    Y = c.values
    n, m = Y.shape
    gm = Y.mean()
    ssa = n * ((Y.mean(0) - gm) ** 2).sum()
    ssb = m * ((Y.mean(1) - gm) ** 2).sum()
    sse = ((Y - gm) ** 2).sum() - ssa - ssb
    dfa, dfe = m - 1, (n - 1) * (m - 1)
    F = (ssa / dfa) / (sse / dfe)
    # Greenhouse-Geisser correction from the covariance of the three ratings
    S = np.cov(Y.T)
    cc = np.eye(m) - np.ones((m, m)) / m
    Sc = cc @ S @ cc
    eps = float(np.trace(Sc) ** 2 / ((m - 1) * np.trace(Sc @ Sc)))
    return dict(n=int(n), F=r2(F), df1=dfa, df2=dfe, p=float(stats.f.sf(F, dfa, dfe)), pes=r2(ssa / (ssa + sse), 3), eps=r2(eps, 3),
                pGG=float(stats.f.sf(F, dfa * eps, dfe * eps)))


full["withinAnova"] = {k: rm_anova(k) for k in ("trust", "belief")}
full["withinAnova"]["trust"]["reported"] = dict(F=1.65, df1=2, df2=1573, p=0.192)
full["withinAnova"]["belief"]["reported"] = dict(F=1.41, df1=2, df2=1575, p=0.245)
within = {}
for k, _, _ in OUTCOMES:
    rows = []
    for pid, lab, a, b in WP:
        r = paired(d[f"{k}_{a}"], d[f"{k}_{b}"], lab, id=pid, first=RECLAB[a], second=RECLAB[b])
        r["pBonferroni"] = min(1.0, r["p"] * 3)
        rows.append(r)
    within[k] = rows
full["withinTests"] = within
# between-subjects and within-subjects effects side by side (trust)
full["effectCompare"] = [dict(measure=k, between={t["id"]: dict(d=t["d"], dLo=t["dLo"], dHi=t["dHi"]) for t in tests[k] if t["id"] != "ai-doc"},
                              within={t["id"]: dict(d=t["d"], dLo=t["dLo"], dHi=t["dHi"]) for t in within[k]}) for k in ("trust", "belief")]
# ================================================================ mixed models on all ratings
rows = []
for r in REC:
    rows.append(pd.DataFrame({"id": d.participant, "rec": r, "trust": d[f"trust_{r}"], "belief": d[f"belief_{r}"], "warmth": d[f"warmth_{r}"],
                              "competence": d[f"competence_{r}"], "man": d["man"], "age": d["age"]}))
L = pd.concat(rows, ignore_index=True)
L["std"] = (L.rec == "standard").astype(int)
L["doc"] = (L.rec == "doctor").astype(int)
NAMES = {"Intercept": "Intercept", "std": "Standard AI (versus humanlike AI)", "doc": "Doctor (versus humanlike AI)", "man": "Man (versus woman)",
         "age": "Age group (1 to 4)", "warmth": "Warmth", "competence": "Competence"}
FORMS = [("{y} ~ std + doc", "Recommender only"), ("{y} ~ std + doc + man + age", "Add gender and age"), ("{y} ~ std + doc + man + age + warmth + competence", "Add warmth and competence")]
full["mixedModels"] = {y: [lmm(f.format(y=y), L, "id", y, lab, NAMES) for f, lab in FORMS] for y in ("trust", "belief")}
for y in full["mixedModels"]:
    for m in full["mixedModels"][y]:
        m["ratingsPerPerson"] = r2(m["n"] / m["people"], 2)

json.dump(full, open(OUT + "study4-full.json", "w"))

# ================================================================ figures
points = {}
g7 = np.linspace(-3, 3, 61)
g4 = np.linspace(0, 4, 41)
points["gridTrust"] = [float(v) for v in g7]
points["gridScale4"] = [float(v) for v in g4]
kind = {"Humanlike AI": "hybrid", "Standard AI": "ai", "Doctor": "human"}
for k, lab, sc in OUTCOMES:
    grid = g7 if k in ("trust", "belief") else g4
    points[f"between_{k}"] = [series(c, KEY[c], G[c][f"{k}_first"], grid, dict(kind=kind[c])) for c in ["Doctor", "Humanlike AI", "Standard AI"]]
    points[f"within_{k}"] = [series(RECLAB[r], r, d[f"{k}_{r}"], grid, dict(kind=kind[RECLAB[r]])) for r in ["doctor", "humanlike", "standard"]]
json.dump(points, open(OUT + "study4-points.json", "w"))
print("wrote study4-full.json and study4-points.json")
