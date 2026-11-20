"""
Compute every Study 6 table and figure from the released file.

Reads   public/data/study6-ratings.csv
Writes  src/data/trust-in-medical-ai/study6-full.json   sample, tables, models, mediation and day-by-day means

Study 6 followed people for 14 daily surveys; the last one, on day 14, also held the mind-perception questions. On day 8, 455 of the
510 people with daily data were randomly shown sleep and device-in-bed advice from a doctor or an AI. The preregistration is on
OSF (10.17605/OSF.IO/736HEF).

Weight on advice (the Judge-Advisor measure) is how far a day's value moved from the person's days 1 to 7 average toward the
recommendation (8.25 hours of sleep, 15 minutes on a device in bed), as a share of the distance, capped at -2 and 2.
Models follow the dissertation's Tables 23 and 24: linear mixed models with a random intercept for each person, REML.
  Model 1  after-advice indicator, all 510 people (the 55 who never got the advice are part of the baseline comparison)
  Model 2  adds recommender (0 = doctor, 1 = AI), its interaction with the advice, age group and gender, for the 455 assigned
  Model 3  adds mind perception, for the 412 assigned people who answered it
Age enters as the age group number (1 = 18 to 44, 4 = 70 and over), so its coefficient is in different units than the
dissertation's age in years. People who reported a gender other than woman or man are too few for their own group and are
coded with women (0), as the dissertation's male/not male indicator did. People who skipped the demographic block drop out of
Models 2 and 3 on the age term.
Mediation follows the dissertation: path a is the difference in mind perception (AI minus doctor), paths b and c' come from a
mixed model of the after-advice days with a random intercept, c is the same model without mind perception, and the indirect
effect a x b is tested with the Sobel z (as in the printed z values) and a 5,000-resample bootstrap of people.
Differences are AI minus doctor. A negative mind-perception difference means more mind in the doctor.

Needs: pandas, numpy, scipy, statsmodels.  Run from the repository root.
"""
import json
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf

sys.path.insert(0, "analysis")
import trust_stats  # noqa: E402
from trust_stats import r2, desc, cronbach, DEMO, sample_table  # noqa: E402

warnings.filterwarnings("ignore")
OUT = "src/data/trust-in-medical-ai/"
MIND = ["mind_anticipate", "mind_account", "mind_feelings", "mind_familiar", "mind_capable", "mind_transparent", "mind_process"]



def lmm(formula, data, group, y, label, names=None):
    """The shared Study 3 to 5 helper tries lbfgs first. For Study 6's sleep Model 1 that stops at a zero person variance (a singular
    fit, and the intercept interval blows up), while the REML optimum has a small positive variance (ICC about .01, as the dissertation
    reports). This tries powell and Nelder-Mead first and keeps the first that converges with a positive variance. The model and the
    statistics are the same as the helper's."""
    import re
    need = [t for t in data.columns if re.search(rf"\b{re.escape(t)}\b", formula)]
    D = data.dropna(subset=need).reset_index(drop=True)
    md = smf.mixedlm(formula, D, groups=D[group])
    res = None
    for method in ("powell", "nm"):
        r = md.fit(reml=True, method=method, maxiter=4000)
        if r.converged and float(r.cov_re.values[0, 0]) > 1e-6:
            res = r
            break
    if res is None:
        return trust_stats.lmm(formula, data, group, y, label, names)
    X = md.exog
    fe = res.fe_params.values
    var_f = float(np.var(X @ fe))
    var_p = float(res.cov_re.values[0, 0])
    var_e = float(res.scale)
    tot = var_f + var_p + var_e
    terms = []
    for nm in res.fe_params.index:
        b, se = float(res.fe_params[nm]), float(res.bse_fe[nm])
        terms.append(dict(term=(names or {}).get(nm, nm), raw=nm, b=r2(b, 3), se=r2(se, 3), lo=r2(b - 1.96 * se, 3), hi=r2(b + 1.96 * se, 3),
                          z=r2(b / se), p=float(2 * stats.norm.sf(abs(b / se)))))
    return dict(label=label, formula=formula, n=int(len(D)), people=int(D[group].nunique()), terms=terms, varPerson=r2(var_p, 3), varResidual=r2(var_e, 3),
                icc=r2(var_p / (var_p + var_e), 3), r2m=r2(var_f / tot, 3), r2c=r2((var_f + var_p) / tot, 3), converged=bool(res.converged))


d = pd.read_csv("public/data/study6-ratings.csv")
d["AI"] = (d["recommender"] == "AI").astype(float).where(d["recommender"].notna())
d["after"] = (d["phase"] == "After advice").astype(float)
d["age_n"] = d["age_group"].map({"18-44": 1, "45-59": 2, "60-69": 3, "70+": 4})
d["male"] = np.where(d["age_group"].isna(), np.nan, (d["gender"] == "Man").astype(float))
people = d.drop_duplicates("participant").set_index("participant")
assigned = people[people["recommender"].notna()]
a_ids = set(assigned.index)
da = d[d["participant"].isin(a_ids)]

# Sample
post_days = da[da["after"] == 1].groupby("participant")["sleep_hours"].count().reindex(list(a_ids)).fillna(0)
sample = dict(
    daily=int(len(people)), assigned=int(len(assigned)), notAssigned=int(len(people) - len(assigned)),
    doctor=int((assigned["recommender"] == "Doctor").sum()), ai=int((assigned["recommender"] == "AI").sum()),
    withMind=int(assigned["mind_perception"].notna().sum()), rows=int(len(d)),
    minPostSurveys=int(post_days.min()), medianPostSurveys=float(post_days.median()),
    fewerThan3Post=int((post_days < 3).sum()), noPost=int((post_days == 0).sum()),
    table=sample_table(assigned, DEMO),
)

# Mind perception
mp = assigned.dropna(subset=["mind_perception"])
doc = mp[mp["recommender"] == "Doctor"]["mind_perception"]
ai = mp[mp["recommender"] == "AI"]["mind_perception"]
fit_a = smf.ols("mind_perception ~ AI", mp).fit()
sp = np.sqrt(((len(doc) - 1) * doc.var() + (len(ai) - 1) * ai.var()) / (len(doc) + len(ai) - 2))
tt = stats.ttest_ind(ai, doc, equal_var=False)
mind = dict(
    alpha=r2(cronbach(mp[MIND]), 3), n=int(len(mp)), doctor=desc(doc), ai=desc(ai),
    a=r2(fit_a.params["AI"], 3), aSe=r2(fit_a.bse["AI"], 3), aLo=r2(fit_a.conf_int().loc["AI", 0], 3), aHi=r2(fit_a.conf_int().loc["AI", 1], 3),
    z=r2(fit_a.params["AI"] / fit_a.bse["AI"], 2), p=float(fit_a.pvalues["AI"]), t=r2(tt.statistic, 2), df=r2(tt.df, 1), d=r2((ai.mean() - doc.mean()) / sp, 2),
)

# Models
NAMES = {"after": "Change after the advice", "AI": "Recommender (0 = doctor, 1 = AI)", "after:AI": "Advice x recommender",
         "age_n": "Age group (1 to 4)", "male": "Gender (1 = man)", "mind_perception": "Mind perception"}
OUTCOMES = [("sleep", "woa_sleep", "Sleep"), ("device", "woa_device", "Device in bed")]
models = {}
for key, y, label in OUTCOMES:
    m1 = lmm(f"{y} ~ after", d, "participant", y, "Model 1", NAMES)
    m2 = lmm(f"{y} ~ after * AI + age_n + male", d, "participant", y, "Model 2", NAMES)
    m3 = lmm(f"{y} ~ after * AI + age_n + male + mind_perception", d, "participant", y, "Model 3", NAMES)
    models[key] = dict(label=label, y=y, models=[m1, m2, m3])

# Mediation on the after-advice days
post = d[(d["after"] == 1) & d["recommender"].notna()]
rng = np.random.default_rng(2026)


def paths(frame, y):
    X = frame.dropna(subset=[y, "AI", "mind_perception"])
    pa = X.drop_duplicates("participant")
    a = smf.ols("mind_perception ~ AI", pa).fit()
    tot = smf.mixedlm(f"{y} ~ AI", X, groups=X["participant"]).fit(reml=True)
    full = smf.mixedlm(f"{y} ~ AI + mind_perception", X, groups=X["participant"]).fit(reml=True)
    return a, tot, full, X


med = {}
for key, y, label in OUTCOMES:
    a, tot, full, X = paths(post, y)
    A, SA = a.params["AI"], a.bse["AI"]
    B, SB = full.fe_params["mind_perception"], full.bse_fe["mind_perception"]
    ind = A * B
    sobel = np.sqrt(B ** 2 * SA ** 2 + A ** 2 * SB ** 2)
    ids = X["participant"].unique()
    pa = X.drop_duplicates("participant").set_index("participant")
    # Bootstrap people using the two-step estimates (a by OLS on people, b by OLS of each person's mean on mind perception and recommender)
    pm = X.groupby("participant")[y].mean()
    pp = pa.join(pm.rename("ybar"))
    boots = []
    for _ in range(5000):
        s = pp.iloc[rng.integers(0, len(pp), len(pp))]
        ba = np.polyfit(s["AI"], s["mind_perception"], 1)[0]
        Xm = np.column_stack([np.ones(len(s)), s["AI"], s["mind_perception"]])
        bb = np.linalg.lstsq(Xm, s["ybar"].to_numpy(), rcond=None)[0][2]
        boots.append(ba * bb)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    med[key] = dict(
        label=label, n=int(len(ids)), obs=int(len(X)),
        a=r2(A, 3), aSe=r2(SA, 3), b=r2(B, 4), bSe=r2(SB, 4), bP=float(2 * stats.norm.sf(abs(B / SB))),
        c=r2(tot.fe_params["AI"], 3), cSe=r2(tot.bse_fe["AI"], 3), cp=r2(full.fe_params["AI"], 3), cpSe=r2(full.bse_fe["AI"], 3),
        ind=r2(ind, 4), sobelSe=r2(sobel, 4), z=r2(ind / sobel, 3), p=float(2 * stats.norm.sf(abs(ind / sobel))),
        bootLo=r2(lo, 4), bootHi=r2(hi, 4),
    )

# Day-by-day means
daily = []
for who in ["Doctor", "AI"]:
    g = da[da["recommender"] == who]
    for day in range(1, 15):
        r = g[g["day"] == day]
        row = dict(recommender=who, day=day)
        for key, y, label in OUTCOMES:
            row[key] = desc(r[y])
        row["sleepHours"] = desc(r["sleep_hours"])
        row["deviceMinutes"] = desc(r["device_minutes"])
        daily.append(row)

# Raw baseline vs after means by recommender, for the plain-language lines
raw = {}
for who in ["Doctor", "AI"]:
    g = da[da["recommender"] == who]
    pb = g[g["after"] == 0].groupby("participant")[["sleep_hours", "device_minutes"]].mean()
    pa_ = g[g["after"] == 1].groupby("participant")[["sleep_hours", "device_minutes"]].mean()
    j = pb.join(pa_, lsuffix="_before", rsuffix="_after").dropna()
    raw[who] = dict(n=int(len(j)), sleepBefore=r2(j["sleep_hours_before"].mean(), 2), sleepAfter=r2(j["sleep_hours_after"].mean(), 2),
                    deviceBefore=r2(j["device_minutes_before"].mean(), 1), deviceAfter=r2(j["device_minutes_after"].mean(), 1))
allp = da.groupby(["participant", "after"])[["sleep_hours", "device_minutes"]].mean().unstack()
raw["Everyone"] = dict(n=int(len(allp.dropna())), sleepBefore=r2(allp[("sleep_hours", 0)].mean(), 2), sleepAfter=r2(allp[("sleep_hours", 1)].mean(), 2),
                       deviceBefore=r2(allp[("device_minutes", 0)].mean(), 1), deviceAfter=r2(allp[("device_minutes", 1)].mean(), 1))

res = dict(sample=sample, mind=mind, models=models, mediation=med, daily=daily, raw=raw,
           notes=dict(target=dict(sleepHours=8.25, deviceMinutes=15), cap=2))
with open(OUT + "study6-full.json", "w") as f:
    json.dump(res, f, indent=1, allow_nan=False)
print(json.dumps(dict(sample={k: v for k, v in sample.items() if k != "table"}, mind=mind, med=med, raw=raw), indent=1))
for key in models:
    for m in models[key]["models"]:
        print(key, m["label"], m["people"], m["n"], m["r2m"], m["r2c"], m["icc"])
        for t in m["terms"]:
            print("   %-34s %7s [%7s,%7s] p=%.3f" % (t["term"], t["b"], t["lo"], t["hi"], t["p"]))
