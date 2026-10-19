"""
De-identify the Study 4 survey file for public release.

Input : the author's cleaned long-format SPSS file for Study 4 (not in this repository). It has three rows per
        person, one for each recommender.
Output: public/data/study4-ratings.csv (one row per person) and public/data/study4-codebook.csv

Design: each person first read one randomly assigned vignette and rated it. That first rating is the
between-subjects part (columns ending _first). Everyone then rated all three recommenders, in a counterbalanced
order: the within-subjects part (columns ending _humanlike, _standard, _doctor). Voice was on in every condition.

What it does
  1. Keeps the 559 people in the file and reshapes to one row per person.
  2. Keeps the ratings used in the analyses and five coarse demographic groups (see deid_common.py).
  3. Drops everything else, including the survey platform's IDs, free text and all other questions.
  4. Replaces participant numbers with new ones assigned after a seeded shuffle.

Usage: python3 analysis/study4-deidentify.py path/to/study4-long.sav
Needs: pandas, pyreadstat, numpy
"""
import sys

import pandas as pd
import pyreadstat

from deid_common import shuffle, demographics, write_ratings, write_codebook

SEED = 2024
COND = {1: "Humanlike AI", 2: "Standard AI", 3: "Doctor"}
SUFFIX = {1: "humanlike", 2: "standard", 3: "doctor"}
ORDER = {1: "HDN", 2: "HND", 3: "DHN", 4: "NHD", 5: "DNH", 6: "NDH"}  # D doctor, H humanlike AI, N standard AI
WITHIN = [("trust", "Trust_WS"), ("belief", "Believe_WS"), ("warmth", "Warm_WS"), ("competence", "Competent_WS"),
          ("humanlike", "Humanlike_WS"), ("appropriate", "Appropriate_WS"), ("compare", "Compare_WS")]


def main(path_in, out_dir="public/data"):
    long, _ = pyreadstat.read_sav(path_in)
    first = long.drop_duplicates("Participant_Num").reset_index(drop=True)
    assert len(first) == 559, len(first)
    wide = first.copy()
    for k, suf in SUFFIX.items():
        part = long[long["Cond"] == k].set_index("Participant_Num")
        for name, col in WITHIN:
            wide[f"{name}_{suf}"] = wide["Participant_Num"].map(part[col])
    df = shuffle(wide, SEED)
    demo = demographics(df)
    cols = {
        "first_recommender": df["Condition"].map(COND),
        "order": df["WS_Condition"].map(ORDER),
        "trust_first": df["Trust"],
        "belief_first": df["Believe"],
        "warmth_first": df["Warmth"],
        "competence_first": df["Competent"],
        "humanlike_first": df["Humanlike"],
        "appropriate_ai": df["Appropriate_AI"],
    }
    for k, suf in SUFFIX.items():
        for name, _ in WITHIN:
            if name == "humanlike" and k == 3:
                continue
            if name == "appropriate" and k == 3:
                continue
            cols[f"{name}_{suf}"] = df[f"{name}_{suf}"]
    write_ratings(f"{out_dir}/study4-ratings.csv", df, demo, cols)
    rows = [
        ("first_recommender", "Which recommender the person was randomly shown first (the between-subjects part)", "Humanlike AI / Standard AI / Doctor", "condition", ""),
        ("order", "Order in which the person then saw the three recommenders: D doctor, H humanlike AI, N standard AI", "HDN / HND / DHN / NHD / DNH / NDH", "condition", ""),
        ("trust_first", "Trust in the first recommender's recommendation", "-3 (completely distrust) to 3 (complete trust)", "between-subjects outcome", "first"),
        ("belief_first", "Belief that the first recommender's recommendation would improve health", "-3 (completely disbelieve) to 3 (completely believe)", "between-subjects outcome", "first"),
        ("warmth_first", "Warm and friendly, first recommender", "0 to 4", "between-subjects perception", "first"),
        ("competence_first", "Competent and capable, first recommender", "0 to 4", "between-subjects perception", "first"),
        ("humanlike_first", "How humanlike the first recommender was, asked when it was an AI", "0 to 4", "between-subjects perception", "first"),
        ("appropriate_ai", "How appropriate is it to use AI to make these health decisions", "-3 (extremely inappropriate) to 3 (extremely appropriate)", "attitude", ""),
    ]
    names = {"trust": ("Trust in the recommendation", "-3 to 3"), "belief": ("Belief the recommendation would improve health", "-3 to 3"),
             "warmth": ("Warm and friendly", "0 to 4"), "competence": ("Competent and capable", "0 to 4"),
             "humanlike": ("How humanlike the AI was (AI conditions only)", "0 to 4"),
             "appropriate": ("How appropriate this AI is for these decisions (AI conditions only)", "-3 to 3"),
             "compare": ("Comparison item from the survey (wording not stored in the data file)", "-3 to 3")}
    who = {"humanlike": "Humanlike AI", "standard": "Standard AI", "doctor": "Doctor"}
    for k, suf in SUFFIX.items():
        for name, _ in WITHIN:
            if name in ("humanlike", "appropriate") and k == 3:
                continue
            text, scale = names[name]
            rows.append((f"{name}_{suf}", f"{who[suf]}: {text}", scale, "within-subjects", who[suf]))
    write_codebook(f"{out_dir}/study4-codebook.csv", len(df), rows)


if __name__ == "__main__":
    main(sys.argv[1])
