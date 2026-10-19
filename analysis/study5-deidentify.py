"""
De-identify the Study 5 survey file for public release.

Input : the author's cleaned wide SPSS file for Study 5 (not in this repository). It holds the survey platform's
        response IDs, participant IDs and free-text explanations, none of which are released.
Output: public/data/study5-ratings.csv (one row per person) and public/data/study5-codebook.csv

Design: everyone rated all three recommenders (doctor, humanlike AI, standard AI). Half also heard a voice
recording with the written recommendation (voiced); half read it only (written). Voice is the between-person factor.

What it does
  1. Keeps the 854 people in the file.
  2. Keeps, for each recommender: trust, belief, warmth, competence, appropriateness, a comparison item, the seven
     mind-perception items, praise and blame (and, for the AI conditions, how humanlike they seemed). Also keeps
     each person's ranking of the three recommenders on trustworthiness.
  3. Adds five coarse demographic groups (see deid_common.py). Everything else is dropped.
  4. Replaces participant numbers with new ones assigned after a seeded shuffle.

Usage: python3 analysis/study5-deidentify.py path/to/study5.sav
Needs: pandas, pyreadstat, numpy
"""
import sys

import pyreadstat

from deid_common import shuffle, demographics, write_ratings, write_codebook

SEED = 2024
SUFFIX = {1: "humanlike", 2: "standard", 3: "doctor"}
WHO = {"humanlike": "Humanlike AI", "standard": "Standard AI", "doctor": "Doctor"}
# public name, raw stem, description, scale
ITEMS = [
    ("trust", "Trust", "Trust in the recommendation", "-3 to 3"),
    ("belief", "Believe", "Belief the recommendation would improve health", "-3 to 3"),
    ("warmth", "Warm", "Warm and friendly", "0 to 4"),
    ("competence", "Competent", "Competent and capable", "0 to 4"),
    ("appropriate", "Appropriate", "How appropriate this recommender is for these health decisions", "-3 to 3"),
    ("compare", "Compare", "Comparison item from the survey (wording not stored in the data file)", "-3 to 3"),
    ("mind_capable", "Capable", "Mind perception 1: capable of accurate health recommendations in general", "0 to 10"),
    ("mind_anticipate", "Anticpate", "Mind perception 2: can anticipate my future health needs", "0 to 10"),
    ("mind_feelings", "Understand", "Mind perception 3: understands my feelings about my health", "0 to 10"),
    ("mind_account", "Account", "Mind perception 4: can account for my health needs", "0 to 10"),
    ("mind_familiar", "Remind", "Mind perception 5: its process reminds me of other health recommendations", "0 to 10"),
    ("mind_transparent", "Transp", "Mind perception 6: its decision process is transparent", "0 to 10"),
    ("mind_process", "PUnder", "Mind perception 7: I understand how it comes up with a recommendation", "0 to 10"),
    ("praise", "Praise", "How much praise the recommender deserves if the recommendation works", "0 to 100"),
    ("blame", "Blame", "How much blame the recommender deserves if the recommendation fails", "0 to 100"),
    ("humanlike", "Humanlike", "How humanlike the AI was (AI conditions only)", "0 to 4"),
]


def main(path_in, out_dir="public/data"):
    df, _ = pyreadstat.read_sav(path_in)
    assert len(df) == 854, len(df)
    df = shuffle(df, SEED)
    demo = demographics(df)
    cols = {"voice": df["IsVoiced"].astype(str).map({"0": "Written only", "1": "Written and voiced"})}
    rows = [("voice", "Whether the person also heard a voice recording with the written recommendation (random assignment)", "Written only / Written and voiced", "condition", "")]
    for k, suf in SUFFIX.items():
        for name, stem, text, scale in ITEMS:
            col = f"Cond_{k}.{stem}_WS"
            if col not in df.columns:
                continue
            cols[f"{name}_{suf}"] = df[col]
            rows.append((f"{name}_{suf}", f"{WHO[suf]}: {text}", scale, "mind perception item" if name.startswith("mind_") else "rating", WHO[suf]))
    for suf, col in [("humanlike", "Rank_Trust_Humanlike"), ("standard", "Rank_Trust_NonHumanlike"), ("doctor", "Rank_Trust_Human")]:
        cols[f"rank_trust_{suf}"] = df[col]
        rows.append((f"rank_trust_{suf}", f"Rank of the {WHO[suf]} on trustworthiness among the three (1 = most trustworthy)", "1 to 3", "ranking", WHO[suf]))
    write_ratings(f"{out_dir}/study5-ratings.csv", df, demo, cols)
    write_codebook(f"{out_dir}/study5-codebook.csv", len(df), rows)


if __name__ == "__main__":
    main(sys.argv[1])
