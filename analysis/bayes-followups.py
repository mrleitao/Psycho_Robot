"""
Bayes factors for the Doctor-versus-AI studies, with a Cauchy prior on the effect.

Reads   public/data/study2-ratings.csv and the Study 1 and Study 2 result files in src/data/trust-in-medical-ai/
Writes  src/data/trust-in-medical-ai/bayes.json

Three kinds of test, each with a Cauchy (JZS) prior centred on zero:
  t        Rouder et al. (2009) default Bayes factor for a t statistic. The prior is on the standardized
           effect size d with scale r = sqrt(2)/2 (the "medium" default); r = 0.5 and r = 1 are shown as a check.
  coef     A regression or mixed-model coefficient, from its estimate and standard error (normal likelihood,
# Bayes factors: JZS BF10 for t tests; Cauchy prior widths set to Funder and Ozer (2019) small, medium and large (d 0.20, 0.41, 0.63; r .10, .20, .30).
           continuous predictors use 0.354 per standard deviation.
  stat     Studies 3 to 6: the dissertation reports t, d, df, and coefficients with intervals but the raw data
           are not released yet, so these Bayes factors come from the reported statistics.

BF01 is the evidence for no difference (1 / BF10). BF10 is the evidence for a difference.
Run from the repository root.  Needs numpy, pandas, scipy.
"""
import json, math
import numpy as np
import pandas as pd
from scipy import integrate, stats

OUT = "src/data/trust-in-medical-ai/"
R_MAIN = math.sqrt(2) / 2
# Funder and Ozer (2019) benchmarks. The prior is a Cauchy curve whose width is set to a small, a medium and a large effect.
FO_NAMES = ["small", "medium", "large"]
FO_R = [0.10, 0.20, 0.30]                                   # correlation benchmarks
FO_D = [round(2 * r / math.sqrt(1 - r * r), 2) for r in FO_R]  # the same effects as Cohen's d: 0.20, 0.41, 0.63


# ---------------------------------------------------------------- Bayes factors
def jzs_bf10(t, n_eff, df, r=R_MAIN):
    """Rouder, Speckman, Sun, Morey & Iverson (2009), equation 1. n_eff is n for one-sample and paired
    tests and n1*n2/(n1+n2) for two-sample tests."""
    t = abs(float(t)); nu = float(df)
    num = (1 + t * t / nu) ** (-(nu + 1) / 2)
    def f(g):
        a = 1 + n_eff * g * r * r
        return a ** -0.5 * (1 + t * t / (nu * a)) ** (-(nu + 1) / 2) * (2 * math.pi) ** -0.5 * g ** -1.5 * math.exp(-1 / (2 * g))
    val = integrate.quad(f, 0, np.inf, limit=300)[0] + 0.0
    return val / num


def coef_bf10(est, se, scale):
    """Normal likelihood for the estimate, Cauchy prior (centred on 0, given scale) on the true value,
    both in the same units as est and se."""
    lik = lambda th: stats.norm.pdf(est, th, se)
    lo, hi = est - 12 * se, est + 12 * se  # the normal likelihood is negligible outside this range
    pts = [x for x in (0.0, est) if lo < x < hi]
    marg = integrate.quad(lambda th: lik(th) * stats.cauchy.pdf(th, 0, scale), lo, hi, points=pts or None, limit=300)[0]
    return marg / stats.norm.pdf(est, 0, se)


def label(bf10):
    """Words for the evidence, after Lee and Wagenmakers (2013). Reports the direction with the stronger evidence."""
    bf = bf10 if bf10 >= 1 else 1 / bf10
    side = "for a difference" if bf10 >= 1 else "for no difference"
    if bf < 3: w = "Anecdotal"
    elif bf < 10: w = "Moderate"
    elif bf < 30: w = "Strong"
    elif bf < 100: w = "Very strong"
    else: w = "Extreme"
    return f"{w} evidence {side}"


def sig(x, k=3):
    if x == 0 or not np.isfinite(x): return x
    return float(f"{x:.{k}g}")


ROWS = []

def add(study, group, tid, text, source, kind, stat, bf_fn, scales, prior_note, preregistered=None):
    bfs = [bf_fn(s) for s in scales]
    main = bfs[1] if len(scales) == 3 else bfs[0]
    ROWS.append({
        "study": study, "group": group, "id": tid, "text": text, "source": source, "kind": kind, "stat": stat,
        "priorNote": prior_note,
        "bf10": sig(main), "bf01": sig(1 / main),
        "sensitivity": [{"scale": s, "size": FO_NAMES[i], "bf10": sig(b), "bf01": sig(1 / b)} for i, (s, b) in enumerate(zip(scales, bfs))],
        "verdict": label(main),
        "supportsNull": bool(main < 1),
    })


T_SCALES = FO_D
def t_rows(study, group, tid, text, source, t, n_eff, df, d, extra=""):
    stat = {"t": t, "df": df, "d": d, "nEff": round(n_eff, 1)}
    add(study, group, tid, text, source, "t", stat, lambda s: jzs_bf10(t, n_eff, df, s), list(T_SCALES),
        "Cauchy prior on d, width set to a small (0.20), medium (0.41) and large (0.63) effect")


# ---------------------------------------------------------------- Study 1 (raw data)
s1 = json.load(open(OUT + "study1-full.json"))
for t in s1["tests"] + s1["extraTests"]:
    n = t["n"]
    t_rows("Study 1", "Hypothesis tests" if t["id"] != "E" and not t["id"].startswith("X") else "Further comparisons",
           t["id"], t["text"], "raw data", t["t"], n, t["df"], t["d"])
hv = json.load(open(OUT + "study1-human-vs-ai.json"))
for t in hv["tests"]:
    for key, nm in [("human_vs_ai", "humans versus AI")]:
        if key in t:
            r = t[key]
            t_rows("Study 1", "Humans versus AI", f"HvA-{t['key']}", f"{t['measure']}: {nm}", "raw data", r["t"], r["n"], r["df"], r["d"])

# ---------------------------------------------------------------- Study 2 (raw data)
d = pd.read_csv("public/data/study2-ratings.csv")
DEC = {
    "prevent_injury_stretching": ("preventative", "bodily injury"), "diagnose_broken_bone": ("diagnostic", "bodily injury"),
    "prescribe_pain_medication": ("prescriptive", "bodily injury"), "prevent_mental_meditation": ("preventative", "mental health"),
    "diagnose_depression": ("diagnostic", "mental health"), "prescribe_mental_therapy": ("prescriptive", "mental health"),
    "prevent_acute_vitamins": ("preventative", "acute sickness"), "diagnose_strep_throat": ("diagnostic", "acute sickness"),
    "prescribe_antibiotics": ("prescriptive", "acute sickness"), "prevent_chronic_diet": ("preventative", "chronic sickness"),
    "diagnose_diabetes": ("diagnostic", "chronic sickness"), "prescribe_insulin": ("prescriptive", "chronic sickness"),
}
def gap(keys):
    return (d[[f"trust_doctor_{k}" for k in keys]].mean(axis=1, skipna=False) - d[[f"trust_ai_{k}" for k in keys]].mean(axis=1, skipna=False))
G = {
    "Diagnostic": gap([k for k, v in DEC.items() if v[0] == "diagnostic"]),
    "Prescriptive": gap([k for k, v in DEC.items() if v[0] == "prescriptive"]),
    "Preventative": gap([k for k, v in DEC.items() if v[0] == "preventative"]),
    "Physical health": gap([k for k, v in DEC.items() if v[1] != "mental health"]),
    "Mental health": gap([k for k, v in DEC.items() if v[1] == "mental health"]),
    "Bodily injury": gap([k for k, v in DEC.items() if v[1] == "bodily injury"]),
    "Acute sickness": gap([k for k, v in DEC.items() if v[1] == "acute sickness"]),
    "Chronic sickness": gap([k for k, v in DEC.items() if v[1] == "chronic sickness"]),
}
def paired_gap(a, b, group):
    x = (G[a] - G[b]).dropna(); n = len(x)
    t, p = stats.ttest_1samp(x, 0)
    dz = x.mean() / x.std(ddof=1)
    t_rows("Study 2", group, f"gap-{a}-{b}", f"Doctor-minus-AI gap: {a.lower()} versus {b.lower()}", "raw data", float(t), n, n - 1, float(dz))
    ROWS[-1]["stat"].update({"diff": round(float(x.mean()), 2), "p": float(p)})
for a, b in [("Diagnostic", "Prescriptive"), ("Diagnostic", "Preventative"), ("Prescriptive", "Preventative")]:
    paired_gap(a, b, "Does the gap change with the kind of decision?")
for a, b in [("Physical health", "Mental health"), ("Bodily injury", "Acute sickness"), ("Bodily injury", "Chronic sickness"), ("Acute sickness", "Chronic sickness")]:
    paired_gap(a, b, "Does the gap change with the kind of decision?")

s2 = json.load(open(OUT + "study2-full.json"))
MM = {m["label"][:20]: m for m in s2["mixedModels"]}
full = [m for m in s2["mixedModels"] if m["label"].startswith("Add intuition")][0]
sd_trust = float(pd.concat([d[[f"trust_doctor_{k}" for k in DEC]].stack(), d[[f"trust_ai_{k}" for k in DEC]].stack()]).std())
need_cols = [f"needs_quant_{k}" for k in DEC]
sd_need = float(d[need_cols].stack().std())
def term(m, name): return [t for t in m["terms"] if t["term"] == name][0]

def coef_row(study, group, tid, text, est, se, unit_sd, binary, stat_note, source="raw data"):
    """est and se in raw units; unit_sd converts a one-unit change to standardized units (SD of outcome / SD of predictor)."""
    k = 1 / sd_trust * unit_sd  # raw -> standardized
    scales = FO_D if binary else FO_R
    est_s, se_s = est * k, se * k
    add(study, group, tid, text, source, "coef", {"b": est, "se": se, "note": stat_note},
        lambda s: coef_bf10(est_s, se_s, s), list(scales),
        "Cauchy prior on the standardized effect, width set to a small, medium and large effect (%s)" % ("d: 0.20, 0.41, 0.63" if binary else "per standard deviation, r: 0.10, 0.20, 0.30"))

t_ = term(full, "IsDoc:Int_Quant")
coef_row("Study 2", "Does the gap depend on the decision?", "H2-interaction",
         "Doctor-minus-AI gap by how much quantitative reasoning the decision needs", t_["b"], t_["se"], sd_need, False,
         "full model, per point on the 0 to 100 scale")
t_ = term(full, "Int_Quant")
coef_row("Study 2", "Does the gap depend on the decision?", "H2-main",
         "Trust by how much quantitative reasoning the decision needs", t_["b"], t_["se"], sd_need, False, "full model")
t_ = term(full, "IsMale")
coef_row("Study 2", "Do people differ?", "gender", "Trust by gender (man versus not)", t_["b"], t_["se"], 1.0, True, "full model")
t_ = term(full, "AgeGroup")
age_sd = float(pd.to_numeric(d["age_group"].map({"18-44": 1, "45-59": 2, "60-69": 3, "70+": 4})).std())
coef_row("Study 2", "Do people differ?", "age", "Trust by age group (four bands)", t_["b"], t_["se"], age_sd, False, "full model, per age band")
ageModel = [m for m in s2["mixedModels"] if m["label"].startswith("Age group by doctor")][0]
t_ = term(ageModel, "AgeGroup:IsDoc")
coef_row("Study 2", "Do people differ?", "age-by-doctor", "Does the gap grow with age? (age band by doctor)", t_["b"], t_["se"], age_sd, False,
         "age model, per age band; the interaction is the change in the gap")
# warmth mediation (the dissertation's H5): estimate and standard error from the released analysis
for m in s2["mediation"]:
    if m["label"].startswith("Warmth and competence"):
        w = m["mediators"][0]
        se = w["indirect"] / w["z"]
        coef_row("Study 2", "What explains the gap?", "H5-warmth", "Warmth as a mediator of the doctor-AI gap",
                 w["indirect"], se, 1.0, True, "indirect effect, trust points", source="raw data")
        ROWS[-1]["priorNote"] = "Cauchy prior on the indirect effect in standard-deviation units of trust, width set to a small, medium and large effect (d: 0.20, 0.41, 0.63)"

# ---------------------------------------------------------------- Study 6 (reported statistics)
# Every number below is copied from the dissertation text (Leitao, 2024). n_eff for two-sample tests comes from (t / d)^2.
def rep_t(study, group, tid, text, t, d_, df, paired=False, page=None):
    n_eff = (df + 1) if paired else (t / d_) ** 2
    t_rows(study, group, tid, text, "reported statistics", t, n_eff, df, d_)
    ROWS[-1]["page"] = page

def rep_coef(study, group, tid, text, b, lo, hi, scale_unit, note, page, binary=True):
    se = (hi - lo) / (2 * 1.96)
    scales = FO_D if binary else FO_R
    k = 1 / scale_unit
    add(study, group, tid, text, "reported statistics", "coef", {"b": b, "se": round(se, 3), "note": note},
        lambda s: coef_bf10(b * k, se * k, s), list(scales), "Cauchy prior on the standardized effect, width set to a small, medium and large effect (d: 0.20, 0.41, 0.63)")
    ROWS[-1]["page"] = page

# ---------------------------------------------------------------- Studies 3 to 5 (raw data)
# Differences are first minus second (doctor or humanlike AI first). Bayes factors do not depend on the sign.
def raw_t(study, group, tid, text, r, page):
    n_eff = r["n"] if "n" in r else r["nA"] * r["nB"] / (r["nA"] + r["nB"])
    t_rows(study, group, tid, text, "raw data", r["t"], n_eff, r["df"], r["d"])
    ROWS[-1]["stat"].update({"diff": r["diff"], "p": r["p"]})
    ROWS[-1]["page"] = page

s3 = json.load(open(OUT + "study3-full.json"))
s4 = json.load(open(OUT + "study4-full.json"))
s5 = json.load(open(OUT + "study5-full.json"))
pick = lambda rows, i: [r for r in rows if r["id"] == i][0]
MEAS = {"trust": "Trust", "belief": "Belief"}
for m, w in MEAS.items():
    raw_t("Study 3", "Humanizing the AI (between people)", f"S3-{m}-hum-std", f"{w}: humanlike AI versus standard AI", pick(s3["tests"][m], "hum-std"), "Chapter 3, Study 3")
    raw_t("Study 3", "Doctor versus AI (between people)", f"S3-{m}-doc-std", f"{w}: doctor versus standard AI", pick(s3["tests"][m], "doc-std"), "Chapter 3, Study 3")
    raw_t("Study 3", "Humanlike AI versus doctor (between people)", f"S3-{m}-hum-doc", f"{w}: humanlike AI versus doctor", pick(s3["tests"][m], "doc-hum"), "Chapter 3, Study 3")
for m, w in MEAS.items():
    raw_t("Study 4", "Humanizing the AI (between people)", f"S4-{m}-hum-std", f"{w}: humanlike AI versus standard AI", pick(s4["betweenTests"][m], "hum-std"), "Chapter 3, Study 4")
    raw_t("Study 4", "Doctor versus AI (between people)", f"S4-{m}-doc-std", f"{w}: doctor versus standard AI", pick(s4["betweenTests"][m], "doc-std"), "Chapter 3, Study 4")
    raw_t("Study 4", "Humanlike AI versus doctor (between people)", f"S4-{m}-hum-doc", f"{w}: humanlike AI versus doctor", pick(s4["betweenTests"][m], "doc-hum"), "Chapter 3, Study 4")
for m, w in MEAS.items():
    raw_t("Study 4", "Humanizing the AI (side by side)", f"S4w-{m}-hum-std", f"{w}: humanlike AI versus standard AI", pick(s4["withinTests"][m], "hum-std"), "Chapter 3, Study 4")
    raw_t("Study 4", "Doctor versus AI (side by side)", f"S4w-{m}-doc-std", f"{w}: doctor versus standard AI", pick(s4["withinTests"][m], "doc-std"), "Chapter 3, Study 4")
    raw_t("Study 4", "Humanlike AI versus doctor (side by side)", f"S4w-{m}-hum-doc", f"{w}: humanlike AI versus doctor", pick(s4["withinTests"][m], "doc-hum"), "Chapter 3, Study 4")
for r, nm, short in (("doctor", "Doctor", "doc"), ("humanlike", "Humanlike AI", "hum"), ("standard", "Standard AI", "std")):
    raw_t("Study 5", "Does a voice help? (between people)", f"S5-{short}-voice", f"{nm}: voiced versus written", pick(s5["voiceTests"]["tb"], f"voice-{r}"), "Chapter 3, Study 5")
raw_t("Study 5", "Humanizing the AI (side by side)", "S5-hum-std", "Humanlike AI versus standard AI", pick(s5["pairedTests"]["tb"], "hum-std"), "Chapter 3, Study 5")
raw_t("Study 5", "Doctor versus AI (side by side)", "S5-doc-std", "Doctor versus standard AI", pick(s5["pairedTests"]["tb"], "doc-std"), "Chapter 3, Study 5")
raw_t("Study 5", "Humanlike AI versus doctor (side by side)", "S5-hum-doc", "Humanlike AI versus doctor", pick(s5["pairedTests"]["tb"], "hum-doc"), "Chapter 3, Study 5")
# Study 5 model terms (Table 22). The outcome SD comes from the person and residual variances of the model.
m5 = s5["mixedModels"][2]
sd5 = math.sqrt(m5["varPerson"] + m5["varResidual"])
def m5term(name): return [t for t in m5["terms"] if t["term"] == name][0]
for tid, txt, nm, grp in [("S5-voice-main", "Voice, across all recommenders", "Voiced (versus written only)", "Does a voice help? (between people)"),
                          ("S5-voice-std-int", "Voice effect for the standard AI versus the humanlike AI", "Standard AI × voiced", "Does a voice help? (between people)"),
                          ("S5-voice-doc-int", "Voice effect for the doctor versus the humanlike AI", "Doctor × voiced", "Does a voice help? (between people)"),
                          ("S5-doc-adj", "Doctor versus humanlike AI after adjusting for mind, warmth, competence", "Doctor (versus humanlike AI)", "Humanlike AI versus doctor (side by side)")]:
    t_ = m5term(nm)
    add("Study 5", grp, tid, txt, "raw data", "coef", {"b": t_["b"], "se": t_["se"], "note": "Table 22 model"},
        lambda s, t_=t_: coef_bf10(t_["b"] / sd5, t_["se"] / sd5, s), list(FO_D),
        "Cauchy prior on the standardized effect, width set to a small, medium and large effect (d: 0.20, 0.41, 0.63)")
    ROWS[-1]["page"] = "Chapter 3, Study 5"
# Study 5 mediation through mind perception: indirect effect over the SD of the outcome
for i, (tid, txt) in enumerate([("S5-med-doc-std", "Mind perception as a mediator: doctor versus standard AI"), ("S5-med-hum-std", "Mind perception as a mediator: humanlike AI versus standard AI"),
                                ("S5-med-hum-doc", "Mind perception as a mediator: humanlike AI versus doctor")]):
    m_ = s5["mediation"][i]
    se = abs(m_["indirect"] / m_["z"])
    add("Study 5", "Does mind perception explain the gaps?", tid, txt, "raw data", "coef", {"b": m_["indirect"], "se": round(se, 4), "note": "indirect effect, trust/belief points"},
        lambda s, m_=m_, se=se: coef_bf10(m_["indirect"] / sd5, se / sd5, s), list(FO_D),
        "Cauchy prior on the indirect effect in standard-deviation units of the outcome, width set to a small, medium and large effect (d: 0.20, 0.41, 0.63)")
    ROWS[-1]["page"] = "Chapter 3, Study 5"

# Study 6 (Tables 23 and 24, model 2). Outcome SD about 1.06 (sleep) and 1.03 (phone in bed) from sigma-squared.
rep_coef("Study 6", "Did the recommender change what people did?", "S6-sleep-int", "Sleep: change after the advice, AI versus doctor", -0.03, -0.144, 0.079, math.sqrt(1.13 + 0.01), "Table 23", "Chapter 4, Study 6")
rep_coef("Study 6", "Did the recommender change what people did?", "S6-sleep-cond", "Sleep: AI versus doctor, overall", 0.03, -0.053, 0.108, math.sqrt(1.13 + 0.01), "Table 23", "Chapter 4, Study 6")
rep_coef("Study 6", "Did the recommender change what people did?", "S6-dib-int", "Phone in bed: change after the advice, AI versus doctor", 0.07, -0.030, 0.175, math.sqrt(0.94 + 0.13), "Table 24", "Chapter 4, Study 6")
rep_coef("Study 6", "Did the recommender change what people did?", "S6-dib-cond", "Phone in bed: AI versus doctor, overall", 0.03, -0.065, 0.132, math.sqrt(0.94 + 0.13), "Table 24", "Chapter 4, Study 6")
# mediation by mind perception: the dissertation gives b and z, so se = b / z
for tid, txt, b, z in [("S6-sleep-med", "Sleep: mind perception as a mediator", -0.012, -0.943), ("S6-dib-med", "Phone in bed: mind perception as a mediator", 0.006, 0.333)]:
    se = abs(b / z)
    add("Study 6", "Did the recommender change what people did?", tid, txt, "reported statistics", "coef", {"b": b, "se": round(se, 4), "note": "indirect effect, from b and z"},
        lambda s, b=b, se=se: coef_bf10(b / math.sqrt(1.13), se / math.sqrt(1.13), s), list(FO_D),
        "Cauchy prior on the standardized effect, width set to a small, medium and large effect (d: 0.20, 0.41, 0.63)")
    ROWS[-1]["page"] = "Chapter 4, Study 6"

out = {
    "method": "Bayes factors with a Cauchy prior centred on no effect. The width of the prior is set to a small, a medium and a large effect on the Funder and Ozer (2019) benchmarks (r = .10, .20, .30, which are d = 0.20, 0.41, 0.63); the medium prior is the headline. t tests use the Rouder et al. (2009) default Bayes factor. Coefficients use a normal likelihood from the estimate and its standard error. BF10 is how many times more likely the data are if there is a difference; BF01 is how many times more likely they are if there is none.",
    "funderOzer": [{"r": r, "d": d, "size": n} for r, d, n in zip(FO_R, FO_D, FO_NAMES)],
    "evidenceWords": [
        {"min": 100, "label": "Extreme"}, {"min": 30, "label": "Very strong"}, {"min": 10, "label": "Strong"}, {"min": 3, "label": "Moderate"}, {"min": 1, "label": "Anecdotal"},
    ],
    "rows": ROWS,
}
json.dump(out, open(OUT + "bayes.json", "w"), indent=1)
print(len(ROWS), "rows")
for r in ROWS:
    print(f"{r['study']:8s} {r['id']:22s} BF10={r['bf10']:<10} BF01={r['bf01']:<10} {r['verdict']}")
