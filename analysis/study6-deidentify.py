"""
De-identify the Study 6 (15-day sleep and phone-in-bed advice study) data for public release.

Input : the author's cleaned long-format SPSS file, Health_Algorithm_Behavior_Final.sav (not in this repository).
        It holds Prolific IDs, survey session IDs, timestamps, free-text answers, the sleep questionnaire and a
        long demographic block, none of which are released apart from five coarse demographic groups.
Output: public/data/study6-ratings.csv (one row per person per day) and public/data/study6-codebook.csv

Design: 510 people completed at least one daily survey (49 more are in the file with a baseline row and nothing else, and are
dropped). On day 8, 455 of the 510 were randomly shown the sleep and device-in-bed advice from a doctor or an AI; the other 55
never got the advice and have no recommender.
Each person's baseline is their mean on days 1 to 7. Weight on advice is how far a day's value moved from that
baseline toward the recommendation (8.25 hours of sleep, 15 minutes on a device in bed), capped at -2 and 2.

Coding note: in the SPSS file the recommender column IsAlg is coded 1 and 2 and carries the labels 1 = AI, 2 = Doctor.
The data show the opposite (mind perception is about one point higher in group 1, and the author's R code and the
dissertation treat the AI as the higher-coded group), so group 1 is the doctor and group 2 is the AI here.

What it does
  1. Reads the daily file and checks the weight-on-advice columns by recomputing them from sleep hours and minutes.
  2. Keeps each day's sleep hours, minutes on a device in bed, and the two weight-on-advice values, with the day,
     whether the day was before or after the advice, and the recommender.
  3. Keeps the seven mind-perception items from the final survey (and their mean) for the 412 people who answered.
  4. Adds five coarse demographic groups. Everything else is dropped.
  5. Replaces participant numbers with new ones assigned after a seeded shuffle of people, and sorts rows by day.

Usage: python3 analysis/study6-deidentify.py path/to/Health_Algorithm_Behavior_Final.sav
Needs: pandas, pyreadstat, numpy
"""
import csv
import sys

import numpy as np
import pandas as pd
import pyreadstat

from deid_common import AGE_LABELS, RELIG_LABELS, DEMOGRAPHICS, fmt

SEED = 2026
MIND = [
    ("mind_anticipate", "Decision_Maker.Antic", "Mind perception 1: can anticipate my future health needs"),
    ("mind_account", "Decision_Maker.Acct", "Mind perception 2: can account for my health needs"),
    ("mind_feelings", "Decision_Maker.Under", "Mind perception 3: understands my feelings about my health"),
    ("mind_familiar", "Decision_Maker.Fam", "Mind perception 4: its process reminds me of other health recommendations"),
    ("mind_capable", "Decision_Maker.Gen", "Mind perception 5: capable of accurate health recommendations in general"),
    ("mind_transparent", "Decision_Maker.Trans", "Mind perception 6: its decision process is transparent"),
    ("mind_process", "Decision_Maker.PUnd", "Mind perception 7: I understand how it comes up with a recommendation"),
]


def person_demographics(p):
    age = pd.to_numeric(p["Age"], errors="coerce").where(lambda s: s >= 18)
    has = pd.to_numeric(p["Age"], errors="coerce").notna() | p["Relig"].notna()
    out = pd.DataFrame(index=p.index)
    out["age_group"] = pd.cut(age, [17, 44, 59, 69, 200], labels=AGE_LABELS).astype(object)
    g = np.where(p["IsMale"] == 1, "Man", np.where(p["IsNonBinary"] == 1, None, "Woman")).astype(object)
    g[~has.to_numpy()] = None
    out["gender"] = g
    others = p[["IsAsian", "IsBlack", "IsHispanic", "IsNativeAmerican", "IsPacificIslander", "IsOther"]].fillna(0).sum(axis=1)
    r = np.where((p["IsWhite"] == 1) & (others == 0), "White", "Another or multiple").astype(object)
    r[~has.to_numpy()] = None
    out["race"] = r
    e = np.where((p["EduAtt_College"] == 1) | (p["EduAtt_Graduate"] == 1), "College degree or more", "No college degree").astype(object)
    e[~has.to_numpy()] = None
    out["education"] = e
    out["religiosity"] = pd.cut(p["Relig"], [0, 3, 4, 7], labels=RELIG_LABELS).astype(object)
    return out


def main(path_in, out_dir="public/data"):
    df, _ = pyreadstat.read_sav(path_in)
    assert len(df) == 5854 and df["PROLIFIC_PID"].nunique() == 559
    # 49 people have a baseline row but no daily survey at all (no day, no outcome, no assignment): they carry no data.
    df = df[df["Day"].notna()].copy()
    assert len(df) == 5805 and df["PROLIFIC_PID"].nunique() == 510
    # Recoding from the SPSS file: Intervention 1 = before, 2 = after; IsAlg 1 = doctor, 2 = AI (see note above).
    df["after"] = (df["Intervention"] == 2).astype(int)
    df["recommender"] = df["IsAlg"].map({1.0: "Doctor", 2.0: "AI"})
    # Recompute weight on advice and check it against the file.
    base = df[df["Day"] <= 7].groupby("PROLIFIC_PID").agg(s=("Sleep_Hours_4", "mean"), b=("DIB_Minutes_1", "mean"))
    x = df.join(base, on="PROLIFIC_PID")
    ws = ((x["Sleep_Hours_4"] - x["s"]) / (8.25 - x["s"])).clip(-2, 2)
    with np.errstate(all="ignore"):
        wd = ((x["DIB_Minutes_1"] - x["b"]) / (15 - x["b"])).clip(-2, 2)
    wd = wd.where(~np.isinf(wd))
    assert (ws - df["Weight_On_Advice_Sleep_Alternative"]).abs().max() < 1e-9
    both = wd.notna() & df["Weight_On_Advice_DIB_Alternative"].notna()
    assert (wd[both] - df["Weight_On_Advice_DIB_Alternative"][both]).abs().max() < 1e-9
    df["woa_sleep"] = ws
    df["woa_device"] = df["Weight_On_Advice_DIB_Alternative"]
    df["mind_perception"] = df[[m[1] for m in MIND]].mean(axis=1, skipna=False)
    assert (df["mind_perception"] - df["Mind_Perception"]).abs().max() < 1e-9

    ids = np.random.default_rng(SEED).permutation(df["PROLIFIC_PID"].unique())
    num = {pid: f"P{i + 1:03d}" for i, pid in enumerate(ids)}
    df["participant"] = df["PROLIFIC_PID"].map(num)
    first = df.drop_duplicates("PROLIFIC_PID").set_index("PROLIFIC_PID")
    demo = person_demographics(first)
    for c in demo.columns:
        df[c] = df["PROLIFIC_PID"].map(demo[c])
    df = df.sort_values(["participant", "Day"]).reset_index(drop=True)

    cols = (["participant"] + [d[0] for d in DEMOGRAPHICS]
            + ["day", "phase", "recommender", "sleep_hours", "device_minutes", "woa_sleep", "woa_device", "mind_perception"]
            + [m[0] for m in MIND])
    df["day"] = df["Day"].astype(int)
    df["phase"] = np.where(df["after"] == 1, "After advice", "Before advice")
    df["sleep_hours"] = df["Sleep_Hours_4"]
    df["device_minutes"] = df["DIB_Minutes_1"]
    for k, src, _ in MIND:
        df[k] = df[src]
    with open(f"{out_dir}/study6-ratings.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for _, r in df[cols].iterrows():
            w.writerow([fmt(r[c]) for c in cols])
    n = df["participant"].nunique()
    rows = [
        ("day", "Study day, 1 to 14. Day 14 is the final survey, which also held the mind-perception questions", "1 to 14", "design", ""),
        ("phase", "Whether the advice had been given yet. It was shown on day 8, so days 1 to 7 are before and days 8 to 14 are after", "Before advice / After advice", "design", ""),
        ("recommender", "Who gave the advice (random assignment). Blank for the 55 people who never got the advice", "Doctor / AI", "condition", ""),
        ("sleep_hours", "Hours slept the night before, from the daily survey", "hours", "daily outcome", ""),
        ("device_minutes", "Minutes spent on a device in bed the night before, from the daily survey", "minutes", "daily outcome", ""),
        ("woa_sleep", "Weight on advice for sleep: how far the day's sleep moved from the person's days 1 to 7 average toward 8.25 hours, as a share of the distance, capped at -2 and 2", "-2 to 2", "weight on advice", ""),
        ("woa_device", "Weight on advice for device time: the same, toward 15 minutes. Blank when the person had no days 1 to 7 average or no value that day", "-2 to 2", "weight on advice", ""),
        ("mind_perception", "Mean of the seven mind-perception items, from the final survey. Blank for people who did not answer (it is the same on every day for a person)", "0 to 10", "mind perception", ""),
    ] + [(k, t, "0 to 10", "mind perception item", "") for k, _, t in MIND]
    with open(f"{out_dir}/study6-codebook.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variable", "description", "scale", "group", "recommender"])
        w.writerow(["participant", "Anonymous participant number, assigned after a seeded shuffle", f"P001 to P{n:03d}", "", ""])
        for name, text, cats in DEMOGRAPHICS:
            w.writerow([name, text, " / ".join(cats), "demographic", ""])
        for r in rows:
            w.writerow(r)
    print(n, "people", len(df), "rows")


if __name__ == "__main__":
    main(sys.argv[1])
