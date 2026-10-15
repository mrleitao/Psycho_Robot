"""
De-identify the Study 1 survey export for public release.

Input : the raw Qualtrics .sav export (not in this repository; it contains IP addresses,
        coordinates, response IDs and panel IDs).
Output: public/data/study1-ratings.csv and public/data/study1-codebook.csv

What it does
  1. Drops Qualtrics preview and test rows (the first seven rows of the export).
  2. Keeps people who gave consent (Consent == 1). This gives the N = 188 analysed in the dissertation.
  3. Keeps only the analysis variables: 15 decision ratings and 33 recommender ratings.
     Everything else is dropped: IP address, coordinates, timestamps, response, panel and device IDs,
     free-text answers, and all demographic questions.
  4. Recodes the 33 recommender ratings from the export's stored codes (1 to 11) to the 0 to 10 scale
     participants saw. Qualtrics stores the scale labels "0" to "10" as codes 1 to 11. Differences and
     effect sizes are unaffected, but means shift by one point.
  5. Replaces response IDs with participant numbers assigned after a seeded shuffle,
     so row order carries no information about when someone took the survey.

Usage: python3 analysis/study1-deidentify.py path/to/raw.sav
Needs: pandas, pyreadstat, numpy
"""
import csv
import sys

import numpy as np
import pyreadstat

SEED = 2023

# Original Qualtrics name -> public name. Decision items are 0-100 sliders.
DECISIONS = {
    "Int_Quant_1": ("prevent_injury_stretching", "Recommend stretching to prevent injury", "preventative", "bodily injury"),
    "Int_Quant_2": ("diagnose_broken_bone", "Diagnose a broken bone", "diagnostic", "bodily injury"),
    "Int_Quant_3": ("prescribe_knee_surgery", "Recommend knee surgery", "prescriptive", "bodily injury (surgery, not in composite)"),
    "Int_Quant_4": ("prescribe_pain_medication", "Prescribe pain medication", "prescriptive", "bodily injury"),
    "Int_Quant_5": ("prevent_mental_meditation", "Recommend meditation", "preventative", "mental health"),
    "Int_Quant_6": ("diagnose_depression", "Diagnose depression", "diagnostic", "mental health"),
    "Int_Quant_7": ("prescribe_mental_therapy", "Prescribe antidepressants and therapy", "prescriptive", "mental health"),
    "Int_Quant_8": ("prevent_acute_vitamins", "Recommend vitamin C and zinc", "preventative", "acute sickness"),
    "Int_Quant_9": ("diagnose_strep_throat", "Diagnose strep throat", "diagnostic", "acute sickness"),
    "Int_Quant_10": ("prescribe_antibiotics", "Prescribe antibiotics", "prescriptive", "acute sickness"),
    "Int_Quant_11": ("prevent_chronic_diet", "Recommend a strict diet", "preventative", "chronic sickness"),
    "Int_Quant_12": ("diagnose_diabetes", "Diagnose diabetes", "diagnostic", "chronic sickness"),
    "Int_Quant_13": ("prescribe_insulin", "Prescribe insulin", "prescriptive", "chronic sickness"),
    "Int_Quant_14": ("prevent_wellbeing", "Recommend general wellbeing improvements", "preventative", "general (not in composite)"),
    "Int_Quant_15": ("medical_general", "Medical decisions in general", "general", "general (not in composite)"),
}

# public id, label, type, trust column, capability column, intuition column (as named in the raw export)
RECOMMENDERS = [
    ("doctor", "Doctor", "human", "Decision_Maker_TR_Doctor_General", "DM_QR_Doctor_General", "DM_IN_Doctor_General"),
    ("nurse", "Nurse", "human", "Decision_Maker_TR_Nurse", "DM_QR_Nurse", "Decision_Maker_IN_Nurse"),
    ("doctor_remote", "Doctor, remote visit", "human", "Decision_Maker_TR_Doctor_Remote", "DM_QR_Doctor_Remote", "Decision_Maker_IN_Doctor_Remote"),
    ("therapist", "Therapist", "human", "Decision_Maker_TR_Therapist", "DM_QR_Therapist", "Decision_Maker_IN_Therapist"),
    ("personal_trainer", "Personal trainer", "human", "Decision_Maker_TR_PersonalTrainer", "DM_QR_PersonalTrainer", "Decision_Maker_IN_PersonalTrainer"),
    ("layperson", "Layperson", "human", "Decision_Maker_TR_Lay", "DM_QR_Lay", "Decision_Maker_IN_Lay"),
    ("doctor_using_ai", "Doctor using AI", "hybrid", "Decision_Maker_TR_Doctor_AI", "DM_QR_Doctor_AI", "Decision_Maker_IN_Doctor_AI"),
    ("ai_general", "AI, general", "ai", "Decision_Maker_TR_AI_General", "DM_QR_AI_General", "Decision_Maker_IN_AI_General"),
    ("ai_diagnostic", "AI diagnostic tool", "ai", "Decision_Maker_TR_AI_Diagonostic", "DM_QR_AI_Diagonstic", "Decision_Maker_IN_AI_Diagonstic"),
    ("ai_chatbot", "AI chatbot", "ai", "Decision_Maker_TR_AI_Chatbot", "DM_QR_AI_Chatbot", "Decision_Maker_IN_AI_Chatbot"),
    ("ai_fitness", "AI fitness coach", "ai", "Decision_Maker_TR_AI_Fitness", "Q29_AI_Fitness", "Decision_Maker_IN_AI_Fitness"),
]
MEASURES = [("trust", 3, "How much do you trust each entity to make recommendations about health? (0 to 10)"),
            ("capability", 4, "How capable is each entity of using quantitative reasoning to make recommendations about health? (0 to 10)"),
            ("intuition", 5, "How capable is each entity of using intuition to make recommendations about health? (0 to 10)")]


def main(path_in, out_dir="public/data"):
    df, _ = pyreadstat.read_sav(path_in)
    df = df.iloc[7:]                      # step 1: preview and test rows
    df = df[df["Consent"] == 1]           # step 2: consent
    assert len(df) == 188, len(df)
    df = df.iloc[np.random.default_rng(SEED).permutation(len(df))].reset_index(drop=True)  # step 5

    header = ["participant"] + [v[0] for v in DECISIONS.values()]
    header += [f"{m}_{r[0]}" for r in RECOMMENDERS for m, _, _ in MEASURES]
    rows = []
    for i, r in df.iterrows():
        row = [f"P{i + 1:03d}"]
        row += [fmt(r[c]) for c in DECISIONS]
        row += [fmt(r[rec[idx]] - 1) for rec in RECOMMENDERS for _, idx, _ in MEASURES]  # step 4
        rows.append(row)
    with open(f"{out_dir}/study1-ratings.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

    with open(f"{out_dir}/study1-codebook.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variable", "description", "scale", "group", "domain_or_type"])
        w.writerow(["participant", "Anonymous participant number, assigned after a seeded shuffle", "P001 to P188", "", ""])
        for name, label, kind, domain in DECISIONS.values():
            w.writerow([name, f"Share of quantitative reasoning (versus intuition) a professional needs to: {label.lower()}", "0 to 100 slider", kind, domain])
        for rec in RECOMMENDERS:
            for m, _, text in MEASURES:
                w.writerow([f"{m}_{rec[0]}", f"{rec[1]}: {text}", "0 to 10", m, rec[2]])


def fmt(v):
    return "" if np.isnan(v) else (int(v) if float(v).is_integer() else round(float(v), 2))


if __name__ == "__main__":
    main(sys.argv[1])
