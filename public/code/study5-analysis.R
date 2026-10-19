# Study 5: the three recommenders, with and without a voice, and mind perception, from the released data
# Matthew Leitao, Georgetown University dissertation, Chapter 3
#
# Reads study5-ratings.csv (de-identified; see study5-codebook.csv). One row per person.
# Everyone rated the doctor, the humanlike AI and the standard AI. Voice is the between-person factor: people were
# randomly assigned to read the recommendation only, or to read it and hear it spoken.
# "Trust and belief" is the mean of the two ratings (-3 to 3). Mind perception is the mean of the seven mind_ items.
#
# Age is released in four bands. Paired effect sizes are dz. Needs: readr, dplyr, tidyr, lme4, lmerTest, afex.
# This was translated from the Python analysis and has not been run in R; the numbers it should print are in
# study5-full.json on the site (analysis/study5-full-results.py).

library(readr); library(dplyr); library(tidyr); library(lme4); library(lmerTest); library(afex)

d <- read_csv("study5-ratings.csv", show_col_types = FALSE)
stopifnot(nrow(d) == 854)
recs <- c("humanlike", "standard", "doctor")
mind_items <- c("capable", "anticipate", "feelings", "account", "familiar", "transparent", "process")
for (r in recs) {
  d[[paste0("tb_", r)]] <- rowMeans(d[, paste0(c("trust_", "belief_"), r)])
  d[[paste0("mind_", r)]] <- rowMeans(d[, paste0("mind_", mind_items, "_", r)])
}

paired <- function(a, b) {
  t <- t.test(a, b, paired = TRUE)
  data.frame(n = sum(complete.cases(a, b)), diff = mean(a - b, na.rm = TRUE), t = unname(t$statistic), df = unname(t$parameter),
             p = t$p.value, p_bonferroni = min(1, 3 * t$p.value), dz = mean(a - b, na.rm = TRUE) / sd(a - b, na.rm = TRUE))
}
for (v in c("tb", "trust", "belief", "warmth", "competence", "mind")) {
  g <- function(r) d[[paste0(v, "_", r)]]
  cat("\n==", v, "\n")
  print(rbind(cbind(test = "Doctor versus standard AI", paired(g("doctor"), g("standard"))),
              cbind(test = "Humanlike versus standard AI", paired(g("humanlike"), g("standard"))),
              cbind(test = "Humanlike AI versus doctor", paired(g("humanlike"), g("doctor")))), digits = 3)
}

# Mixed ANOVA on the people who rated all three: recommender (within) by voice (between)
w <- d %>% select(participant, voice, tb_humanlike, tb_standard, tb_doctor) %>%
  pivot_longer(starts_with("tb_"), names_to = "recommender", names_prefix = "tb_", values_to = "tb") %>% drop_na()
w <- w %>% group_by(participant) %>% filter(n() == 3) %>% ungroup()
print(aov_ez("participant", "tb", w, within = "recommender", between = "voice", anova_table = list(es = "pes")))

# Voiced versus written only, within each recommender
for (r in recs) print(t.test(d[[paste0("tb_", r)]] ~ d$voice))

# Friedman test of the trust rankings
ranks <- d %>% select(starts_with("rank_trust_")) %>% drop_na()
print(friedman.test(as.matrix(ranks)))

# Mixed model: recommender, voice and their interaction (reference: humanlike AI, written only)
long <- d %>% mutate(AgeGroup = as.numeric(factor(age_group, levels = c("18-44", "45-59", "60-69", "70+"))), IsMale = as.numeric(gender == "Man")) %>%
  pivot_longer(all_of(paste0(rep(c("tb", "mind", "warmth", "competence"), each = 3), "_", recs)),
               names_to = c(".value", "who"), names_sep = "_") %>%
  mutate(std = as.numeric(who == "standard"), doc = as.numeric(who == "doctor"), voiced = as.numeric(voice == "Written and voiced"))
m1 <- lmer(tb ~ std * voiced + doc * voiced + (1 | participant), data = long); print(summary(m1))
m3 <- lmer(tb ~ std * voiced + doc * voiced + mind + warmth + competence + AgeGroup + IsMale + (1 | participant), data = long); print(summary(m3))
