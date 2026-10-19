"""
Compute every Study 5 table and figure from the released file.

Reads   public/data/study5-ratings.csv
Writes  src/data/trust-in-medical-ai/study5-full.json    tables, tests and models
        src/data/trust-in-medical-ai/study5-points.json  per-person values for the jittered plots

Study 5 replicated the within-person part of Study 4 and added a between-person test of voice. 854 adults read three vignettes
(a doctor, a humanlike AI and a standard AI) and rated trust and belief in each recommendation. Half also heard a voice
recording with the written recommendation; half read it only. The preregistration is public/docs/study5-preregistration.pdf.

Trust/belief is the average of the trust and belief ratings (they correlate at about .81), as in the dissertation.
Mind perception is the average of the seven mind-perception items (alpha = .96, as in the dissertation).
Differences are the first group minus the second, with the doctor or the humanlike AI first: a positive number means more
trust in the doctor or the humanlike AI. For voice, a positive number means more trust when the recommendation was voiced.
The dissertation reports some of these with the opposite sign.
Cohen's d: pooled SD for two groups; d_z for pairs of ratings.
The mixed ANOVA uses the 727 people who rated all three recommenders; the dissertation's Tables 20 and 21 report slightly
different degrees of freedom because they include people with missing ratings.
Mediation follows Montoya and Hayes (2017) for two within-person conditions: the path from the condition to mind perception is
the mean difference in mind perception, the path from mind perception to trust/belief is estimated from the differences while
holding each person's average mind perception fixed, and the interval comes from resampling people 3,000 times. The notebook
attempted the same with Mplus and the R process package and left the estimates in its text; these land within about .02 of them.
Age enters models as the age group number (1 = 18 to 44, 4 = 70 and over).

Needs: pandas, numpy, scipy, statsmodels.  Run from the repository root.
"""
import json
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "analysis")
from trust_stats import r2, desc, welch, paired, lmm, series, cronbach, DEMO, sample_table  # noqa: E402

warnings.filterwarnings("ignore")
OUT = "src/data/trust-in-medical-ai/"
d = pd.read_csv("public/data/study5-ratings.csv")
REC = ["humanlike", "standard", "doctor"]
RECLAB = {"humanlike": "Humanlike AI", "standard": "Standard AI", "doctor": "Doctor"}
MI = ["capable", "anticipate", "feelings", "account", "familiar", "transparent", "process"]
MI_LAB = {"capable": "Capable of accurate recommendations", "anticipate": "Can anticipate my health needs", "feelings": "Understands my feelings",
          "account": "Can account for my health needs", "familiar": "Process feels familiar", "transparent": "Process is transparent", "process": "I understand the process"}
d["voiced"] = (d.voice == "Written and voiced").astype(int)
d["man"] = (d.gender == "Man").astype(float).where(d.gender.notna())
d["age"] = d.age_group.map({"18-44": 1, "45-59": 2, "60-69": 3, "70+": 4})
for r in REC:
    d[f"tb_{r}"] = (d[f"trust_{r}"] + d[f"belief_{r}"]) / 2
    d[f"mind_{r}"] = d[[f"mind_{m}_{r}" for m in MI]].mean(axis=1, skipna=False)
V, W = d[d.voiced == 1], d[d.voiced == 0]

full = {}
full["sample"] = sample_table(d, DEMO)
three = d[[f"tb_{r}" for r in REC]].dropna()
full["design"] = dict(n=len(d), written=int(len(W)), voiced=int(len(V)), allThree=int(len(three)),
                      allThreeWritten=int(d.loc[three.index].voiced.eq(0).sum()), allThreeVoiced=int(d.loc[three.index].voiced.eq(1).sum()))

# ---------------------------------------------------------------- descriptives
MEAS = [("tb", "Trust/belief", "-3 to 3"), ("trust", "Trust", "-3 to 3"), ("belief", "Belief", "-3 to 3"), ("warmth", "Warmth", "0 to 4"), ("competence", "Competence", "0 to 4"),
        ("mind", "Mind perception", "0 to 10"), ("appropriate", "Appropriate for these decisions", "-3 to 3"), ("praise", "Praise if it works", "0 to 100"), ("blame", "Blame if it fails", "0 to 100")]
full["descriptives"] = [dict(id=k, label=lab, scale=sc, cells={r: desc(d[f"{k}_{r}"]) for r in REC}) for k, lab, sc in MEAS]
full["descriptivesByVoice"] = [dict(id=k, label=lab, scale=sc, cells={r: dict(written=desc(W[f"{k}_{r}"]), voiced=desc(V[f"{k}_{r}"])) for r in REC}) for k, lab, sc in MEAS[:3]]
full["trustBelief"] = dict(r=r2(pd.concat([d[f"trust_{r}"] for r in REC]).corr(pd.concat([d[f"belief_{r}"] for r in REC])), 3))
allm = pd.concat([d[[f"mind_{m}_{r}" for m in MI]].set_axis(MI, axis=1) for r in REC]).dropna()
full["mindReliability"] = dict(alpha=r2(cronbach(allm), 3), n=int(len(allm)),
                               items=[dict(id=m, label=MI_LAB[m], cells={r: desc(d[f"mind_{m}_{r}"]) for r in REC}) for m in MI])

# ---------------------------------------------------------------- mixed ANOVA on the people who rated all three
c = d.loc[three.index]
Y = three.values
g = c.voiced.values.astype(int)
n, k = Y.shape
subj, gm = Y.mean(1), Y.mean()
n1, n0 = int((g == 1).sum()), int((g == 0).sum())
ss_rec = n * ((Y.mean(0) - gm) ** 2).sum()
ss_voice = k * (n1 * (subj[g == 1].mean() - gm) ** 2 + n0 * (subj[g == 0].mean() - gm) ** 2)
ss_subj = k * ((subj - gm) ** 2).sum()
ss_bres = ss_subj - ss_voice
cell = np.array([[Y[g == gg][:, j].mean() for j in range(k)] for gg in (0, 1)])
ss_cells = sum(((n1 if gg else n0) * (cell[gg, j] - gm) ** 2) for gg in (0, 1) for j in range(k))
ss_int = ss_cells - ss_rec - ss_voice
ss_wres = ((Y - gm) ** 2).sum() - ss_subj - ss_rec - ss_int
dfb, dfw = n - 2, (n - 2) * (k - 1)


def row(label, ss, df1, ss_err, df2, stratum):
    F = (ss / df1) / (ss_err / df2)
    return dict(effect=label, stratum=stratum, ss=r2(ss), df1=df1, df2=df2, ms=r2(ss / df1, 3), F=r2(F), p=float(stats.f.sf(F, df1, df2)), pes=r2(ss / (ss + ss_err), 3))


full["mixedAnova"] = dict(n=int(n), rows=[row("Voice", ss_voice, 1, ss_bres, dfb, "between people"),
                                          row("Recommender", ss_rec, 2, ss_wres, dfw, "within people"),
                                          row("Recommender × voice", ss_int, 2, ss_wres, dfw, "within people")],
                          residualBetween=dict(ss=r2(ss_bres), df=dfb, ms=r2(ss_bres / dfb, 3)), residualWithin=dict(ss=r2(ss_wres), df=dfw, ms=r2(ss_wres / dfw, 3)),
                          reported=dict(recommender=dict(F=145.4, df1=2, df2=1514, pes=0.161), interaction=dict(F=16.32, df1=2, df2=1512, pes=0.021), voice=dict(F=0.12, df1=1, df2=850, p=0.727)))

# ---------------------------------------------------------------- voiced versus written, recommender by recommender
vt = {}
for m in ("tb", "trust", "belief"):
    vt[m] = [welch(V[f"{m}_{r}"], W[f"{m}_{r}"], f"{RECLAB[r]}: voiced versus written", id=f"voice-{r}", first="Written and voiced", second="Written only", recommender=RECLAB[r]) for r in ("doctor", "humanlike", "standard")]
full["voiceTests"] = vt
full["voiceMind"] = [welch(V[f"mind_{r}"], W[f"mind_{r}"], f"{RECLAB[r]}: mind perception, voiced versus written", id=f"voice-mind-{r}", recommender=RECLAB[r]) for r in ("doctor", "humanlike", "standard")]
# all three recommenders together, per person: does voice change the average?
avg = d[[f"tb_{r}" for r in REC]].mean(axis=1, skipna=False)
full["voiceAll"] = welch(avg[d.voiced == 1], avg[d.voiced == 0], "All three recommenders averaged: voiced versus written", id="voice-all")

# ---------------------------------------------------------------- recommenders against each other
WP = [("doc-std", "Doctor versus standard AI", "doctor", "standard"), ("hum-std", "Humanlike AI versus standard AI", "humanlike", "standard"),
      ("hum-doc", "Humanlike AI versus doctor", "humanlike", "doctor")]
pt = {}
for m in ("tb", "trust", "belief", "warmth", "competence", "mind"):
    rows = []
    for pid, lab, a, b in WP:
        r = paired(d[f"{m}_{a}"], d[f"{m}_{b}"], lab, id=pid, first=RECLAB[a], second=RECLAB[b])
        r["pBonferroni"] = min(1.0, r["p"] * 3)
        rows.append(r)
    pt[m] = rows
full["pairedTests"] = pt
# the same comparison inside each voice group
full["pairedByVoice"] = [dict(voice=name, rows=[paired(grp[f"tb_{a}"], grp[f"tb_{b}"], lab, id=pid) for pid, lab, a, b in WP]) for name, grp in (("Written only", W), ("Written and voiced", V))]

# ---------------------------------------------------------------- the ranking question
rk = d[[f"rank_trust_{r}" for r in REC]].dropna()
chi, pf = stats.friedmanchisquare(*[rk[f"rank_trust_{r}"] for r in REC])
full["ranking"] = dict(n=int(len(rk)), friedman=r2(chi), p=float(pf),
                       rows=[dict(rec=RECLAB[r], first=int((rk[f"rank_trust_{r}"] == 1).sum()), second=int((rk[f"rank_trust_{r}"] == 2).sum()),
                                  third=int((rk[f"rank_trust_{r}"] == 3).sum()), mean=r2(rk[f"rank_trust_{r}"].mean())) for r in ("doctor", "humanlike", "standard")])

# ---------------------------------------------------------------- mixed model (long format)
rows = []
for r in REC:
    rows.append(pd.DataFrame({"id": d.participant, "rec": r, "tb": d[f"tb_{r}"], "mind": d[f"mind_{r}"], "warm": d[f"warmth_{r}"], "comp": d[f"competence_{r}"],
                              "voiced": d.voiced, "man": d.man, "age": d.age}))
L = pd.concat(rows, ignore_index=True)
L["std"] = (L.rec == "standard").astype(int)
L["doc"] = (L.rec == "doctor").astype(int)
NAMES = {"Intercept": "Intercept", "std": "Standard AI (versus humanlike AI)", "doc": "Doctor (versus humanlike AI)", "voiced": "Voiced (versus written only)",
         "std:voiced": "Standard AI × voiced", "doc:voiced": "Doctor × voiced", "mind": "Mind perception", "warm": "Warmth", "comp": "Competence",
         "age": "Age group (1 to 4)", "man": "Man (versus woman)"}
FORMS = [("tb ~ std * voiced + doc * voiced", "Recommender, voice and their interaction"),
         ("tb ~ std * voiced + doc * voiced + mind", "Add mind perception"),
         ("tb ~ std * voiced + doc * voiced + mind + warm + comp + age + man", "Add warmth, competence, age group and gender (dissertation Table 22)")]
full["mixedModels"] = [lmm(f, L, "id", "tb", lab, NAMES) for f, lab in FORMS]

# ---------------------------------------------------------------- mediation through mind perception
def mediation(a_, b_, label, B=3000):
    x = d[[f"tb_{a_}", f"tb_{b_}", f"mind_{a_}", f"mind_{b_}"]].dropna()
    dy = (x[f"tb_{a_}"] - x[f"tb_{b_}"]).values
    dm = (x[f"mind_{a_}"] - x[f"mind_{b_}"]).values
    mb = ((x[f"mind_{a_}"] + x[f"mind_{b_}"]) / 2).values
    mb = mb - mb.mean()

    def est(dy, dm, mb):
        X = np.column_stack([np.ones(len(dy)), dm, mb])
        beta = np.linalg.lstsq(X, dy, rcond=None)[0]
        return dm.mean(), beta[1], beta[0], dy.mean()
    a, b, direct, total = est(dy, dm, mb)
    arr = np.column_stack([dy, dm, mb])
    rng = np.random.default_rng(7)
    boots = []
    for _ in range(B):
        s = arr[rng.integers(0, len(arr), len(arr))]
        aa, bb, cc, tt = est(s[:, 0], s[:, 1], s[:, 2])
        boots.append([aa * bb, cc, tt])
    boots = np.array(boots)
    # standard errors for the paths from the regression, and a Sobel-type z for a times b
    X = np.column_stack([np.ones(len(dy)), dm, mb])
    beta = np.linalg.lstsq(X, dy, rcond=None)[0]
    res = dy - X @ beta
    cov = np.linalg.inv(X.T @ X) * (res @ res / (len(dy) - 3))
    se_b = float(np.sqrt(cov[1, 1]))
    se_a = float(dm.std(ddof=1) / np.sqrt(len(dm)))
    se_ind = float(np.sqrt(a ** 2 * se_b ** 2 + b ** 2 * se_a ** 2))
    return dict(label=label, n=int(len(x)), a=r2(a, 3), aSE=r2(se_a, 3), b=r2(b, 3), bSE=r2(se_b, 3), indirect=r2(a * b, 3), lo=r2(np.percentile(boots[:, 0], 2.5), 3),
                hi=r2(np.percentile(boots[:, 0], 97.5), 3), z=r2(a * b / se_ind), p=float(2 * stats.norm.sf(abs(a * b / se_ind))),
                direct=r2(direct, 3), directLo=r2(np.percentile(boots[:, 1], 2.5), 3), directHi=r2(np.percentile(boots[:, 1], 97.5), 3), total=r2(total, 3),
                share=r2(100 * a * b / total, 0) if abs(total) > 0.05 else None)


med = [mediation("doctor", "standard", "Doctor versus standard AI"), mediation("humanlike", "standard", "Humanlike AI versus standard AI"),
       mediation("humanlike", "doctor", "Humanlike AI versus doctor")]
med[0]["reported"], med[1]["reported"], med[2]["reported"] = 0.486, 0.412, -0.015
full["mediation"] = med

cols = ["tb", "mind", "warmth", "competence"]
long = pd.concat([pd.DataFrame({k: d[f"{k}_{r}"] for k in cols}) for r in REC], ignore_index=True)
full["correlations"] = dict(labels=["Trust/belief", "Mind perception", "Warmth", "Competence"], r=[[r2(long[a].corr(long[b]), 3) for b in cols] for a in cols], n=int(long.dropna().shape[0]))
json.dump(full, open(OUT + "study5-full.json", "w"))

# ---------------------------------------------------------------- figures
points = {}
g7 = np.linspace(-3, 3, 61)
g10 = np.linspace(0, 10, 51)
points["gridTrust"] = [float(v) for v in g7]
points["gridMind"] = [float(v) for v in g10]
kind = {"humanlike": "hybrid", "standard": "ai", "doctor": "human"}
points["tb"] = [series(RECLAB[r], r, d[f"tb_{r}"], g7, dict(kind=kind[r])) for r in ["doctor", "humanlike", "standard"]]
points["tbByVoice"] = [dict(rec=RECLAB[r], kind=kind[r], rows=[series("Written only", f"{r}_written", W[f"tb_{r}"], g7, dict(kind=kind[r])),
                                                                series("Written and voiced", f"{r}_voiced", V[f"tb_{r}"], g7, dict(kind=kind[r]))]) for r in ["doctor", "humanlike", "standard"]]
points["mind"] = [series(RECLAB[r], r, d[f"mind_{r}"], g10, dict(kind=kind[r])) for r in ["doctor", "humanlike", "standard"]]
json.dump(points, open(OUT + "study5-points.json", "w"))
print("wrote study5-full.json and study5-points.json")
