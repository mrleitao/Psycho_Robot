"""
Compute every Study 2 table and figure from the released file.

Reads   public/data/study2-ratings.csv
Writes  src/data/trust-in-medical-ai/study2-full.json    tables, tests and models
        src/data/trust-in-medical-ai/study2-points.json  per-person values for the jittered plots

Needs: pandas, numpy, scipy, statsmodels.  Run from the repository root.

Study 2 asked 106 adults how much they would trust a doctor, and how much they would trust a medical AI,
for each of twelve medical decisions, and then how they saw the doctor and the AI (quantitative reasoning,
intuition, warmth, competence and seven mind-perception items). The preregistration is in
public/docs/study2-preregistration.pdf and the author's original notebook is public/code/study2-original-analysis.Rmd.

Where the notebook used an R package or Mplus, this uses the closest Python equivalent:
  psych::describe / alpha / corr.test   same formulas (skew and kurtosis are the type 3 estimates)
  psych::statsBy                        pooled within-person and between-person correlations, written out in wb()
  lme4::lmer                            statsmodels MixedLM, restricted maximum likelihood, with the same random effects
  MuMIn / performance R squared         Nakagawa marginal and conditional R squared
  Mplus two-level mediation             person-centred regression paths with a person-level (cluster) bootstrap, see mediation()

Two differences from the notebook come from the public file, not from the method:
  * Ratings are on the scales participants saw (0 to 10, competence and warmth 0 to 4). The notebook kept some of
    the survey's stored codes (for example competence as 4 to 8), so means and model intercepts differ while
    differences, correlations and slopes do not.
  * Age is released in four groups, so models that used age in years use the group number (1 to 4) instead.
Composites are missing when any item is missing (the notebook adds the items). The preregistration said
the remaining items would be averaged.
"""
import json
import numpy as np
import pandas as pd
from scipy import stats, optimize
import statsmodels.formula.api as smf
import warnings

warnings.filterwarnings("ignore")
OUT = "src/data/trust-in-medical-ai/"
d = pd.read_csv("public/data/study2-ratings.csv")
rng = np.random.default_rng(2023)
N = len(d)

# ---------------------------------------------------------------- names
DECISIONS = {
    "prevent_injury_stretching": ("Recommend stretching", "preventative", "bodily injury"),
    "diagnose_broken_bone": ("Diagnose a broken bone", "diagnostic", "bodily injury"),
    "prescribe_pain_medication": ("Prescribe pain medication", "prescriptive", "bodily injury"),
    "prevent_mental_meditation": ("Recommend meditation", "preventative", "mental health"),
    "diagnose_depression": ("Diagnose depression", "diagnostic", "mental health"),
    "prescribe_mental_therapy": ("Prescribe antidepressants", "prescriptive", "mental health"),
    "prevent_acute_vitamins": ("Recommend vitamin C and zinc", "preventative", "acute sickness"),
    "diagnose_strep_throat": ("Diagnose strep throat", "diagnostic", "acute sickness"),
    "prescribe_antibiotics": ("Prescribe antibiotics", "prescriptive", "acute sickness"),
    "prevent_chronic_diet": ("Recommend a strict diet", "preventative", "chronic sickness"),
    "diagnose_diabetes": ("Diagnose diabetes", "diagnostic", "chronic sickness"),
    "prescribe_insulin": ("Prescribe insulin", "prescriptive", "chronic sickness"),
}
STAGES = {"q_diagnosis": ("Diagnostic", "diagnostic"), "q_prescription": ("Prescriptive", "prescriptive"), "q_preventative": ("Preventative", "preventative")}
DOMAINS = {"q_physical": ("Physical health", None), "q_mental": ("Mental health", "mental health"), "q_injury": ("Bodily injury", "bodily injury"),
           "q_acute": ("Acute sickness", "acute sickness"), "q_chronic": ("Chronic sickness", "chronic sickness")}
COMPOSITES = {}  # id -> (label, [decision keys])
for cid, (lab, stage) in STAGES.items():
    COMPOSITES[cid] = (lab, [k for k, v in DECISIONS.items() if v[1] == stage])
for cid, (lab, dom) in DOMAINS.items():
    COMPOSITES[cid] = (lab, [k for k, v in DECISIONS.items() if (v[2] == dom if dom else v[2] != "mental health")])
ORDER_COMPOSITES = ["q_diagnosis", "q_prescription", "q_preventative", "q_physical", "q_mental", "q_injury", "q_acute", "q_chronic"]

QUALITIES = [("quantitative_reasoning", "Quantitative reasoning", "0 to 10"), ("intuition", "Intuition", "0 to 10"),
             ("competence", "Competence", "0 to 4"), ("warmth", "Warmth", "0 to 4"),
             ("general_accuracy", "Accurate recommendations in general", "0 to 10"), ("anticipate_needs", "Can anticipate my health needs", "0 to 10"),
             ("understand_feelings", "Understands my feelings", "0 to 10"), ("account_for_needs", "Can account for my health needs", "0 to 10"),
             ("familiar_process", "Process feels familiar", "0 to 10"), ("transparent_process", "Process is transparent", "0 to 10"),
             ("understand_process", "I understand the process", "0 to 10")]
MIND = ["general_accuracy", "anticipate_needs", "understand_feelings", "account_for_needs", "familiar_process", "transparent_process", "understand_process"]
MIND_ALT = ["anticipate_needs", "account_for_needs", "understand_feelings"]

for cid, (lab, keys) in COMPOSITES.items():
    d[f"needs_{cid}"] = d[[f"needs_quant_{k}" for k in keys]].mean(axis=1, skipna=False)
    for who in ("doctor", "ai"):
        d[f"trust_{who}_{cid}"] = d[[f"trust_{who}_{k}" for k in keys]].mean(axis=1, skipna=False)
d["trust_doctor_all"] = d[[f"trust_doctor_{k}" for k in DECISIONS]].mean(axis=1, skipna=False)
d["trust_ai_all"] = d[[f"trust_ai_{k}" for k in DECISIONS]].mean(axis=1, skipna=False)


# ---------------------------------------------------------------- helpers
def r2(x, k=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), k)


def desc(x):
    x = pd.Series(x).dropna().astype(float)
    n = len(x)
    s = x.std(ddof=1)
    m2 = ((x - x.mean()) ** 2).mean()
    g1 = ((x - x.mean()) ** 3).mean() / m2 ** 1.5
    g2 = ((x - x.mean()) ** 4).mean() / m2 ** 2 - 3
    return dict(n=n, mean=r2(x.mean()), sd=r2(s), median=r2(x.median()), min=r2(x.min()), max=r2(x.max()),
                skew=r2(g1 * ((n - 1) / n) ** 1.5), kurtosis=r2((g2 + 3) * ((n - 1) / n) ** 2 - 3), se=r2(s / np.sqrt(n)))


def boot_ci(x, B=2000):
    x = np.asarray(pd.Series(x).dropna(), float)
    means = rng.choice(x, size=(B, len(x)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def t_ci(x):
    x = np.asarray(pd.Series(x).dropna(), float)
    h = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return float(x.mean() - h), float(x.mean() + h)


def cronbach(df):
    c = df.cov()
    k = df.shape[1]
    raw = k / (k - 1) * (1 - np.trace(c.values) / c.values.sum())
    r = df.corr()
    rbar = (r.values.sum() - k) / (k * (k - 1))
    return float(raw), float(rbar)


def corr_p(df):
    cols = list(df.columns)
    R = np.zeros((len(cols), len(cols)))
    P = np.zeros_like(R)
    Nn = np.zeros_like(R)
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            x = df[[a, b]].dropna()
            r, p = stats.pearsonr(x[a], x[b]) if i != j else (1.0, 0.0)
            R[i, j], P[i, j], Nn[i, j] = r, p, len(x)
    return R, P, Nn


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


def paired(a, b, label=None, **extra):
    x = pd.concat([a, b], axis=1).dropna()
    x.columns = ["a", "b"]
    diff = x.a - x.b
    n = len(x)
    t, p = stats.ttest_rel(x.a, x.b)
    h = stats.t.ppf(0.975, n - 1) * diff.std(ddof=1) / np.sqrt(n)
    dz = diff.mean() / diff.std(ddof=1)
    lo, hi = d_ci(dz, n)
    out = dict(n=n, meanA=r2(x.a.mean()), sdA=r2(x.a.std()), meanB=r2(x.b.mean()), sdB=r2(x.b.std()),
               diff=r2(diff.mean()), lo=r2(diff.mean() - h), hi=r2(diff.mean() + h), t=r2(t), df=n - 1, p=float(p),
               d=r2(dz), dLo=r2(lo), dHi=r2(hi),
               higher=int((diff > 0).sum()), same=int((diff == 0).sum()), lower=int((diff < 0).sum()))
    if label:
        out["label"] = label
    out.update(extra)
    return out


def density(x, grid, adjust=1.5):
    x = np.asarray(pd.Series(x).dropna(), float)
    iqr = np.subtract(*np.percentile(x, [75, 25]))
    bw = 0.9 * min(x.std(ddof=1), iqr / 1.34) * len(x) ** (-0.2) * adjust
    return np.exp(-0.5 * ((grid[:, None] - x[None, :]) / bw) ** 2).sum(axis=1) / (len(x) * bw * np.sqrt(2 * np.pi))


full = {"method": {}}

# ---------------------------------------------------------------- sample
DEMO = [("age_group", "Age group", ["18-44", "45-59", "60-69", "70+"]), ("gender", "Gender", ["Woman", "Man"]),
        ("race", "Race", ["White", "Another or multiple"]), ("education", "Education", ["No college degree", "College degree or more"]),
        ("religiosity", "How religious", ["Not at all to slightly", "Moderately", "More than moderately"]),
        ("ai_experience", "Experience with AI", ["None or a little", "Moderate or more"])]
sample = []
for col, name, levels in DEMO:
    rows = [dict(group=lv, n=int((d[col] == lv).sum()), pct=r2(100 * (d[col] == lv).sum() / N, 1)) for lv in levels]
    sample.append(dict(variable=name, rows=rows, missing=int(d[col].isna().sum())))
full["sample"] = dict(n=N, variables=sample)

# ---------------------------------------------------------------- the twelve decisions: how much quantitative reasoning
full["decisionDescriptives"] = [dict(label=DECISIONS[k][0], id=k, **desc(d[f"needs_quant_{k}"])) for k in DECISIONS]
full["compositeDescriptives"] = [dict(label=COMPOSITES[c][0], id=c, items=len(COMPOSITES[c][1]), **desc(d[f"needs_{c}"])) for c in ORDER_COMPOSITES]
rel = []
for c in ORDER_COMPOSITES:
    items = d[[f"needs_quant_{k}" for k in COMPOSITES[c][1]]]
    a, rbar = cronbach(items)
    rel.append(dict(label=COMPOSITES[c][0], id=c, items=[DECISIONS[k][0] for k in COMPOSITES[c][1]], alpha=r2(a, 3), meanR=r2(rbar, 3)))
full["reliability"] = rel
R12, P12, N12 = corr_p(d[[f"needs_quant_{k}" for k in DECISIONS]])
full["decisionCorrelations"] = dict(labels=[DECISIONS[k][0] for k in DECISIONS], r=[[r2(v, 3) for v in row] for row in R12])

# ---------------------------------------------------------------- trust: descriptives for the doctor and the AI
trust_desc = []
for k in DECISIONS:
    trust_desc.append(dict(label=DECISIONS[k][0], id=k, doctor=desc(d[f"trust_doctor_{k}"]), ai=desc(d[f"trust_ai_{k}"])))
full["trustDescriptives"] = trust_desc
full["trustCompositeDescriptives"] = [dict(label=COMPOSITES[c][0], id=c, doctor=desc(d[f"trust_doctor_{c}"]), ai=desc(d[f"trust_ai_{c}"])) for c in ORDER_COMPOSITES]

# ---------------------------------------------------------------- H1: paired t tests, doctor minus AI
h1 = []
for k in DECISIONS:
    h1.append(paired(d[f"trust_doctor_{k}"], d[f"trust_ai_{k}"], label=DECISIONS[k][0], id=k,
                     needs=r2(d[f"needs_quant_{k}"].mean(), 2)))
full["tests"] = h1
full["compositeTests"] = [paired(d[f"trust_doctor_{c}"], d[f"trust_ai_{c}"], label=COMPOSITES[c][0], id=c) for c in ORDER_COMPOSITES]
full["overallTest"] = paired(d["trust_doctor_all"], d["trust_ai_all"], label="All twelve decisions", id="all")

# ---------------------------------------------------------------- how people saw the doctor and the AI (exploratory; not in the notebook)
qual = []
for key, label, scale in QUALITIES:
    qual.append(paired(d[f"{key}_doctor"], d[f"{key}_ai"], label=label, id=key, scale=scale, mind=key in MIND))
full["qualityTests"] = qual

# ---------------------------------------------------------------- H3: correlations among quantitative reasoning, intuition, competence and warmth
H3 = [("quantitative_reasoning", "Quantitative reasoning"), ("intuition", "Intuition"), ("competence", "Competence"), ("warmth", "Warmth")]
cors = []
for who, wl in (("doctor", "Doctor"), ("ai", "AI")):
    R, P, Nn = corr_p(d[[f"{k}_{who}" for k, _ in H3]])
    cors.append(dict(who=wl, vars=[v for _, v in H3], r=[[r2(v, 3) for v in row] for row in R], p=[[float(v) for v in row] for row in P],
                     n=[[int(v) for v in row] for row in Nn]))
full["correlationsByTarget"] = cors

# ---------------------------------------------------------------- long data: one row per person, decision and recommender
long = []
for i, r in d.iterrows():
    for who in ("doctor", "ai"):
        mind = np.nanmean([r[f"{m}_{who}"] for m in MIND])
        mind_alt = np.nanmean([r[f"{m}_{who}"] for m in MIND_ALT])
        for k in DECISIONS:
            long.append(dict(ID=i + 1, DM=who, IsDoc=float(who == "doctor"), Decision=k, Trust=r[f"trust_{who}_{k}"], Int_Quant=r[f"needs_quant_{k}"],
                             Intuition=r[f"intuition_{who}"], Quant=r[f"quantitative_reasoning_{who}"], Warmth=r[f"warmth_{who}"],
                             Competence=r[f"competence_{who}"], Mind=mind, MindAlt=mind_alt,
                             AgeGroup=["18-44", "45-59", "60-69", "70+"].index(r["age_group"]) + 1 if isinstance(r["age_group"], str) else np.nan,
                             IsMale=float(r["gender"] == "Man")))
L = pd.DataFrame(long)

# mind perception composite reliability, on one row per person and recommender
a7, r7 = cronbach(pd.concat(
    [d[[f"{m}_doctor" for m in MIND]].rename(columns=lambda c: c.replace("_doctor", "")),
     d[[f"{m}_ai" for m in MIND]].rename(columns=lambda c: c.replace("_ai", ""))], ignore_index=True))
a3, r3_ = cronbach(pd.concat([d[[f"{m}_doctor" for m in MIND_ALT]].rename(columns=lambda c: c.replace("_doctor", "")),
                              d[[f"{m}_ai" for m in MIND_ALT]].rename(columns=lambda c: c.replace("_ai", ""))], ignore_index=True))
full["mindReliability"] = [dict(label="Mind perception, seven items", k=7, alpha=r2(a7, 3), meanR=r2(r7, 3)),
                           dict(label="Alternative, three items (anticipate, account for, understand feelings)", k=3, alpha=r2(a3, 3), meanR=r2(r3_, 3))]


# ---------------------------------------------------------------- H3: within-person and between-person correlations
def wb(data, cols, names):
    means = data.groupby("ID")[cols].mean()
    within = data[cols] - data.groupby("ID")[cols].transform("mean")
    Rw = within.corr().values
    Rb = means.corr().values
    J = int(data.groupby("ID").ngroups)
    pb = np.zeros_like(Rb)
    pw = np.zeros_like(Rb)
    for i in range(len(cols)):
        for j in range(len(cols)):
            if i == j:
                continue
            tb = Rb[i, j] * np.sqrt((J - 2) / (1 - Rb[i, j] ** 2))
            pb[i, j] = 2 * stats.t.sf(abs(tb), J - 2)
            # a person contributes one independent difference (doctor minus AI), so the within test has J - 2 degrees of freedom
            tw = Rw[i, j] * np.sqrt((J - 2) / (1 - Rw[i, j] ** 2))
            pw[i, j] = 2 * stats.t.sf(abs(tw), J - 2)
    return dict(vars=names, people=J, between=[[r2(v, 3) for v in r] for r in Rb], pBetween=[[float(v) for v in r] for r in pb],
                within=[[r2(v, 3) for v in r] for r in Rw], pWithin=[[float(v) for v in r] for r in pw])


WB_COLS = ["Competence", "Quant", "Warmth", "Intuition", "Mind", "MindAlt"]
WB_NAMES = ["Competence", "Quantitative reasoning", "Warmth", "Intuition", "Mind perception", "Mind perception, three items"]
full["withinBetween"] = wb(L, WB_COLS, WB_NAMES)
full["withinBetweenNote"] = ("Within-person correlations ask whether, for one person, the target rated higher on one quality (the doctor or the AI) is also rated higher "
                             "on another. Between-person correlations use each person's average over the doctor and the AI. Within-person p values treat each person as one "
                             "doctor-minus-AI difference, so they use 104 degrees of freedom, not the thousands of rows the notebook's long file holds.")

# ---------------------------------------------------------------- mixed models
def fit_lmm(formula, data, re_formula=None, label=""):
    need = [t for t in data.columns if t in formula]
    D = data.dropna(subset=need + ["Trust"]).reset_index(drop=True)
    md = smf.mixedlm(formula, D, groups=D["ID"], re_formula=re_formula)
    res = md.fit(reml=True, method=["lbfgs", "powell"], maxiter=2000)
    ml = smf.mixedlm(formula, D, groups=D["ID"], re_formula=re_formula).fit(reml=False, method=["lbfgs", "powell"], maxiter=2000)
    X = md.exog
    fe = res.fe_params.values
    var_f = float(np.var(X @ fe))
    cov_re = res.cov_re.values
    if re_formula:
        z = np.column_stack([np.ones(len(D)), D["Int_Quant"].values])
        var_re = float(np.mean(np.einsum("ij,jk,ik->i", z, cov_re, z)))
    else:
        var_re = float(cov_re[0, 0])
    var_e = float(res.scale)
    tot = var_f + var_re + var_e
    names = list(res.fe_params.index)
    sdy = float(D["Trust"].std())
    terms = []
    for nm in names:
        b = float(res.fe_params[nm])
        se = float(res.bse_fe[nm])
        beta = None
        clean = nm.replace("[T.1.0]", "")
        if nm != "Intercept" and ":" not in nm and clean in D.columns:
            beta = b * float(D[clean].std()) / sdy
        terms.append(dict(term=clean, b=r2(b, 3), se=r2(se, 3), lo=r2(b - 1.96 * se, 3), hi=r2(b + 1.96 * se, 3), z=r2(b / se, 2),
                          p=float(2 * stats.norm.sf(abs(b / se))), beta=r2(beta, 3) if beta is not None else None))
    # variance inflation factors the way car::vif treats a mixed model: from the correlation of the fixed-effect estimates
    cov = res.cov_params().loc[names, names].values
    keep = [i for i, nm in enumerate(names) if nm != "Intercept"]
    cc = cov[np.ix_(keep, keep)]
    Rm = cc / np.sqrt(np.outer(np.diag(cc), np.diag(cc)))
    vif = {names[keep[i]]: float(Rm[i, i] * np.linalg.inv(Rm)[i, i]) for i in range(len(keep))}
    k = len(names) + (3 if re_formula else 1) + 1
    for t in terms:
        t["vif"] = r2(vif.get(t["term"] if t["term"] in vif else t["term"], None) if t["term"] in vif else None, 2)
    ll = float(ml.llf)
    return dict(label=label, formula=formula, randomEffects=("(1 + Int_Quant | person)" if re_formula else "(1 | person)"), n=int(len(D)),
                people=int(D["ID"].nunique()), terms=terms, varPerson=r2(cov_re[0, 0], 3), varSlope=r2(cov_re[1, 1], 5) if re_formula else None,
                corPersonSlope=r2(cov_re[0, 1] / np.sqrt(cov_re[0, 0] * cov_re[1, 1]), 2) if re_formula and cov_re[1, 1] > 0 else None,
                varResidual=r2(var_e, 3), icc=r2(var_re / (var_re + var_e), 3), r2m=r2(var_f / tot, 3), r2c=r2((var_f + var_re) / tot, 3),
                converged=bool(res.converged), k=k, aic=r2(-2 * ll + 2 * k, 1) if np.isfinite(ll) else None, bic=r2(-2 * ll + np.log(len(D)) * k, 1) if np.isfinite(ll) else None)


L["DM"] = L["DM"].map({"doctor": "Doctor", "ai": "AI"})
RE = "~Int_Quant"
models = [
    fit_lmm("Trust ~ IsDoc", L, None, "Doctor versus AI only"),
    fit_lmm("Trust ~ IsDoc * Int_Quant", L, RE, "Does the gap depend on how much quantitative reasoning a decision needs (H2)"),
    fit_lmm("Trust ~ IsDoc * Int_Quant + Intuition + Quant + Warmth + Competence + AgeGroup + IsMale", L, RE,
            "Add intuition, quantitative reasoning, warmth, competence, age group and gender"),
    fit_lmm("Trust ~ IsDoc * Int_Quant + Intuition + Quant + Mind + AgeGroup + IsMale", L, RE,
            "Mind perception in place of warmth and competence"),
    fit_lmm("Trust ~ IsDoc * Int_Quant + AgeGroup + IsMale + Intuition + Quant", L, RE,
            "Intuition and quantitative reasoning only"),
    fit_lmm("Trust ~ IsDoc + AgeGroup + IsMale + Intuition * Int_Quant + Quant * Int_Quant", L, RE,
            "Intuition and quantitative reasoning each interact with the decision"),
    fit_lmm("Trust ~ AgeGroup * IsDoc + IsMale + Int_Quant + Intuition + Quant + Warmth + Competence", L, RE,
            "Age group by doctor interaction"),
]
full["mixedModels"] = models
full["mixedNote"] = ("Random intercept for each person, plus a random slope for how much quantitative reasoning the decision needs in every model but the first; "
                     "restricted maximum likelihood; Wald z tests. R squared is Nakagawa's marginal and conditional version, and the person share is the person variance "
                     "over person plus residual variance. Standardized betas are b times the SD of the predictor over the SD of trust. AIC refits by maximum likelihood. "
                     "Age enters as the age group number (1 = 18 to 44, 4 = 70 and over) because the public file does not hold age in years. The notebook's other "
                     "attempts are not reproduced: one used a person's own average as its outcome and predictor and the notebook records that it was singular.")
full["decisionBetas"] = None

# ---------------------------------------------------------------- mediation (H4)
MED = L.dropna(subset=["Trust", "Quant", "Intuition", "Warmth", "Competence", "IsDoc", "Int_Quant"]).reset_index(drop=True)


def centered(data, cols):
    return data[cols] - data.groupby("ID")[cols].transform("mean")


def paths(data, mediators):
    """Within-person paths: each mediator on doctor-versus-AI (a), trust on the mediators and doctor-versus-AI together (b, direct)."""
    C = centered(data, ["Trust", "IsDoc"] + mediators)
    x = C["IsDoc"].values
    a = {m: float(x @ C[m].values / (x @ x)) for m in mediators}
    Z = C[mediators + ["IsDoc"]].values
    coef = np.linalg.lstsq(Z, C["Trust"].values, rcond=None)[0]
    b = dict(zip(mediators, coef[:-1]))
    total = float(x @ C["Trust"].values / (x @ x))
    return a, b, float(coef[-1]), total


def mediation(mediators, label):
    a, b, direct, total = paths(MED, mediators)
    C = centered(MED, ["Trust", "IsDoc"] + mediators)
    # cluster-robust standard errors for the paths, then the delta method for a times b
    cl = MED["ID"]
    wfit = smf.ols("Trust ~ " + " + ".join(mediators) + " + IsDoc - 1", C).fit(cov_type="cluster", cov_kwds={"groups": cl})
    afit = {m: smf.ols(f"{m} ~ IsDoc - 1", C).fit(cov_type="cluster", cov_kwds={"groups": cl}) for m in mediators}
    ids = MED["ID"].unique()
    groups = {i: MED[MED["ID"] == i] for i in ids}
    boots = []
    for _ in range(2000):
        pick = rng.choice(ids, size=len(ids), replace=True)
        bd = pd.concat([groups[i].assign(ID=j) for j, i in enumerate(pick)], ignore_index=True)
        try:
            ab, bb, db, tb = paths(bd, mediators)
            boots.append([ab[m] * bb[m] for m in mediators] + [db, tb])
        except np.linalg.LinAlgError:
            pass
    boots = np.array(boots)
    rows = []
    for i, m in enumerate(mediators):
        ind = a[m] * b[m]
        se = float(np.sqrt(a[m] ** 2 * wfit.bse[m] ** 2 + b[m] ** 2 * afit[m].bse["IsDoc"] ** 2))
        rows.append(dict(mediator=m, a=r2(a[m], 3), aSE=r2(float(afit[m].bse["IsDoc"]), 3), b=r2(b[m], 3), bSE=r2(float(wfit.bse[m]), 3),
                         indirect=r2(ind, 3), lo=r2(np.percentile(boots[:, i], 2.5), 3), hi=r2(np.percentile(boots[:, i], 97.5), 3),
                         z=r2(ind / se, 2), p=float(2 * stats.norm.sf(abs(ind / se)))))
    return dict(label=label, n=int(len(MED)), people=int(MED["ID"].nunique()), mediators=rows, direct=r2(direct, 3),
                directLo=r2(np.percentile(boots[:, -2], 2.5), 3), directHi=r2(np.percentile(boots[:, -2], 97.5), 3), total=r2(total, 3))


MEDNAMES = {"Warmth": "Warmth", "Competence": "Competence", "Intuition": "Intuition", "Quant": "Quantitative reasoning"}
meds = [mediation(["Warmth", "Competence"], "Warmth and competence together"),
        mediation(["Intuition", "Quant"], "Intuition and quantitative reasoning together"),
        mediation(["Warmth"], "Warmth alone"), mediation(["Competence"], "Competence alone"),
        mediation(["Intuition"], "Intuition alone"), mediation(["Quant"], "Quantitative reasoning alone")]
for m in meds:
    for r in m["mediators"]:
        r["name"] = MEDNAMES[r["mediator"]]
full["mediation"] = meds
full["mediationNote"] = ("Paths are within-person: every variable is taken as a distance from that person's own average, so the doctor-versus-AI contrast is "
                         "a within-person effect. a is the effect of the doctor (versus the AI) on the mediator, b the effect of the mediator on trust with the "
                         "doctor contrast held fixed, and the indirect effect is a times b. Intervals come from resampling people 2,000 times. z is the delta-method "
                         "ratio with standard errors that allow for several ratings per person. The notebook ran these as Mplus two-level models; the "
                         "indirect effects here reproduce its estimates, and its test statistics are close but not identical.")

# ---------------------------------------------------------------- does the gap differ between groups of people?
VARS = [("age_group", "Age"), ("gender", "Gender"), ("education", "Education"), ("religiosity", "How religious"), ("ai_experience", "Experience with AI")]
ORDER = {"age_group": ["18-44", "45-59", "60-69", "70+"], "gender": ["Woman", "Man"], "education": ["No college degree", "College degree or more"],
         "religiosity": ["Not at all to slightly", "Moderately", "More than moderately"], "ai_experience": ["None or a little", "Moderate or more"]}
MIN_N = 10
subs = []
gap = {"trust": d["trust_doctor_all"] - d["trust_ai_all"], "quant": d["quantitative_reasoning_doctor"] - d["quantitative_reasoning_ai"],
       "intuition": d["intuition_doctor"] - d["intuition_ai"]}
for col, name in VARS:
    groups, samples = [], {k: [] for k in gap}
    for lv in ORDER[col]:
        idx = d[col] == lv
        if idx.sum() < MIN_N:
            continue
        cells = []
        for k, g in gap.items():
            x = g[idx].dropna()
            if len(x) < MIN_N:
                cells.append(None)
                continue
            lo, hi = t_ci(x)
            cells.append(dict(mean=r2(x.mean()), lo=r2(lo), hi=r2(hi), n=int(len(x))))
            samples[k].append(x.values)
        groups.append(dict(label=lv, n=int(idx.sum()), cells=cells))
    tests = []
    for k in gap:
        arr = samples[k]
        if len(arr) == 2:
            t, p = stats.ttest_ind(arr[0], arr[1])
            tests.append(dict(stat="t", value=r2(t), df=int(len(arr[0]) + len(arr[1]) - 2), p=float(p)))
        elif len(arr) > 2:
            F, p = stats.f_oneway(*arr)
            tests.append(dict(stat="F", value=r2(F), df=[len(arr) - 1, int(sum(len(a) for a in arr) - len(arr))], p=float(p)))
        else:
            tests.append(None)
    subs.append(dict(variable=name, groups=groups, tests=tests))
full["subgroups"] = subs
full["subgroupNote"] = ("Each dot is the average gap (doctor minus AI) for the people in that group, with its 95% confidence interval. Groups under 10 people are not shown, "
                        "and race is not shown because only one group has 30 or more people. The tests ask whether the gap differs between the groups shown; they are "
                        "exploratory and not corrected for the 15 comparisons.")

# ---------------------------------------------------------------- decision-level link between the need for quantitative reasoning and the gap (H2, descriptive)
dl = [(DECISIONS[k][0], float(d[f"needs_quant_{k}"].mean()), h["diff"], h["lo"], h["hi"], k) for k, h in zip(DECISIONS, h1)]
x = np.array([p[1] for p in dl])
y = np.array([p[2] for p in dl])
lin = stats.linregress(x, y)
full["gapByNeed"] = dict(points=[dict(label=p[0], x=r2(p[1]), y=r2(p[2]), lo=r2(p[3]), hi=r2(p[4]), id=p[5]) for p in dl],
                         slope=r2(lin.slope, 4), intercept=r2(lin.intercept, 3), r=r2(lin.rvalue, 3), p=float(lin.pvalue), n=len(dl))

json.dump(full, open(OUT + "study2-full.json", "w"))

# ---------------------------------------------------------------- figures: per-person points, bootstrapped intervals, densities
points = {"participants": [str(p) for p in d["participant"]]}
grid100 = np.linspace(0, 100, 51)
grid10 = np.linspace(0, 10, 51)


def series(label, key, values, grid, extra=None):
    v = pd.Series(values)
    lo, hi = boot_ci(v)
    dn = density(v, grid)
    dn = dn / dn.max()
    out = dict(id=key, label=label, n=int(v.notna().sum()), mean=r2(v.mean()), lo=r2(lo), hi=r2(hi),
               values=[None if pd.isna(a) else r2(a, 1) for a in v], density=[r2(a, 3) for a in dn])
    if extra:
        out.update(extra)
    return out


points["decisions"] = [series(DECISIONS[k][0], k, d[f"needs_quant_{k}"], grid100, dict(stage=DECISIONS[k][1])) for k in DECISIONS]
points["composites"] = [series(COMPOSITES[c][0], c, d[f"needs_{c}"], grid100) for c in ORDER_COMPOSITES]
points["domainOrder"] = ["q_acute", "q_chronic", "q_injury", "q_mental", "q_physical"]
points["stageOrder"] = ["q_diagnosis", "q_prescription", "q_preventative"]
points["trustOverall"] = [series("Doctor, average of twelve decisions", "doctor_all", d["trust_doctor_all"], grid10, dict(kind="human")),
                          series("AI, average of twelve decisions", "ai_all", d["trust_ai_all"], grid10, dict(kind="ai"))]
points["qualityClouds"] = []
for key, label, scale in QUALITIES[:4]:
    top = 4 if scale == "0 to 4" else 10
    g = np.linspace(0, top, 51)
    points["qualityClouds"].append(dict(key=key, label=label, top=top, rows=[
        series("Doctor", f"{key}_doctor", d[f"{key}_doctor"], g, dict(kind="human")),
        series("AI", f"{key}_ai", d[f"{key}_ai"], g, dict(kind="ai"))]))
points["densityGrid100"] = [float(v) for v in grid100]
points["densityGrid10"] = [float(v) for v in grid10]
json.dump(points, open(OUT + "study2-points.json", "w"))
print("wrote study2-full.json and study2-points.json")
