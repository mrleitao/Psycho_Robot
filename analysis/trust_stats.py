"""
Shared statistics for the Study 3, 4 and 5 result scripts.

Where the author's notebook used an R package, this file holds the closest Python equivalent:
  t.test (Welch)            welch()          unequal-variance t test, Cohen's d from the pooled SD
  paired t test             paired()         Cohen's d_z (mean difference over the SD of the differences)
  aov / Tukey               anova1(), tukey()
  lm                        ols()            ordinary least squares with the humanlike AI as the reference
  lmer                      lmm()            statsmodels MixedLM, REML, random intercept per person
  MuMIn::r.squaredGLMM      lmm()            Nakagawa marginal and conditional R squared
Run from the repository root; these helpers only compute, they read and write nothing.
"""
import re

import numpy as np
import pandas as pd
from scipy import stats, optimize
import statsmodels.formula.api as smf
from statsmodels.stats.multicomp import pairwise_tukeyhsd

rng = np.random.default_rng(2024)


def r2(x, k=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), k)


def clean(x):
    return pd.Series(x).dropna().astype(float)


def desc(x):
    x = clean(x)
    n = len(x)
    s = x.std(ddof=1)
    h = stats.t.ppf(0.975, n - 1) * s / np.sqrt(n)
    return dict(n=n, mean=r2(x.mean()), sd=r2(s), se=r2(s / np.sqrt(n)), lo=r2(x.mean() - h), hi=r2(x.mean() + h),
                median=r2(x.median()), min=r2(x.min()), max=r2(x.max()))


def boot_ci(x, B=2000):
    x = np.asarray(clean(x))
    means = rng.choice(x, size=(B, len(x)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def density(x, grid, adjust=1.5):
    x = np.asarray(clean(x))
    iqr = np.subtract(*np.percentile(x, [75, 25]))
    spread = min(x.std(ddof=1), iqr / 1.34) if iqr > 0 else x.std(ddof=1)
    bw = 0.9 * spread * len(x) ** (-0.2) * adjust
    return np.exp(-0.5 * ((grid[:, None] - x[None, :]) / bw) ** 2).sum(axis=1) / (len(x) * bw * np.sqrt(2 * np.pi))


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


def nct_ci(t, df, scale, level=0.95):
    """Confidence interval for a standardized effect by inverting the noncentral t distribution. scale turns the
    noncentrality into d: 1/sqrt(n) for paired data, sqrt(1/n1 + 1/n2) for two groups."""
    a = (1 - level) / 2

    def f(nc, q):
        return stats.nct.cdf(t, df, nc) - q
    w = 4 * np.sqrt(1 + t ** 2 / (2 * df)) + 2
    lo = optimize.brentq(f, t - w, t + w, args=(1 - a,))
    hi = optimize.brentq(f, t - w, t + w, args=(a,))
    return lo * scale, hi * scale


def welch(a, b, label=None, **extra):
    """a minus b. Two independent groups, unequal variances."""
    x, y = clean(a), clean(b)
    n1, n2 = len(x), len(y)
    v1, v2 = x.var(ddof=1), y.var(ddof=1)
    se = np.sqrt(v1 / n1 + v2 / n2)
    df = se ** 4 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
    diff = x.mean() - y.mean()
    t = diff / se
    p = 2 * stats.t.sf(abs(t), df)
    h = stats.t.ppf(0.975, df) * se
    sp = np.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    d = diff / sp
    tp = d / np.sqrt(1 / n1 + 1 / n2)
    lo, hi = nct_ci(tp, n1 + n2 - 2, np.sqrt(1 / n1 + 1 / n2))
    out = dict(nA=n1, nB=n2, meanA=r2(x.mean()), sdA=r2(x.std()), meanB=r2(y.mean()), sdB=r2(y.std()), diff=r2(diff), lo=r2(diff - h),
               hi=r2(diff + h), t=r2(t), df=r2(df), p=float(p), d=r2(d), dLo=r2(lo), dHi=r2(hi))
    if label:
        out["label"] = label
    out.update(extra)
    return out


def paired(a, b, label=None, **extra):
    """a minus b, for the same people."""
    x = pd.concat([pd.Series(a), pd.Series(b)], axis=1).dropna().astype(float)
    x.columns = ["a", "b"]
    diff = x.a - x.b
    n = len(x)
    t, p = stats.ttest_rel(x.a, x.b)
    h = stats.t.ppf(0.975, n - 1) * diff.std(ddof=1) / np.sqrt(n)
    dz = diff.mean() / diff.std(ddof=1)
    lo, hi = nct_ci(dz * np.sqrt(n), n - 1, 1 / np.sqrt(n))
    out = dict(n=n, meanA=r2(x.a.mean()), sdA=r2(x.a.std()), meanB=r2(x.b.mean()), sdB=r2(x.b.std()), diff=r2(diff.mean()),
               lo=r2(diff.mean() - h), hi=r2(diff.mean() + h), t=r2(t), df=n - 1, p=float(p), d=r2(dz), dLo=r2(lo), dHi=r2(hi),
               higher=int((diff > 0).sum()), same=int((diff == 0).sum()), lower=int((diff < 0).sum()))
    if label:
        out["label"] = label
    out.update(extra)
    return out


def anova1(groups):
    """One-way ANOVA across independent groups. groups: dict name -> values."""
    arrs = {k: np.asarray(clean(v)) for k, v in groups.items()}
    F, p = stats.f_oneway(*arrs.values())
    allv = np.concatenate(list(arrs.values()))
    n, k = len(allv), len(arrs)
    ssb = sum(len(v) * (v.mean() - allv.mean()) ** 2 for v in arrs.values())
    sst = ((allv - allv.mean()) ** 2).sum()
    return dict(F=r2(F), df1=k - 1, df2=n - k, p=float(p), eta2=r2(ssb / sst, 3), n=n)


def tukey(groups):
    """Tukey HSD adjusted p values for every pair. groups: dict name -> values."""
    vals, labs = [], []
    for k, v in groups.items():
        v = clean(v)
        vals += list(v)
        labs += [k] * len(v)
    res = pairwise_tukeyhsd(np.array(vals), np.array(labs))
    out = {}
    for row in res.summary().data[1:]:
        out[(row[0], row[1])] = dict(diff=r2(row[2]), p=float(row[3]))
        out[(row[1], row[0])] = dict(diff=r2(-row[2]), p=float(row[3]))
    return out


def ols(data, y, terms, label):
    """terms: list of (column, public name). Listwise deletion within the model."""
    cols = [c for c, _ in terms]
    D = data.dropna(subset=[y] + cols)
    fit = smf.ols(f"{y} ~ " + " + ".join(cols), D).fit()
    rows = [dict(term="Intercept", b=r2(fit.params["Intercept"], 3), se=r2(fit.bse["Intercept"], 3), t=r2(fit.tvalues["Intercept"]), p=float(fit.pvalues["Intercept"]))]
    for c, name in terms:
        rows.append(dict(term=name, b=r2(fit.params[c], 3), se=r2(fit.bse[c], 3), t=r2(fit.tvalues[c]), p=float(fit.pvalues[c])))
    return dict(label=label, n=int(fit.nobs), r2=r2(fit.rsquared, 3), r2adj=r2(fit.rsquared_adj, 3), df=int(fit.df_resid), terms=rows)


def lmm(formula, data, group, y, label, names=None):
    """Random intercept for each person, REML, Wald z tests, Nakagawa R squared."""
    need = [t for t in data.columns if re.search(rf"\b{re.escape(t)}\b", formula)]
    D = data.dropna(subset=need).reset_index(drop=True)
    md = smf.mixedlm(formula, D, groups=D[group])
    res = None
    for method in (["lbfgs", "powell"], ["powell"], ["bfgs"], ["nm"]):
        try:
            res = md.fit(reml=True, method=method, maxiter=4000)
            if res.converged:
                break
        except np.linalg.LinAlgError:
            continue
    X = md.exog
    fe = res.fe_params.values
    var_f = float(np.var(X @ fe))
    var_p = float(res.cov_re.values[0, 0])
    var_e = float(res.scale)
    tot = var_f + var_p + var_e
    sdy = float(D[y].std())
    terms = []
    for nm in res.fe_params.index:
        b, se = float(res.fe_params[nm]), float(res.bse_fe[nm])
        base = nm.split("[")[0]
        std = None
        if nm != "Intercept" and ":" not in nm and "[" not in nm and base in D.columns:
            std = b * float(D[base].std()) / sdy
        terms.append(dict(term=(names or {}).get(nm, nm), raw=nm, b=r2(b, 3), se=r2(se, 3), lo=r2(b - 1.96 * se, 3), hi=r2(b + 1.96 * se, 3),
                          z=r2(b / se), p=float(2 * stats.norm.sf(abs(b / se))), beta=r2(std, 3) if std is not None else None))
    return dict(label=label, formula=formula, n=int(len(D)), people=int(D[group].nunique()), terms=terms, varPerson=r2(var_p, 3), varResidual=r2(var_e, 3),
                icc=r2(var_p / (var_p + var_e), 3), r2m=r2(var_f / tot, 3), r2c=r2((var_f + var_p) / tot, 3), converged=bool(res.converged))


def cronbach(df):
    c = df.cov()
    k = df.shape[1]
    return float(k / (k - 1) * (1 - np.trace(c.values) / c.values.sum()))


def sample_table(d, demo):
    N = len(d)
    out = []
    for col, name, levels in demo:
        rows = [dict(group=lv, n=int((d[col] == lv).sum()), pct=r2(100 * (d[col] == lv).sum() / N, 1)) for lv in levels]
        out.append(dict(variable=name, rows=rows, missing=int(d[col].isna().sum())))
    return dict(n=N, variables=out)


DEMO = [("age_group", "Age group", ["18-44", "45-59", "60-69", "70+"]), ("gender", "Gender", ["Woman", "Man"]),
        ("race", "Race", ["White", "Another or multiple"]), ("education", "Education", ["No college degree", "College degree or more"]),
        ("religiosity", "How religious", ["Not at all to slightly", "Moderately", "More than moderately"])]
