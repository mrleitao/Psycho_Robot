# Study 4: first-rating comparisons and the three-way side-by-side comparison, from the released data
# Matthew Leitao, Georgetown University dissertation, Chapter 3
#
# Reads study4-ratings.csv (de-identified; see study4-codebook.csv). One row per person.
# Part 1 (between people): each person was randomly shown one recommender first and rated it; those ratings
# are the columns ending _first, and first_recommender says which one.
# Part 2 (within people): everyone then rated all three recommenders in a random order (columns ending
# _humanlike, _standard, _doctor).
#
# Age is released in four bands. Part 1 d uses the pooled standard deviation; Part 2 uses dz.
#
# Needs: readr, dplyr, tidyr, lme4, lmerTest, effectsize, afex.
# This was translated from the Python analysis and has not been run in R; the numbers it should print are in
# study4-full.json on the site (analysis/study4-full-results.py).

library(readr); library(dplyr); library(tidyr); library(lme4); library(lmerTest); library(effectsize); library(afex)

d <- read_csv("study4-ratings.csv", show_col_types = FALSE)
stopifnot(nrow(d) == 559)

# ---- Part 1
d$first_recommender <- factor(d$first_recommender, levels = c("Humanlike AI", "Standard AI", "Doctor"))
welch <- function(x, y) {
  t <- t.test(x, y)
  data.frame(diff = mean(x, na.rm = TRUE) - mean(y, na.rm = TRUE), t = unname(t$statistic), df = unname(t$parameter), p = t$p.value,
             d = cohens_d(x, y, pooled_sd = TRUE)$Cohens_d)
}
for (v in c("trust", "belief", "warmth", "competence")) {
  x <- d[[paste0(v, "_first")]]; g <- d$first_recommender
  cat("\n== Part 1:", v, "\n")
  print(summary(aov(x ~ g)))
  print(rbind(
    cbind(test = "Doctor versus both AIs", welch(x[g == "Doctor"], x[g != "Doctor"])),
    cbind(test = "Humanlike versus standard AI", welch(x[g == "Humanlike AI"], x[g == "Standard AI"])),
    cbind(test = "Doctor versus standard AI", welch(x[g == "Doctor"], x[g == "Standard AI"])),
    cbind(test = "Doctor versus humanlike AI", welch(x[g == "Doctor"], x[g == "Humanlike AI"]))), digits = 3)
}
# Manipulation check, first rating
print(welch(d$humanlike_first[d$first_recommender == "Humanlike AI"], d$humanlike_first[d$first_recommender == "Standard AI"]), digits = 3)

# ---- Part 2
paired <- function(a, b) {
  t <- t.test(a, b, paired = TRUE)
  data.frame(n = sum(complete.cases(a, b)), diff = mean(a - b, na.rm = TRUE), t = unname(t$statistic), df = unname(t$parameter),
             p = t$p.value, p_bonferroni = min(1, 3 * t$p.value), dz = mean(a - b, na.rm = TRUE) / sd(a - b, na.rm = TRUE))
}
for (v in c("trust", "belief", "warmth", "competence")) {
  h <- d[[paste0(v, "_humanlike")]]; s <- d[[paste0(v, "_standard")]]; o <- d[[paste0(v, "_doctor")]]
  cat("\n== Part 2:", v, "\n")
  print(rbind(cbind(test = "Humanlike versus standard AI", paired(h, s)), cbind(test = "Doctor versus standard AI", paired(o, s)),
              cbind(test = "Doctor versus humanlike AI", paired(o, h))), digits = 3)
}

# Repeated-measures ANOVA on the people who rated all three (Greenhouse-Geisser correction)
for (v in c("trust", "belief")) {
  w <- d %>% select(participant, humanlike = all_of(paste0(v, "_humanlike")), standard = all_of(paste0(v, "_standard")), doctor = all_of(paste0(v, "_doctor"))) %>%
    drop_na() %>% pivot_longer(-participant, names_to = "recommender", values_to = "rating")
  cat("\n== repeated-measures ANOVA:", v, "\n")
  print(aov_ez("participant", "rating", w, within = "recommender", anova_table = list(correction = "GG", es = "pes")))
}

# Mixed models, Part 2 (reference: humanlike AI; age band and gender as in the dissertation)
long <- d %>% mutate(AgeGroup = as.numeric(factor(age_group, levels = c("18-44", "45-59", "60-69", "70+"))), IsMale = as.numeric(gender == "Man")) %>%
  pivot_longer(c(starts_with("trust_"), starts_with("belief_"), starts_with("warmth_"), starts_with("competence_")) & !ends_with("_first"),
               names_to = c(".value", "who"), names_sep = "_") %>%
  mutate(std = as.numeric(who == "standard"), doc = as.numeric(who == "doctor"))
print(summary(lmer(trust ~ std + doc + (1 | participant), data = long)))
print(summary(lmer(trust ~ std + doc + IsMale + AgeGroup + warmth + competence + (1 | participant), data = long)))
