"""
Compute every Study 1 table and figure the notebook produced, from the released file.

Reads   public/data/study1-ratings.csv and src/data/trust-in-medical-ai/study1-test-defs.json
Writes  src/data/trust-in-medical-ai/study1-full.json    tables and model results
        src/data/trust-in-medical-ai/study1-points.json  per-person values for the jittered plots

Needs: pandas, numpy, scipy, statsmodels, factor_analyzer.  Run from the repository root.

Where the notebook (public/code/study1-original-analysis.Rmd) used an R package, this uses the
closest Python equivalent and says so in the "method" notes inside the JSON:
  psych::describe        skew and kurtosis are the type 3 estimates
  psych::alpha           raw alpha from pairwise covariances
  psych::fa              minimum residual extraction, oblimin rotation (the notebook's minchi
                         method gives the same answer when every correlation uses the same n)
  lme4::lmer             a random-intercept model fitted by restricted maximum likelihood (written out in lmm() below)
  MuMIn::r.squaredGLMM   Nakagawa marginal and conditional R squared
Run study1-analysis.R in R to compare the two sets of numbers.
"""
import json
import numpy as np
import pandas as pd
from scipy import stats, optimize
import statsmodels.formula.api as smf
from factor_analyzer import FactorAnalyzer
import factor_analyzer.factor_analyzer as _fa

# factor_analyzer still passes an argument that current scikit-learn renamed; translate it.
_orig_check = _fa.check_array
_fa.check_array = lambda *a, force_all_finite=None, **k: _orig_check(
    *a, **({"ensure_all_finite": force_all_finite} if force_all_finite is not None else {}), **k)

OUT = "src/data/trust-in-medical-ai/"
d = pd.read_csv("public/data/study1-ratings.csv")
DEFS = json.load(open(OUT + "study1-test-defs.json"))
rng = np.random.default_rng(2023)

# ---------------------------------------------------------------- names
DECISION_LABEL = {
    "prevent_injury_stretching": "Recommend stretching",
    "diagnose_broken_bone": "Diagnose a broken bone",
    "prescribe_knee_surgery": "Recommend knee surgery",
    "prescribe_pain_medication": "Prescribe pain medication",
    "prevent_mental_meditation": "Recommend meditation",
    "diagnose_depression": "Diagnose depression",
    "prescribe_mental_therapy": "Prescribe antidepressants and therapy",
    "prevent_acute_vitamins": "Recommend vitamin C and zinc",
    "diagnose_strep_throat": "Diagnose strep throat",
    "prescribe_antibiotics": "Prescribe antibiotics",
    "prevent_chronic_diet": "Recommend a strict diet",
    "diagnose_diabetes": "Diagnose diabetes",
    "prescribe_insulin": "Prescribe insulin and a diet change",
    "prevent_wellbeing": "Recommend general wellbeing habits",
    "medical_general": "Medical decisions in general",
}
STAGE = {}
for k in DECISION_LABEL:
    STAGE[k] = k.split("_")[0]
COMPOSITES = DEFS["composites"]
COMPOSITES["q_chronic"] = ["diagnose_diabetes", "prevent_chronic_diet", "prescribe_insulin"]
COMPOSITE_LABEL = {
    "q_diagnosis": "Diagnostic", "q_prescription": "Prescriptive", "q_preventative": "Preventative",
    "q_physical": "Physical health", "q_mental": "Mental health", "q_injury": "Bodily injury",
    "q_acute": "Acute sickness", "q_chronic": "Chronic sickness",
}
for name, cols in COMPOSITES.items():
    d[name] = d[cols].mean(axis=1, skipna=False)  # missing if any item is missing, as in the notebook

MAKER = {"doctor": "Doctor", "nurse": "Nurse", "doctor_remote": "Doctor, remote visit", "therapist": "Therapist",
         "personal_trainer": "Personal trainer", "layperson": "Layperson", "doctor_using_ai": "Doctor using AI",
         "ai_general": "AI, general", "ai_diagnostic": "AI diagnostic tool", "ai_chatbot": "AI chatbot",
         "ai_fitness": "AI fitness coach"}
IS_AI = {k: int(k.startswith("ai_") or k == "doctor_using_ai") for k in MAKER}  # the notebook counts a doctor using AI as AI
MEASURES = [("trust", "Trust"), ("capability", "Quantitative reasoning"), ("intuition", "Intuition")]


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
    skew = g1 * ((n - 1) / n) ** 1.5          # psych type 3
    kurt = (g2 + 3) * ((n - 1) / n) ** 2 - 3  # psych type 3
    return dict(n=n, mean=r2(x.mean()), sd=r2(s), median=r2(x.median()), min=r2(x.min()), max=r2(x.max()),
                skew=r2(skew), kurtosis=r2(kurt), se=r2(s / np.sqrt(n)))


def boot_ci(x, B=2000):
    x = np.asarray(pd.Series(x).dropna(), float)
    means = rng.choice(x, size=(B, len(x)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def p_fmt(p):
    return float(p)


def cronbach(df):
    c = df.cov()  # pairwise complete, as psych::alpha does
    k = df.shape[1]
    raw = k / (k - 1) * (1 - np.trace(c.values) / c.values.sum())
    r = df.corr()
    rbar = (r.values.sum() - k) / (k * (k - 1))
    std = k * rbar / (1 + (k - 1) * rbar)
    return float(raw), float(std), float(rbar)


def corr_p(df):
    cols = list(df.columns)
    R = np.zeros((len(cols), len(cols)))
    P = np.zeros_like(R)
    N = np.zeros_like(R)
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            x = df[[a, b]].dropna()
            r, p = stats.pearsonr(x[a], x[b]) if i != j else (1.0, 0.0)
            R[i, j], P[i, j], N[i, j] = r, p, len(x)
    return R, P, N


def d_ci(dz, n, level=0.95):
    """Confidence interval for a paired Cohen's d by inverting the noncentral t, as the effectsize package does."""
    t = dz * np.sqrt(n)
    df = n - 1
    a = (1 - level) / 2

    def f(nc, q):
        return stats.nct.cdf(t, df, nc) - q
    w = 4 * np.sqrt(1 + t ** 2 / (2 * df))  # the noncentral t function returns NaN for very large noncentrality, so stay close to t
    lo = optimize.brentq(f, t - w, t + w, args=(1 - a,))
    hi = optimize.brentq(f, t - w, t + w, args=(a,))
    return lo / np.sqrt(n), hi / np.sqrt(n)


def paired(a, b):
    x = d[[a, b]].dropna()
    diff = x[a] - x[b]
    n = len(x)
    t, p = stats.ttest_rel(x[a], x[b])
    h = stats.t.ppf(0.975, n - 1) * diff.std(ddof=1) / np.sqrt(n)
    dz = diff.mean() / diff.std(ddof=1)
    lo, hi = d_ci(dz, n)
    pos = int((diff > 0).sum())
    zero = int((diff == 0).sum())
    neg = int((diff < 0).sum())
    return dict(n=n, meanA=r2(x[a].mean()), meanB=r2(x[b].mean()), sdA=r2(x[a].std()), sdB=r2(x[b].std()),
                diff=r2(diff.mean()), lo=r2(diff.mean() - h), hi=r2(diff.mean() + h), t=r2(t), df=n - 1,
                p=p_fmt(p), d=r2(dz), dLo=r2(lo), dHi=r2(hi),
                dir=dict(higher=pos, same=zero, lower=neg))


full = {"method": {}}
full["method"]["descriptives"] = "Skew and kurtosis are the type 3 estimates that psych::describe reports. SE is the standard error of the mean."
full["method"]["reliability"] = "Cronbach's alpha from pairwise covariances, as psych::alpha reports as raw alpha."

# ---------------------------------------------------------------- sample
sample = []
for col, label in [("age_group", "Age"), ("gender", "Gender"), ("race", "Race"), ("education", "Education"),
                   ("politics", "Political views"), ("ai_experience", "Experience with AI")]:
    vc = d[col].value_counts(dropna=True)
    rows = [dict(group=str(g), n=int(n), pct=r2(100 * n / len(d), 1)) for g, n in vc.items()]
    miss = int(d[col].isna().sum())
    sample.append(dict(variable=label, rows=rows, missing=miss))
full["sample"] = dict(n=int(len(d)), variables=sample)

# ---------------------------------------------------------------- decision descriptives
dec = []
for k, label in DECISION_LABEL.items():
    row = dict(id=k, label=label, stage=STAGE[k])
    row.update(desc(d[k]))
    dec.append(row)
full["decisionDescriptives"] = dec
comp = []
for k, label in COMPOSITE_LABEL.items():
    row = dict(id=k, label=label, items=len(COMPOSITES[k]))
    row.update(desc(d[k]))
    comp.append(row)
full["compositeDescriptives"] = comp

# ---------------------------------------------------------------- reliability
REL = [
    ("Diagnostic decisions", COMPOSITES["q_diagnosis"]),
    ("Prescriptive decisions", COMPOSITES["q_prescription"]),
    ("Preventative decisions", COMPOSITES["q_preventative"]),
    ("Physical health decisions", COMPOSITES["q_physical"]),
    ("Mental health decisions", COMPOSITES["q_mental"]),
    ("Bodily injury decisions", COMPOSITES["q_injury"]),
    ("Acute sickness decisions", COMPOSITES["q_acute"]),
    ("Chronic sickness decisions", COMPOSITES["q_chronic"]),
]
rel = []
for label, cols in REL:
    df = d[cols]
    raw, std, rbar = cronbach(df)
    R, P, N = corr_p(df)
    rel.append(dict(label=label, items=[DECISION_LABEL[c] for c in cols], alpha=r2(raw, 3), alphaStd=r2(std, 3),
                    meanR=r2(rbar, 3), r=[[r2(v, 3) for v in row] for row in R], p=[[float(v) for v in row] for row in P]))
full["reliability"] = rel

# ---------------------------------------------------------------- factor analysis of the 12 composite items
EFA_ITEMS = ["diagnose_broken_bone", "diagnose_strep_throat", "diagnose_diabetes", "prevent_injury_stretching",
             "prevent_acute_vitamins", "prevent_chronic_diet", "prescribe_pain_medication", "prescribe_antibiotics",
             "prescribe_insulin", "diagnose_depression", "prevent_mental_meditation", "prescribe_mental_therapy"]
E = d[EFA_ITEMS].dropna()
C = E.corr().values
eig = np.sort(np.linalg.eigvalsh(C))[::-1]
fa = FactorAnalyzer(n_factors=3, rotation="oblimin", method="minres", is_corr_matrix=True)
fa.fit(C)
load = fa.loadings_
phi = fa.phi_ if hasattr(fa, "phi_") and fa.phi_ is not None else np.eye(3)
comm = fa.get_communalities()
# order factors by the variance they carry, then flip signs so the biggest loading is positive
ss = (load ** 2).sum(axis=0)
order = np.argsort(-ss)
load = load[:, order]
phi = phi[np.ix_(order, order)]
for j in range(3):
    if load[np.abs(load[:, j]).argmax(), j] < 0:
        load[:, j] *= -1
        phi[j, :] *= -1
        phi[:, j] *= -1
full["efa"] = dict(
    n=int(len(E)),
    eigenvalues=[r2(v, 3) for v in eig],
    items=[DECISION_LABEL[c] for c in EFA_ITEMS],
    stage=[STAGE[c] for c in EFA_ITEMS],
    loadings=[[r2(v, 3) for v in row] for row in load],
    communalities=[r2(v, 3) for v in comm],
    factorCorrelations=[[r2(v, 3) for v in row] for row in phi],
    variance=[r2(v / len(EFA_ITEMS), 3) for v in (load ** 2).sum(axis=0)],
    note="Three factors, minimum residual extraction and oblimin rotation, on the 12 decisions that form the composites "
         "(everyone with all 12 answers). The notebook asked for minchi extraction, which gives the same answer when every "
         "correlation rests on the same number of people. Loadings are the pattern matrix.",
)

# ---------------------------------------------------------------- decision makers
mk = []
for k, label in MAKER.items():
    row = dict(id=k, label=label, ai=IS_AI[k])
    for m, _ in MEASURES:
        row[m] = desc(d[f"{m}_{k}"])
    mk.append(row)
mk.sort(key=lambda r: -r["trust"]["mean"])
full["makerDescriptives"] = mk

# ---------------------------------------------------------------- tests
tests = []
for t in DEFS["tests"]:
    r = paired(t["a"], t["b"])
    tests.append({**{k: t[k] for k in ("id", "text", "aLabel", "bLabel", "scale", "preregistered")}, **r})
full["tests"] = tests

extra = [
    ("X1", "Trust: layperson versus AI", "trust_layperson", "trust_ai_general", "Layperson", "AI", "0 to 10"),
    ("X2", "Intuition: layperson versus AI", "intuition_layperson", "intuition_ai_general", "Layperson", "AI", "0 to 10"),
    ("X3", "AI: quantitative reasoning versus intuition", "capability_ai_general", "intuition_ai_general", "Quantitative reasoning", "Intuition", "0 to 10"),
    ("X4", "Trust: doctor versus doctor using AI", "trust_doctor", "trust_doctor_using_ai", "Doctor", "Doctor using AI", "0 to 10"),
]
ex = []
for i, text, a, b, la, lb, sc in extra:
    ex.append(dict(id=i, text=text, aLabel=la, bLabel=lb, scale=sc, **paired(a, b)))
full["extraTests"] = ex

# ---------------------------------------------------------------- regressions and correlations within a decision maker
reg, cor = [], []
for k in ("doctor", "ai_general", "layperson"):
    x = d[[f"trust_{k}", f"capability_{k}", f"intuition_{k}"]].dropna()
    x.columns = ["trust", "qr", "intuition"]
    m = smf.ols("trust ~ intuition + qr", data=x).fit()
    z = (x - x.mean()) / x.std()
    mz = smf.ols("trust ~ intuition + qr", data=z).fit()
    terms = []
    for term, label in [("Intercept", "Intercept"), ("intuition", "Intuition"), ("qr", "Quantitative reasoning")]:
        terms.append(dict(term=label, b=r2(m.params[term], 3), se=r2(m.bse[term], 3), t=r2(m.tvalues[term], 2),
                          p=float(m.pvalues[term]), beta=None if term == "Intercept" else r2(mz.params[term], 3)))
    reg.append(dict(maker=MAKER[k], n=int(len(x)), r2=r2(m.rsquared, 3), adjR2=r2(m.rsquared_adj, 3),
                    F=r2(m.fvalue, 2), df1=int(m.df_model), df2=int(m.df_resid), p=float(m.f_pvalue), terms=terms))
    R, P, N = corr_p(x[["trust", "qr", "intuition"]])
    cor.append(dict(maker=MAKER[k], n=int(len(x)), vars=["Trust", "Quantitative reasoning", "Intuition"],
                    r=[[r2(v, 3) for v in row] for row in R], p=[[float(v) for v in row] for row in P]))
full["regressions"] = reg
full["correlationsByMaker"] = cor

# ---------------------------------------------------------------- long data and mixed models
long = []
for i, r in d.iterrows():
    for k in MAKER:
        long.append(dict(ID=r["participant"], maker=k, IsAI=IS_AI[k], Trust=r[f"trust_{k}"],
                         QR=r[f"capability_{k}"], Int=r[f"intuition_{k}"]))
L = pd.DataFrame(long).dropna().reset_index(drop=True)
g = L.groupby("ID")
L["QR_PM"], L["Int_PM"] = g["QR"].transform("mean"), g["Int"].transform("mean")
L["QR_PMC"], L["Int_PMC"] = L["QR"] - L["QR_PM"], L["Int"] - L["Int_PM"]

import patsy


def lmm(formula, data, reml=True):
    """Linear mixed model with one random intercept per person, fitted by (restricted) maximum likelihood.

    Written out directly rather than with a package because a person's random intercept can shrink to zero here,
    which makes the general-purpose fitters stop with a singular matrix. lme4 reports that case as a singular fit
    and carries on; this does the same."""
    y, X = patsy.dmatrices(formula, data, return_type="dataframe")
    names = list(X.columns)
    y = y.values.ravel()
    Xv = X.values
    ids = data["ID"].values
    groups = [np.where(ids == g)[0] for g in pd.unique(ids)]
    p = Xv.shape[1]
    N = len(y)

    def pieces(tau, sig):
        xx = np.zeros((p, p)); xy = np.zeros(p); yy = 0.0; logdet = 0.0
        for ix in groups:
            n = len(ix)
            c = tau / (sig + n * tau)
            xs, ys = Xv[ix].sum(axis=0), y[ix].sum()
            xx += (Xv[ix].T @ Xv[ix] - c * np.outer(xs, xs)) / sig
            xy += (Xv[ix].T @ y[ix] - c * xs * ys) / sig
            yy += ((y[ix] @ y[ix]) - c * ys * ys) / sig
            logdet += (n - 1) * np.log(sig) + np.log(sig + n * tau)
        return xx, xy, yy, logdet

    def negll(theta, restricted):
        tau, sig = np.exp(theta[0]) if theta[0] > -30 else 0.0, np.exp(theta[1])
        xx, xy, yy, logdet = pieces(tau, sig)
        beta = np.linalg.solve(xx, xy)
        quad = yy - xy @ beta
        ll = -0.5 * (logdet + quad + N * np.log(2 * np.pi))
        if restricted:
            ll += -0.5 * np.linalg.slogdet(xx)[1] + 0.5 * p * np.log(2 * np.pi)
        return -ll

    start = np.log([max(np.var(y) / 3, 1e-3), max(np.var(y) / 2, 1e-3)])
    best = None
    for t0 in (start, start + [-3, 0], [-30, start[1]]):
        r = optimize.minimize(negll, t0, args=(reml,), method="Nelder-Mead", options=dict(xatol=1e-8, fatol=1e-10, maxiter=4000))
        if best is None or r.fun < best.fun:
            best = r
    tau = float(np.exp(best.x[0])) if best.x[0] > -30 else 0.0
    sig = float(np.exp(best.x[1]))
    xx, xy, yy, logdet = pieces(tau, sig)
    beta = np.linalg.solve(xx, xy)
    cov = np.linalg.inv(xx)
    return dict(names=names, beta=beta, cov=cov, tau=tau, sig=sig, X=Xv, loglik=-best.fun, nobs=N)



def fit_mixed(formula, data=L, label=""):
    res = lmm(formula, data, reml=True)
    ml = lmm(formula, data, reml=False)
    names, b_all, cov = res["names"], res["beta"], res["cov"]
    fixed_var = float(np.var(res["X"] @ b_all))
    var_u, var_e = res["tau"], res["sig"]
    r2m = fixed_var / (fixed_var + var_u + var_e)
    r2c = (fixed_var + var_u) / (fixed_var + var_u + var_e)
    sdy = float(data["Trust"].std())
    terms = []
    for idx, nm in enumerate(names):
        se = float(np.sqrt(cov[idx, idx]))
        b = float(b_all[idx])
        beta = None
        if nm != "Intercept" and ":" not in nm:
            beta = b * float(data[nm].std()) / sdy
        terms.append(dict(term=nm, b=r2(b, 3), se=r2(se, 3), lo=r2(b - 1.96 * se, 3), hi=r2(b + 1.96 * se, 3),
                          z=r2(b / se, 2), p=float(2 * stats.norm.sf(abs(b / se))), beta=r2(beta, 3) if beta is not None else None))
    k = len(names) + 2
    return dict(label=label, formula=formula, n=int(len(data)), people=int(data["ID"].nunique()), terms=terms,
                varPerson=r2(var_u, 3), varResidual=r2(var_e, 3), icc=r2(var_u / (var_u + var_e), 3),
                r2m=r2(r2m, 3), r2c=r2(r2c, 3), llml=float(ml["loglik"]), k=k,
                aic=r2(-2 * ml["loglik"] + 2 * k, 1), bic=r2(-2 * ml["loglik"] + np.log(len(data)) * k, 1))


models = [
    fit_mixed("Trust ~ IsAI", label="AI versus human only"),
    fit_mixed("Trust ~ QR + Int", label="Quantitative reasoning and intuition"),
    fit_mixed("Trust ~ QR + Int + IsAI", label="Add AI versus human"),
    fit_mixed("Trust ~ QR * IsAI + Int * IsAI", label="Let the slopes differ for AI"),
    fit_mixed("Trust ~ QR_PM + QR_PMC + Int_PM + Int_PMC", label="Between and within people"),
    fit_mixed("Trust ~ QR_PM + QR_PMC + Int_PM + Int_PMC + IsAI", label="Between and within people, plus AI"),
    fit_mixed("Trust ~ QR + Int", data=L[L.IsAI == 1].reset_index(drop=True), label="AI recommenders only"),
    fit_mixed("Trust ~ QR + Int", data=L[L.IsAI == 0].reset_index(drop=True), label="Human recommenders only"),
]
full["mixedModels"] = models


def lrt(a, b):
    chi = 2 * (b["llml"] - a["llml"])
    df = b["k"] - a["k"]
    return dict(from_=a["label"], to=b["label"], chi2=r2(chi, 2), df=int(df), p=float(stats.chi2.sf(chi, df)))


full["modelComparisons"] = [lrt(models[1], models[2]), lrt(models[2], models[3]), lrt(models[4], models[5])]
full["mixedNote"] = ("Random intercept for each person, restricted maximum likelihood, 188 people with 11 ratings each. Tests are Wald z tests. "
                     "Standardized betas are b times the SD of the predictor over the SD of trust. Model comparisons refit by maximum likelihood. "
                     "The notebook's last model (3D) uses grand-mean variables the notebook never creates, so it is not reproduced here. "
                     "A doctor using AI counts as AI, as in the notebook.")

# slopes figure: predicted trust over 0 to 10 for the AI-only and human-only models, other predictor held at its mean
slopes = []
for lab, data in (("AI", L[L.IsAI == 1].reset_index(drop=True)), ("Human", L[L.IsAI == 0].reset_index(drop=True))):
    res = lmm("Trust ~ QR + Int", data, reml=True)
    cov, b = res["cov"], res["beta"]
    mq, mi = data["QR"].mean(), data["Int"].mean()
    for pred in ("QR", "Int"):
        pts = []
        for xv in np.linspace(0, 10, 21):
            v = np.array([1.0, xv if pred == "QR" else mq, xv if pred == "Int" else mi])
            fit = float(v @ b)
            se = float(np.sqrt(v @ cov @ v))
            pts.append([r2(xv, 1), r2(fit, 3), r2(fit - 1.96 * se, 3), r2(fit + 1.96 * se, 3)])
        slopes.append(dict(group=lab, predictor="Quantitative reasoning" if pred == "QR" else "Intuition",
                           slope=r2(b[1] if pred == "QR" else b[2], 3), points=pts))
full["slopes"] = dict(lines=slopes, note="Predicted trust from the AI-only and human-only models, with the other rating held at its average. Bands are 95% confidence intervals for the fixed effects.")

# ---------------------------------------------------------------- within and between person correlations
def wb(data):
    cols = ["Trust", "Int", "QR"]
    names = ["Trust", "Intuition", "Quantitative reasoning"]
    means = data.groupby("ID")[cols].mean()
    within = data[cols] - data.groupby("ID")[cols].transform("mean")
    J, N = means.shape[0], len(data)
    rb = means.corr().values
    rw = within.corr().values
    pb = np.zeros((3, 3))
    pw = np.zeros((3, 3))
    for i in range(3):
        for j in range(3):
            if i == j:
                continue
            tb = rb[i, j] * np.sqrt((J - 2) / (1 - rb[i, j] ** 2))
            pb[i, j] = 2 * stats.t.sf(abs(tb), J - 2)
            dfw = N - J - 1
            tw = rw[i, j] * np.sqrt(dfw / (1 - rw[i, j] ** 2))
            pw[i, j] = 2 * stats.t.sf(abs(tw), dfw)
    return dict(vars=names, people=int(J), ratings=int(N), between=[[r2(v, 3) for v in r] for r in rb],
                pBetween=[[float(v) for v in r] for r in pb], within=[[r2(v, 3) for v in r] for r in rw],
                pWithin=[[float(v) for v in r] for r in pw])


full["withinBetween"] = [dict(label="All recommenders", **wb(L)),
                         dict(label="AI recommenders", **wb(L[L.IsAI == 1])),
                         dict(label="Human recommenders", **wb(L[L.IsAI == 0]))]
full["withinBetweenNote"] = ("Between-person correlations use each person's average over the recommenders. Within-person correlations use each rating's "
                             "distance from that person's own average, pooled across people.")

# ---------------------------------------------------------------- figures: per-person points, bootstrap CIs, densities
def density(x, grid, adjust=1.5):
    x = np.asarray(pd.Series(x).dropna(), float)
    iqr = np.subtract(*np.percentile(x, [75, 25]))
    bw = 0.9 * min(x.std(ddof=1), iqr / 1.34) * len(x) ** (-0.2) * adjust  # R's bw.nrd0 times adjust
    dens = np.exp(-0.5 * ((grid[:, None] - x[None, :]) / bw) ** 2).sum(axis=1) / (len(x) * bw * np.sqrt(2 * np.pi))
    return dens


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


points["decisions"] = [series(DECISION_LABEL[k], k, d[k], grid100, dict(stage=STAGE[k])) for k in DECISION_LABEL]
points["composites"] = [series(COMPOSITE_LABEL[k], k, d[k], grid100) for k in COMPOSITE_LABEL]
points["trust"] = [series(MAKER[k], k, d[f"trust_{k}"], grid10, dict(ai=IS_AI[k])) for k in MAKER]
points["trust"].sort(key=lambda r: r["mean"])
points["domainOrder"] = ["q_acute", "q_chronic", "q_injury", "q_mental", "q_physical"]
points["stageOrder"] = ["q_diagnosis", "q_prescription", "q_preventative"]
points["densityGrid100"] = [float(v) for v in grid100]
points["densityGrid10"] = [float(v) for v in grid10]

# decision-maker map: means and 95% CI of the mean on quantitative reasoning and intuition
mm = []
for k, label in MAKER.items():
    q = d[f"capability_{k}"].dropna()
    i = d[f"intuition_{k}"].dropna()
    mm.append(dict(id=k, label=label, ai=IS_AI[k], qr=r2(q.mean()), qrCI=r2(1.96 * q.std() / np.sqrt(len(q))),
                   intuition=r2(i.mean()), intuitionCI=r2(1.96 * i.std() / np.sqrt(len(i))), n=int(len(q)),
                   trust=r2(d[f"trust_{k}"].mean())))
full["makerMap"] = mm

json.dump(full, open(OUT + "study1-full.json", "w"))
json.dump(points, open(OUT + "study1-points.json", "w"))
print("tests:", [(t["id"], t["t"], t["d"], t["dLo"], t["dHi"]) for t in tests])
print("eigenvalues:", full["efa"]["eigenvalues"][:5])
print("loadings:", full["efa"]["loadings"])
for m in models:
    print(m["label"], [(t["term"], t["b"]) for t in m["terms"]], "R2m", m["r2m"], "R2c", m["r2c"])
print(full["modelComparisons"])
print([ (r["label"], r["alpha"]) for r in rel])
