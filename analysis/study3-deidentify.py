"""
De-identify the Study 3 survey file for public release.

Input : the author's cleaned SPSS file for Study 3 (not in this repository).
Output: public/data/study3-ratings.csv and public/data/study3-codebook.csv

What it does
  1. Keeps the 609 people who answered the trust question. The cleaned file has 664 rows; the other 55 left
     before the ratings and are not in the dissertation.
  2. Keeps the condition each person was randomly shown (humanlike AI, standard AI or doctor) and the ratings:
     trust, belief, warmth, competence, how humanlike the AI seemed (AI conditions only) and a comparison item.
  3. Adds five coarse demographic groups (see deid_common.py). Everything else is dropped.
  4. Replaces participant numbers with new ones assigned after a seeded shuffle.

Usage: python3 analysis/study3-deidentify.py path/to/study3.sav
Needs: pandas, pyreadstat, numpy
"""
import sys

import pandas as pd
import pyreadstat

from deid_common import shuffle, demographics, write_ratings, write_codebook

SEED = 2024
COND = {1: "Humanlike AI", 2: "Standard AI", 3: "Doctor"}


def main(path_in, out_dir="public/data"):
    df, _ = pyreadstat.read_sav(path_in)
    df = df[df["Trust"].notna()]
    assert len(df) == 609, len(df)
    df = shuffle(df, SEED)
    demo = demographics(df)
    cols = {
        "condition": df["Condition"].map(COND),
        "trust": df["Trust"],
        "belief": df["Believe"],
        "warmth": df["Warmth"],
        "competence": df["Competent"],
        "humanlike": df["Humanlike"],
        "compare": df["Compare"],
    }
    write_ratings(f"{out_dir}/study3-ratings.csv", df, demo, cols)
    write_codebook(f"{out_dir}/study3-codebook.csv", len(df), [
        ("condition", "Which recommender the person was randomly shown", "Humanlike AI / Standard AI / Doctor", "condition", ""),
        ("trust", "How much would you trust the recommendation?", "-3 (completely distrust) to 3 (complete trust)", "outcome", ""),
        ("belief", "How much would you believe the recommendation would improve your health?", "-3 (completely disbelieve) to 3 (completely believe)", "outcome", ""),
        ("warmth", "How much does warm and friendly describe the recommender?", "0 (does not describe at all) to 4 (describes completely)", "perception", ""),
        ("competence", "How much does competent and capable describe the recommender?", "0 (does not describe at all) to 4 (describes completely)", "perception", ""),
        ("humanlike", "How humanlike is the AI? Asked in the two AI conditions only", "0 (not humanlike at all) to 4 (completely humanlike)", "perception", ""),
        ("compare", "Comparison item from the survey (wording is not stored in the data file)", "-3 to 3", "other", ""),
    ])


if __name__ == "__main__":
    main(sys.argv[1])
