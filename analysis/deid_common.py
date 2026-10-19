"""
Shared helpers for the Study 3, 4 and 5 de-identification scripts.

Each study's script reads the author's cleaned SPSS file (not in this repository) and writes two public files:
  public/data/studyN-ratings.csv   one row per person
  public/data/studyN-codebook.csv  one row per column

What is released, and what is not
  Released  the ratings used in the analyses, and five coarse demographic groups (age group, gender, race,
            education, religiosity) so readers can filter and check the models that used them.
  Dropped   response and participant IDs from the survey platform, panel IDs, IP addresses, location,
            timestamps, free-text answers, and every other demographic or attitude question. That includes
            income, employment, disability, mental health, transgender status, first language and birthplace.
  Shuffled  the released participant number (P001, P002, ...) is assigned after a seeded shuffle, so row order
            carries no information about when someone took the survey.
  Missing   people who skipped the demographic block have blank demographic cells. The SPSS file codes them as 0
            on the gender and race indicators; they are blank here. Ages under 18 are data-entry errors and are blank.
"""
import csv

import numpy as np
import pandas as pd

AGE_LABELS = ["18-44", "45-59", "60-69", "70+"]
RELIG_LABELS = ["Not at all to slightly", "Moderately", "More than moderately"]

DEMOGRAPHICS = [
    ("age_group", "Age group, in years", AGE_LABELS),
    ("gender", "Gender, as reported. Only woman and man were reported by 10 or more people, so smaller groups are left blank", ["Woman", "Man"]),
    ("race", "Race, as reported. White only if that is the only group selected; everyone else, including anyone selecting more than one, is combined", ["White", "Another or multiple"]),
    ("education", "Highest education completed, in two groups", ["No college degree", "College degree or more"]),
    ("religiosity", "How religious the person considers themselves, from a 7-point scale: not at all to slightly (0 to 2), moderately (3), more than moderately (4 to 6)", RELIG_LABELS),
]


def demographics(df):
    """Five coarse groups from the cleaned SPSS indicators. Blank for people who skipped the demographic block."""
    has = ~(df["Age"].isna() & df["Religious"].isna())
    out = pd.DataFrame(index=df.index)
    age = df["Age"].where(df["Age"] >= 18)
    out["age_group"] = pd.cut(age, [17, 44, 59, 69, 200], labels=AGE_LABELS).astype(object)
    gender = np.where(df["IsMale"] == 1, "Man", np.where(df["IsNonBinary"] == 1, None, "Woman")).astype(object)
    gender[~has.to_numpy()] = None
    out["gender"] = gender
    others = df[["IsAsian", "IsBlack", "IsHispanic", "IsNativeAmerican", "IsPacificIslander", "IsOther"]].fillna(0).sum(axis=1)
    race = np.where((df["IsWhite"] == 1) & (others == 0), "White", "Another or multiple").astype(object)
    race[~has.to_numpy()] = None
    out["race"] = race
    edu = np.where((df["EduAtt_College"] == 1) | (df["EduAtt_Graduate"] == 1), "College degree or more", "No college degree").astype(object)
    edu[~has.to_numpy()] = None
    out["education"] = edu
    out["religiosity"] = pd.cut(df["Religious"], [-1, 2, 3, 6], labels=RELIG_LABELS).astype(object)
    return out


def fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or (not isinstance(v, str) and pd.isna(v)):
        return ""
    if isinstance(v, str):
        return v
    return int(v) if float(v).is_integer() else round(float(v), 3)


def shuffle(df, seed):
    return df.iloc[np.random.default_rng(seed).permutation(len(df))].reset_index(drop=True)


def write_ratings(path, df, demo, cols):
    """cols is an ordered dict of column name -> Series aligned with df."""
    header = ["participant"] + [d[0] for d in DEMOGRAPHICS] + list(cols)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i in range(len(df)):
            row = [f"P{i + 1:03d}"] + [fmt(demo.loc[i, d[0]]) for d in DEMOGRAPHICS]
            row += [fmt(c.iloc[i]) for c in cols.values()]
            w.writerow(row)


def write_codebook(path, n, rows):
    """rows: (variable, description, scale, group, recommender) tuples."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variable", "description", "scale", "group", "recommender"])
        w.writerow(["participant", "Anonymous participant number, assigned after a seeded shuffle", f"P001 to P{n:03d}", "", ""])
        for name, text, cats in DEMOGRAPHICS:
            w.writerow([name, text, " / ".join(cats), "demographic", ""])
        for r in rows:
            w.writerow(r)
