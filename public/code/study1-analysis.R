# Study 1: preregistered tests, from the released data
# Matthew Leitao, Georgetown University dissertation, Chapter 1
#
# Reads study1-ratings.csv (de-identified; see study1-codebook.csv) and runs the paired tests
# for the seven preregistered hypotheses (1.a.1 to 3.a), plus one exploratory test (2.a.2,
# doctor versus AI on quantitative reasoning).
#
# Rating scales: the decision items are 0 to 100 sliders. The recommender ratings are 0 to 10.
# Note: in the raw Qualtrics export the 0 to 10 ratings are stored as codes 1 to 11. The released file
# is already recoded to 0 to 10, so means here are one point lower than in the raw export.
# Differences, t, p and d are identical either way.
#
# Written to read top to bottom. Needs: readr, dplyr, effectsize (only for Cohen's d).
# This version was translated from the original analysis script. The numbers it should print
# are listed in study1-tests.json on the site, which were computed independently in Python.

library(readr)
library(dplyr)
library(effectsize)

d <- read_csv("study1-ratings.csv", show_col_types = FALSE)
stopifnot(nrow(d) == 188)

# Composites: the mean of the matching decisions (as in the original script).
d <- d %>%
  mutate(
    q_diagnosis    = rowMeans(across(c(diagnose_broken_bone, diagnose_depression, diagnose_strep_throat, diagnose_diabetes))),
    q_prescription = rowMeans(across(c(prescribe_pain_medication, prescribe_mental_therapy, prescribe_antibiotics, prescribe_insulin))),
    q_preventative = rowMeans(across(c(prevent_injury_stretching, prevent_mental_meditation, prevent_acute_vitamins, prevent_chronic_diet))),
    q_physical     = rowMeans(across(c(diagnose_broken_bone, diagnose_strep_throat, diagnose_diabetes,
                                       prevent_injury_stretching, prevent_acute_vitamins, prevent_chronic_diet,
                                       prescribe_pain_medication, prescribe_antibiotics, prescribe_insulin))),
    q_mental       = rowMeans(across(c(diagnose_depression, prevent_mental_meditation, prescribe_mental_therapy))),
    q_injury       = rowMeans(across(c(diagnose_broken_bone, prevent_injury_stretching, prescribe_pain_medication))),
    q_acute        = rowMeans(across(c(diagnose_strep_throat, prevent_acute_vitamins, prescribe_antibiotics)))
  )

# One helper so every test is run and reported the same way.
paired <- function(label, a, b) {
  keep <- complete.cases(a, b)
  a <- a[keep]; b <- b[keep]
  t <- t.test(a, b, paired = TRUE)
  dz <- mean(a - b) / sd(a - b)   # Cohen's d for paired data
  data.frame(test = label, n = length(a), mean_a = mean(a), mean_b = mean(b),
             t = unname(t$statistic), df = unname(t$parameter), p = t$p.value, d = dz)
}

results <- bind_rows(
  paired("1.a.1 Diagnostic vs prescriptive",      d$q_diagnosis,    d$q_prescription),
  paired("1.a.2 Diagnostic vs preventative",      d$q_diagnosis,    d$q_preventative),
  paired("1.a.3 Prescriptive vs preventative",    d$q_prescription, d$q_preventative),
  paired("1.b.1 Physical vs mental health",       d$q_physical,     d$q_mental),
  paired("1.b.2 Bodily injury vs acute sickness", d$q_injury,       d$q_acute),
  paired("2.a.1 Intuition: doctor vs AI",         d$intuition_doctor,  d$intuition_ai_general),
  paired("2.a.2 Quantitative: doctor vs AI",      d$capability_doctor, d$capability_ai_general),
  paired("3.a   Trust: doctor vs AI",             d$trust_doctor,   d$trust_ai_general)
)
print(results, digits = 3)

# Check the effect size helper against the effectsize package for the headline test.
print(cohens_d(d$trust_doctor, d$trust_ai_general, paired = TRUE))

# "Person as effect size": how many people trusted the doctor more, the same, or less.
table(sign(d$trust_doctor - d$trust_ai_general),
      dnn = "doctor minus AI (1 = doctor trusted more)")
