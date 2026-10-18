# Study 2: preregistered tests and the main mixed models, from the released data
# Matthew Leitao, Georgetown University dissertation, Chapter 1
#
# Reads study2-ratings.csv (de-identified; see study2-codebook.csv).
# Each person rated trust in a doctor and in an AI for twelve medical decisions, how much quantitative
# reasoning each decision needs, and the doctor and the AI on several qualities.
#
# Scales: the released file uses the scales people saw. Trust and most ratings run 0 to 10; competence and
# warmth run 0 to 4; the need for quantitative reasoning runs 0 to 100. The original notebook kept some of the
# survey's stored codes (for example competence as 4 to 8), so intercepts and means differ from the notebook.
# Differences, correlations and slopes are identical either way.
# Age is released in four bands, so age enters as the band number (1 = 18 to 44, ... 4 = 70 and over).
#
# Needs: readr, dplyr, tidyr, lme4, lmerTest, effectsize.
# This was translated from the original notebook and has not been run on the released file; the numbers it should
# print are in study2-full.json on the site, computed in Python (analysis/study2-full-results.py).

library(readr); library(dplyr); library(tidyr); library(lme4); library(lmerTest); library(effectsize)

d <- read_csv("study2-ratings.csv", show_col_types = FALSE)
stopifnot(nrow(d) == 106)

decisions <- c("prevent_injury_stretching", "diagnose_broken_bone", "prescribe_pain_medication",
               "prevent_mental_meditation", "diagnose_depression", "prescribe_mental_therapy",
               "prevent_acute_vitamins", "diagnose_strep_throat", "prescribe_antibiotics",
               "prevent_chronic_diet", "diagnose_diabetes", "prescribe_insulin")

# H1: trust in a doctor versus an AI, one paired t test per decision
paired <- function(a, b) {
  t <- t.test(a, b, paired = TRUE)
  data.frame(n = sum(complete.cases(a, b)), diff = mean(a - b, na.rm = TRUE), t = unname(t$statistic),
             df = unname(t$parameter), p = t$p.value, d = mean(a - b, na.rm = TRUE) / sd(a - b, na.rm = TRUE))
}
h1 <- bind_rows(lapply(decisions, function(k) cbind(decision = k, paired(d[[paste0("trust_doctor_", k)]], d[[paste0("trust_ai_", k)]]))))
print(h1, digits = 3)

# Ratings of the doctor and the AI on the qualities
for (q in c("quantitative_reasoning", "intuition", "competence", "warmth"))
  print(cbind(quality = q, paired(d[[paste0(q, "_doctor")]], d[[paste0(q, "_ai")]])), digits = 3)

# Long file: one row per person, decision and recommender
mind_items <- c("general_accuracy", "anticipate_needs", "understand_feelings", "account_for_needs",
                "familiar_process", "transparent_process", "understand_process")
long <- bind_rows(lapply(c("doctor", "ai"), function(who) {
  out <- d %>% transmute(ID = participant, DM = who, IsDoc = as.numeric(who == "doctor"),
    Intuition = .data[[paste0("intuition_", who)]], Quant = .data[[paste0("quantitative_reasoning_", who)]],
    Warmth = .data[[paste0("warmth_", who)]], Competence = .data[[paste0("competence_", who)]],
    AgeGroup = as.numeric(factor(age_group, levels = c("18-44", "45-59", "60-69", "70+"))), IsMale = as.numeric(gender == "Man"))
  for (k in decisions) out[[paste0("T_", k)]] <- d[[paste0("trust_", who, "_", k)]]
  for (k in decisions) out[[paste0("N_", k)]] <- d[[paste0("needs_quant_", k)]]
  out
})) %>%
  pivot_longer(starts_with("T_"), names_to = "Decision", names_prefix = "T_", values_to = "Trust") %>%
  mutate(Int_Quant = NA_real_)
# Attach each decision's own need-for-quantitative-reasoning rating
need <- d %>% select(ID = participant, starts_with("needs_quant_")) %>%
  pivot_longer(-ID, names_to = "Decision", names_prefix = "needs_quant_", values_to = "Int_Quant")
long <- long %>% select(-Int_Quant, -starts_with("N_")) %>% left_join(need, by = c("ID", "Decision"))

# H2: does the doctor-versus-AI gap depend on how much quantitative reasoning the decision needs?
m2 <- lmer(Trust ~ IsDoc * Int_Quant + (1 + Int_Quant | ID), data = long)
print(summary(m2))

# Add intuition, quantitative reasoning, warmth, competence, age band and gender
m3 <- lmer(Trust ~ IsDoc * Int_Quant + Intuition + Quant + Warmth + Competence + AgeGroup + IsMale + (1 + Int_Quant | ID), data = long)
print(summary(m3))
