"""
De-identify the Study 2 survey export for public release.

Input : the raw Qualtrics .sav export (not in this repository; it contains IP addresses,
        coordinates, response IDs, panel IDs and free-text answers).
Output: public/data/study2-ratings.csv and public/data/study2-codebook.csv

What it does
  1. Drops the four Qualtrics preview and test rows at the top of the export.
  2. Keeps people who gave consent (Consent == 1). This gives the N = 106 analysed in the dissertation.
  3. Keeps only the analysis variables: 12 decision ratings, 24 trust ratings (a doctor and an AI for
     each decision) and 11 ratings of each of the doctor and the AI.
     Everything else is dropped: IP address, coordinates, timestamps, response, panel and device IDs,
     free-text answers, and every demographic question not listed in DEMOGRAPHICS.
  4. Recodes every rating from the export's stored codes to the numbers participants saw. Qualtrics stores
     the 0 to 10 scale labels under codes that skip numbers (for example 0, 1, 2 ... 9, 10 are stored as
     1, 3, 4 ... 11, 13), so each variable is decoded with its own value labels. Competence and warmth
     are reported on a 0 to 4 scale ("does not describe at all" to "describes completely"). Differences,
     correlations and slopes are unaffected; means and intercepts differ from the notebook, which kept some
     of the stored codes (for example competence as 4 to 8).
  5. Adds five coarse demographic groups for filtering (see DEMOGRAPHICS below). Age is released only in
     groups, and income, employment, ethnicity details, Hispanic and transgender status, first language and
     free-text answers are not released at all.
  6. Replaces response IDs with participant numbers assigned after a seeded shuffle, so row order carries
     no information about when someone took the survey.

Usage: python3 analysis/study2-deidentify.py path/to/raw.sav
Needs: pandas, pyreadstat, numpy
"""
import csv
import re
import sys

import numpy as np
import pandas as pd
import pyreadstat

SEED = 2023

# public name, label, stage, domain, raw decision column, raw trust column stem
DECISIONS = [
    ("prevent_injury_stretching", "Recommend stretching to prevent injury", "preventative", "bodily injury", "Int_Quant_1", "A1"),
    ("diagnose_broken_bone", "Diagnose a broken bone", "diagnostic", "bodily injury", "Int_Quant_2", "A2"),
    ("prescribe_pain_medication", "Prescribe pain medication for a knee injury", "prescriptive", "bodily injury", "Int_Quant_4", "A4"),
    ("prevent_mental_meditation", "Recommend meditation and exercise for mental health", "preventative", "mental health", "Int_Quant_5", "A5"),
    ("diagnose_depression", "Diagnose depression", "diagnostic", "mental health", "Int_Quant_6", "A6"),
    ("prescribe_mental_therapy", "Prescribe antidepressants and cognitive behavioral therapy", "prescriptive", "mental health", "Int_Quant_7", "A7"),
    ("prevent_acute_vitamins", "Recommend vitamin C and zinc to fight off infections", "preventative", "acute sickness", "Int_Quant_8", "A8"),
    ("diagnose_strep_throat", "Diagnose strep throat", "diagnostic", "acute sickness", "Int_Quant_9", "A9"),
    ("prescribe_antibiotics", "Prescribe antibiotics for strep throat", "prescriptive", "acute sickness", "Int_Quant_10", "A10"),
    ("prevent_chronic_diet", "Recommend a strict diet for better physical health", "preventative", "chronic sickness", "Int_Quant_11", "A11"),
    ("diagnose_diabetes", "Diagnose diabetes", "diagnostic", "chronic sickness", "Int_Quant_12", "A12"),
    ("prescribe_insulin", "Prescribe insulin and a change in diet for diabetes", "prescriptive", "chronic sickness", "Int_Quant_13", "A13"),
]

# public name, question text, scale, raw stem (the export names them Decision_Maker.<stem>.Doc / .AI)
QUALITIES = [
    ("quantitative_reasoning", "How capable is each entity of using quantitative reasoning to make recommendations about health?", "0 to 10", "Decision_Maker.QR.{}"),
    ("intuition", "How capable is each entity of using intuition to make recommendations about health?", "0 to 10", "Decision_Maker.IN.{}"),
    ("general_accuracy", "How capable is each entity at making accurate recommendations about health in general?", "0 to 10", "Decision_Maker.Gen.{}"),
    ("anticipate_needs", "How much do you believe each entity can anticipate your future health needs?", "0 to 10", "Decision_Maker.Antic.{}"),
    ("understand_feelings", "How much do you believe each entity understands your feelings surrounding your health?", "0 to 10", "Decision_Maker.Under.{}"),
    ("account_for_needs", "How much do you believe each entity can account for your health needs?", "0 to 10", "Decision_Maker.Acct.{}"),
    ("familiar_process", "How much does each entity's decision making process remind you of receiving other types of health recommendations?", "0 to 10", "Decision_Maker.Fam.{}"),
    ("transparent_process", "How transparent is the decision making process for each entity?", "0 to 10", "Decision_Maker.Trans.{}"),
    ("understand_process", "How much do you understand the process by which each entity comes up with a health recommendation?", "0 to 10", "Decision_Maker.PUnd.{}"),
    ("competence", "How much do you believe competent and capable describes the entity?", "0 to 4", "Competence.{}"),
    ("warmth", "How much do you believe warm and friendly describes the entity?", "0 to 4", "Warmth.{}"),
]
MIND_ITEMS = ["general_accuracy", "anticipate_needs", "understand_feelings", "account_for_needs", "familiar_process",
              "transparent_process", "understand_process"]

# Coarse demographic groups released for filtering. To release fewer, delete entries here and re-run.
DEMOGRAPHICS = [
    ("age_group", "Age group, in years", ["18-44", "45-59", "60-69", "70+"]),
    ("gender", "Gender, as reported. Only woman and man were reported by 10 or more people, so smaller groups are left blank", ["Woman", "Man"]),
    ("race", "Race, as reported. White only if that is the only group selected; everyone else, including anyone selecting more than one, is combined", ["White", "Another or multiple"]),
    ("education", "Highest education completed, in two groups", ["No college degree", "College degree or more"]),
    ("religiosity", "How religious the person considers themselves, from a 7-point scale: not at all to slightly (0 to 2), moderately (3), more than moderately (4 to 6)", ["Not at all to slightly", "Moderately", "More than moderately"]),
    ("ai_experience", "Experience with AI in general, from a 5-point scale: none or a little versus moderate to all the time", ["None or a little", "Moderate or more"]),
]


def decode(series, labels):
    """Map stored codes to the numbers on the scale the participant saw, using the variable's own value labels."""
    out = {}
    for code, text in labels.items():
        m = re.fullmatch(r"\s*(\d+)\s*", str(text))
        out[code] = int(m.group(1)) if m else None
    return series.map(out)


def decode_ordinal(series, labels, start=0):
    """For labelled scales without numbers (competence, warmth), number the labels in code order."""
    order = {code: i + start for i, code in enumerate(sorted(labels))}
    return series.map(order)


def demographics(df):
    out = pd.DataFrame(index=df.index)
    out["age_group"] = pd.cut(df["Age"], [17, 44, 59, 69, 200], labels=DEMOGRAPHICS[0][2]).astype(object)
    out["gender"] = df["Gender"].map({1: "Man", 2: "Woman"})
    n_groups = df[["Ethnicity_1", "Ethnicity_2", "Ethnicity_3", "Ethnicity_5", "Ethnicity_6", "Ethnicity_8"]].eq(1).sum(axis=1)
    race = np.where((n_groups == 1) & (df["Ethnicity_3"] == 1), "White", "Another or multiple").astype(object)
    race[(n_groups == 0).to_numpy()] = None
    out["race"] = race
    out["education"] = np.where(df["Education_Att"] >= 4, "College degree or more", "No college degree")
    out["religiosity"] = pd.cut(df["Religious"], [-1, 2, 3, 6], labels=DEMOGRAPHICS[4][2]).astype(object)
    out["ai_experience"] = np.where(df["Exp_AI_General"] >= 3, "Moderate or more", "None or a little")
    return out


def fmt(v):
    return "" if pd.isna(v) else (int(v) if float(v).is_integer() else round(float(v), 2))


def main(path_in, out_dir="public/data"):
    df, meta = pyreadstat.read_sav(path_in)
    vl = meta.variable_value_labels
    df = df.iloc[4:]                      # step 1
    df = df[df["Consent"] == 1]           # step 2
    assert len(df) == 106, len(df)
    df = df.iloc[np.random.default_rng(SEED).permutation(len(df))].reset_index(drop=True)  # step 6
    demo = demographics(df)

    cols, names = {}, []
    for name, *_rest, dec_col, stem in DECISIONS:
        cols[f"needs_quant_{name}"] = df[dec_col]
    for name, *_rest, dec_col, stem in DECISIONS:
        cols[f"trust_doctor_{name}"] = decode(df[f"{stem}_AI_Doc_Trust_2"], vl[f"{stem}_AI_Doc_Trust_2"])
    for name, *_rest, dec_col, stem in DECISIONS:
        cols[f"trust_ai_{name}"] = decode(df[f"{stem}_AI_Doc_Trust_1"], vl[f"{stem}_AI_Doc_Trust_1"])
    for who, raw in [("doctor", "Doc"), ("ai", "AI")]:
        for name, _t, scale, stem in QUALITIES:
            col = stem.format(raw)
            cols[f"{name}_{who}"] = (decode_ordinal(df[col], vl[col]) if scale == "0 to 4" else decode(df[col], vl[col]))

    header = ["participant"] + [d[0] for d in DEMOGRAPHICS] + list(cols)
    with open(f"{out_dir}/study2-ratings.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i in range(len(df)):
            row = [f"P{i + 1:03d}"] + ["" if pd.isna(demo.loc[i, d[0]]) else demo.loc[i, d[0]] for d in DEMOGRAPHICS]
            row += [fmt(c.iloc[i]) for c in cols.values()]
            w.writerow(row)

    with open(f"{out_dir}/study2-codebook.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variable", "description", "scale", "group", "domain_or_type"])
        w.writerow(["participant", "Anonymous participant number, assigned after a seeded shuffle", "P001 to P106", "", ""])
        for name, text, cats in DEMOGRAPHICS:
            w.writerow([name, text, " / ".join(cats), "demographic", ""])
        for name, label, stage, domain, *_ in DECISIONS:
            w.writerow([f"needs_quant_{name}", f"Share of quantitative reasoning (versus intuition) a professional needs to: {label.lower()}", "0 to 100 slider", "needs_quant", f"{stage}; {domain}"])
        for who, who_label in [("doctor", "Doctor"), ("ai", "Medical AI")]:
            for name, label, stage, domain, *_ in DECISIONS:
                w.writerow([f"trust_{who}_{name}", f"{who_label}: how much do you trust each entity to accurately {label.lower()}? (0 to 10)", "0 to 10", "trust", f"{who}; {stage}; {domain}"])
        for who, who_label in [("doctor", "Doctor"), ("ai", "Medical AI")]:
            for name, text, scale, _ in QUALITIES:
                grp = "mind perception item" if name in MIND_ITEMS else "decision-maker quality"
                w.writerow([f"{name}_{who}", f"{who_label}: {text}", scale, grp, who])


if __name__ == "__main__":
    main(sys.argv[1])
