"""
Compare human recommenders with AI recommenders in Study 1, from the released file.

Reads   public/data/study1-ratings.csv
Writes  src/data/trust-in-medical-ai/study1-human-vs-ai.json

Needs: pandas, numpy, scipy.  Run from the repository root.

Groups
  Human   doctor, nurse, doctor (remote visit), therapist, personal trainer, layperson   (6 recommenders)
  AI      AI in general, AI diagnostic tool, AI chatbot, AI fitness coach               (4 recommenders)
  Doctor using AI is shown on its own. The dissertation notebook counts it as AI in the mixed models;
  the "AI plus doctor using AI" rows below show that the answers do not change if you do the same.

Each person's score for a group is the average of their ratings of that group's recommenders. A person with
any rating missing in a group has no score for that group (the same rule the notebook uses for composites).
Tests are paired t tests, with Cohen's d for paired data and its interval from the noncentral t.
Subgroup results are only shown for groups of 10 or more people, and race only for groups of 30 or more.
"""
import json
import numpy as np
import pandas as pd
from scipy import stats, optimize

OUT = "src/data/trust-in-medical-ai/"
d = pd.read_csv("public/data/study1-ratings.csv")
rng = np.random.default_rng(2023)

HUMAN = ["doctor", "nurse", "doctor_remote", "therapist", "personal_trainer", "layperson"]
AI = ["ai_general", "ai_diagnostic", "ai_chatbot", "ai_fitness"]
HYBRID = ["doctor_using_ai"]
LABEL = {"doctor": "Doctor", "nurse": "Nurse", "doctor_remote": "Doctor, remote visit", "therapist": "Therapist",
         "personal_trainer": "Personal trainer", "layperson": "Layperson", "doctor_using_ai": "Doctor using AI",
         "ai_general": "AI, general", "ai_diagnostic": "AI diagnostic tool", "ai_chatbot": "AI chatbot",
         "ai_fitness": "AI fitness coach"}
MEASURES = [("trust", "Trust"), ("capability", "Quantitative reasoning"), ("intuition", "Intuition")]


def r2(x, k=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), k)


def boot_ci(x, B=2000):
    x = np.asarray(pd.Series(x).dropna(), float)
    means = rng.choice(x, size=(B, len(x)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def t_ci(x):
    x = np.asarray(pd.Series(x).dropna(), float)
    n = len(x)
    h = stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n)
    return float(x.mean() - h), float(x.mean() + h)


def d_ci(dz, n, level=0.95):
    t = dz * np.sqrt(n)
    df = n - 1
    a = (1 - level) / 2

    def f(nc, q):
        return stats.nct.cdf(t, df, nc) - q
    w = 4 * np.sqrt(1 + t ** 2 / (2 * df))
    lo = optimize.brentq(f, t - w, t + w, args=(1 - a,))
    hi = optimize.brentq(f, t - w, t + w, args=(a,))
    return lo / np.sqrt(n), hi / np.sqrt(n)


def cronbach(df):
    c = df.cov()
    k = df.shape[1]
    raw = k / (k - 1) * (1 - np.trace(c.values) / c.values.sum())
    r = df.corr()
    rbar = (r.values.sum() - k) / (k * (k - 1))
    return float(raw), float(rbar)


def density(x, grid, adjust=1.5):
    x = np.asarray(pd.Series(x).dropna(), float)
    iqr = np.subtract(*np.percentile(x, [75, 25]))
    bw = 0.9 * min(x.std(ddof=1), iqr / 1.34) * len(x) ** (-0.2) * adjust
    return np.exp(-0.5 * ((grid[:, None] - x[None, :]) / bw) ** 2).sum(axis=1) / (len(x) * bw * np.sqrt(2 * np.pi))


def group_score(keys, measure):
    return d[[f"{measure}_{k}" for k in keys]].mean(axis=1, skipna=False)


# --------------------------------------------------------------- per-person group scores
score = {}
for m, _ in MEASURES:
    score[(m, "human")] = group_score(HUMAN, m)
    score[(m, "ai")] = group_score(AI, m)
    score[(m, "hybrid")] = d[f"{m}_doctor_using_ai"]
    score[(m, "ai5")] = group_score(AI + HYBRID, m)


def paired(a, b):
    x = pd.concat([a, b], axis=1).dropna()
    x.columns = ["a", "b"]
    diff = x.a - x.b
    n = len(x)
    t, p = stats.ttest_rel(x.a, x.b)
    h = stats.t.ppf(0.975, n - 1) * diff.std(ddof=1) / np.sqrt(n)
    dz = diff.mean() / diff.std(ddof=1)
    lo, hi = d_ci(dz, n)
    return dict(n=n, meanA=r2(x.a.mean()), sdA=r2(x.a.std()), meanB=r2(x.b.mean()), sdB=r2(x.b.std()),
                diff=r2(diff.mean()), lo=r2(diff.mean() - h), hi=r2(diff.mean() + h), t=r2(t), df=n - 1, p=float(p),
                d=r2(dz), dLo=r2(lo), dHi=r2(hi),
                higher=int((diff > 0).sum()), same=int((diff == 0).sum()), lower=int((diff < 0).sum()))


out = {}
out["groups"] = dict(human=[LABEL[k] for k in HUMAN], ai=[LABEL[k] for k in AI], hybrid=[LABEL[k] for k in HYBRID])

# --------------------------------------------------------------- headline tests
tests = []
for m, ml in MEASURES:
    row = dict(measure=ml, key=m)
    row["human_vs_ai"] = paired(score[(m, "human")], score[(m, "ai")])
    row["human_vs_hybrid"] = paired(score[(m, "human")], score[(m, "hybrid")])
    row["hybrid_vs_ai"] = paired(score[(m, "hybrid")], score[(m, "ai")])
    row["human_vs_ai5"] = paired(score[(m, "human")], score[(m, "ai5")])
    tests.append(row)
out["tests"] = tests

# --------------------------------------------------------------- per-person distributions
grid = np.linspace(0, 10, 51)
clouds = []
for m, ml in MEASURES:
    rows = []
    for g, gl, kind in [("human", "Human recommenders (average of 6)", "human"),
                        ("hybrid", "Doctor using AI", "hybrid"),
                        ("ai", "AI recommenders (average of 4)", "ai")]:
        v = score[(m, g)]
        lo, hi = boot_ci(v)
        dn = density(v, grid)
        dn = dn / dn.max()
        rows.append(dict(id=f"{m}_{g}", label=gl, kind=kind, n=int(v.notna().sum()), mean=r2(v.mean()), lo=r2(lo), hi=r2(hi),
                         values=[None if pd.isna(a) else r2(a, 2) for a in v], density=[r2(a, 3) for a in dn]))
    clouds.append(dict(key=m, measure=ml, rows=rows))
out["clouds"] = clouds
out["densityGrid10"] = [float(v) for v in grid]

# --------------------------------------------------------------- recommender profile
profile = []
for grp, keys in [("human", HUMAN), ("hybrid", HYBRID), ("ai", AI)]:
    for k in keys:
        cells = []
        for m, ml in MEASURES:
            v = d[f"{m}_{k}"].dropna()
            lo, hi = t_ci(v)
            cells.append(dict(mean=r2(v.mean()), lo=r2(lo), hi=r2(hi), n=int(len(v))))
        profile.append(dict(id=k, label=LABEL[k], group=grp, cells=cells))
# order inside each group by trust, high to low
order = {"human": 0, "hybrid": 1, "ai": 2}
profile.sort(key=lambda r: (order[r["group"]], -r["cells"][0]["mean"]))
out["profile"] = profile

# --------------------------------------------------------------- do people who trust humans trust AI?
tr = pd.concat([score[("trust", "human")], score[("trust", "ai")]], axis=1).dropna()
tr.columns = ["human", "ai"]
r, p = stats.pearsonr(tr.human, tr.ai)
z = np.arctanh(r)
se = 1 / np.sqrt(len(tr) - 3)
lo, hi = np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)
lin = stats.linregress(tr.human, tr.ai)
out["trustLink"] = dict(n=len(tr), r=r2(r, 3), lo=r2(lo, 3), hi=r2(hi, 3), p=float(p), slope=r2(lin.slope, 3),
                        intercept=r2(lin.intercept, 3),
                        points=[[r2(a, 2), r2(b, 2)] for a, b in zip(tr.human, tr.ai)])
links = []
for m, ml in MEASURES:
    x = pd.concat([score[(m, "human")], score[(m, "ai")]], axis=1).dropna()
    rr, pp = stats.pearsonr(x.iloc[:, 0], x.iloc[:, 1])
    zz = np.arctanh(rr)
    ss = 1 / np.sqrt(len(x) - 3)
    links.append(dict(measure=ml, n=len(x), r=r2(rr, 3), lo=r2(np.tanh(zz - 1.96 * ss), 3), hi=r2(np.tanh(zz + 1.96 * ss), 3), p=float(pp)))
out["links"] = links

# --------------------------------------------------------------- consistency within each group
cons = []
for m, ml in MEASURES:
    for g, keys, gl in [("human", HUMAN, "Human (6)"), ("ai", AI, "AI (4)")]:
        a, rbar = cronbach(d[[f"{m}_{k}" for k in keys]])
        cons.append(dict(measure=ml, group=gl, k=len(keys), alpha=r2(a, 2), meanR=r2(rbar, 2)))
out["consistency"] = cons

# --------------------------------------------------------------- who shows the gap
VARS = [("age_group", "Age"), ("gender", "Gender"), ("race", "Race"), ("education", "Education"),
        ("politics", "Political views"), ("ai_experience", "Experience with AI")]
MIN_N, MIN_RACE = 10, 30
subs = []
for col, name in VARS:
    groups = []
    samples = {m: [] for m, _ in MEASURES}
    for lvl in [x for x in d[col].dropna().unique()]:
        idx = d[col] == lvl
        n_people = int(idx.sum())
        if n_people < MIN_N or (col == "race" and n_people < MIN_RACE):
            continue
        cells = []
        for m, ml in MEASURES:
            gap = (score[(m, "human")] - score[(m, "ai")])[idx].dropna()
            if len(gap) < MIN_N:
                cells.append(None)
                continue
            lo, hi = t_ci(gap)
            cells.append(dict(mean=r2(gap.mean()), lo=r2(lo), hi=r2(hi), n=int(len(gap))))
            samples[m].append(gap.values)
        groups.append(dict(label=str(lvl), n=n_people, cells=cells))
    order_levels = {"age_group": ["18-29", "30-44", "45-59", "60+"], "politics": ["Liberal", "Moderate", "Conservative"],
                    "education": ["No college degree", "College degree or more"],
                    "ai_experience": ["None or a little", "Moderate or more"], "gender": ["Woman", "Man"],
                    "race": ["White", "Black"]}[col]
    groups.sort(key=lambda g: order_levels.index(g["label"]))
    tests_g = []
    for m, ml in MEASURES:
        arrs = samples[m]
        if len(arrs) < 2:
            tests_g.append(None)
            continue
        if len(arrs) == 2:
            t, pv = stats.ttest_ind(arrs[0], arrs[1])
            tests_g.append(dict(stat="t", value=r2(t), df=int(len(arrs[0]) + len(arrs[1]) - 2), p=float(pv)))
        else:
            F, pv = stats.f_oneway(*arrs)
            tests_g.append(dict(stat="F", value=r2(F), df=[len(arrs) - 1, int(sum(len(a) for a in arrs) - len(arrs))], p=float(pv)))
    subs.append(dict(variable=name, groups=groups, tests=tests_g))
out["subgroups"] = subs
out["subgroupNote"] = ("Each dot is the average gap (human minus AI) for the people in that group, with its 95% confidence interval. "
                       "Groups under 10 people are not shown, and race is shown only for groups of 30 or more. "
                       "The tests ask whether the gap differs between the groups shown; they are exploratory and not corrected for the "
                       "18 comparisons.")

json.dump(out, open(OUT + "study1-human-vs-ai.json", "w"))
print("wrote", OUT + "study1-human-vs-ai.json")
for t in tests:
    h = t["human_vs_ai"]
    print(t["measure"], h["meanA"], h["meanB"], h["diff"], h["lo"], h["hi"], "t", h["t"], "p", h["p"], "d", h["d"], h["dLo"], h["dHi"], "n", h["n"],
          "up/same/down", h["higher"], h["same"], h["lower"])
print(out["trustLink"]["r"], out["trustLink"]["n"])
for s in subs:
    print(s["variable"], [(g["label"], g["n"]) for g in s["groups"]], [t and (t["stat"], t["value"], round(t["p"], 3)) for t in s["tests"]])
