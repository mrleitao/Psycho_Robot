"""
Compute the summary files the website charts read, from public/data/study1-ratings.csv.

Writes
  src/data/trust-in-medical-ai/trust-by-recommender.json   mean, SD and 95% CI of trust, per recommender
  src/data/trust-in-medical-ai/study1-tests.json           the seven preregistered paired tests plus one exploratory test

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

# Composites exactly as in the original analysis script.
def comp(cols): return d[cols].mean(axis=1)
d["q_diagnosis"] = comp(["diagnose_broken_bone", "diagnose_depression", "diagnose_strep_throat", "diagnose_diabetes"])
d["q_prescription"] = comp(["prescribe_pain_medication", "prescribe_mental_therapy", "prescribe_antibiotics", "prescribe_insulin"])
d["q_preventative"] = comp(["prevent_injury_stretching", "prevent_mental_meditation", "prevent_acute_vitamins", "prevent_chronic_diet"])
d["q_physical"] = comp(["diagnose_broken_bone", "diagnose_strep_throat", "diagnose_diabetes", "prevent_injury_stretching",
                        "prevent_acute_vitamins", "prevent_chronic_diet", "prescribe_pain_medication", "prescribe_antibiotics", "prescribe_insulin"])
d["q_mental"] = comp(["diagnose_depression", "prevent_mental_meditation", "prescribe_mental_therapy"])
d["q_injury"] = comp(["diagnose_broken_bone", "prevent_injury_stretching", "prescribe_pain_medication"])
d["q_acute"] = comp(["diagnose_strep_throat", "prevent_acute_vitamins", "prescribe_antibiotics"])

TESTS = [
    ("1.a.1", "Diagnostic decisions need more quantitative reasoning than prescriptive ones", "q_diagnosis", "q_prescription", "Diagnostic", "Prescriptive", "0 to 100"),
    ("1.a.2", "Diagnostic decisions need more quantitative reasoning than preventative ones", "q_diagnosis", "q_preventative", "Diagnostic", "Preventative", "0 to 100"),
    ("1.a.3", "Prescriptive decisions need more quantitative reasoning than preventative ones", "q_prescription", "q_preventative", "Prescriptive", "Preventative", "0 to 100"),
    ("1.b.1", "Physical health decisions need more quantitative reasoning than mental health ones", "q_physical", "q_mental", "Physical health", "Mental health", "0 to 100"),
    ("1.b.2", "Bodily injury decisions need more quantitative reasoning than acute sickness ones", "q_injury", "q_acute", "Bodily injury", "Acute sickness", "0 to 100"),
    ("2.a.1", "A doctor is seen as more capable of intuition than an AI", "intuition_doctor", "intuition_ai_general", "Doctor", "AI", "0 to 10"),
    ("2.a.2", "A doctor is seen as more capable of quantitative reasoning than an AI (exploratory, not preregistered)", "capability_doctor", "capability_ai_general", "Doctor", "AI", "0 to 10"),
    ("3.a", "Doctors are judged more trustworthy than medical AI", "trust_doctor", "trust_ai_general", "Doctor", "AI", "0 to 10"),
]
out = []
for hid, text, a, b, la, lb, scale in TESTS:
    x = d[[a, b]].dropna()
    diff = x[a] - x[b]
    t, p = stats.ttest_rel(x[a], x[b])
    dz = diff.mean() / diff.std(ddof=1)
    n = len(x)
    h = stats.t.ppf(0.975, n - 1) * diff.std(ddof=1) / np.sqrt(n)
    out.append(dict(id=hid, text=text, a=la, b=lb, scale=scale, n=n, meanA=round(x[a].mean(), 2), meanB=round(x[b].mean(), 2),
                    diff=round(diff.mean(), 2), lo=round(diff.mean() - h, 2), hi=round(diff.mean() + h, 2),
                    t=round(float(t), 2), df=n - 1, p=float(p), d=round(float(dz), 2),
                    supported=bool(p < .05 and diff.mean() > 0)))
json.dump({"note": "Paired t tests on the released data. d is Cohen's d for paired data (mean difference over the SD of the differences).",
           "tests": out}, open("src/data/trust-in-medical-ai/study1-tests.json", "w"), indent=2)
for o in out: print(o["id"], o["n"], o["meanA"], o["meanB"], o["t"], f'{o["p"]:.3g}', o["d"], o["supported"])
