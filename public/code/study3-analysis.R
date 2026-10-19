# Study 3: condition comparisons and regression models, from the released data
# Matthew Leitao, Georgetown University dissertation, Chapter 3
#
# Reads study3-ratings.csv (de-identified; see study3-codebook.csv). Each person was randomly shown one
# recommender (doctor, standard AI or humanlike AI) and rated trust and belief (-3 to 3) and warmth and
# competence (0 to 4). The two AI conditions also rated how humanlike the AI seemed (0 to 4).
#
# Age is released in four bands, so age enters as the band number (1 = 18 to 44, ... 4 = 70 and over).
# Cohen's d uses the pooled standard deviation. The dissertation text used 2t / sqrt(df), so values differ slightly.
#
# Needs: readr, dplyr, effectsize.
# This was translated from the Python analysis and has not been run in R; the numbers it should print are in
# study3-full.json on the site (analysis/study3-full-results.py).

library(readr); library(dplyr); library(effectsize)

d <- read_csv("study3-ratings.csv", show_col_types = FALSE)
stopifnot(nrow(d) == 609)
d$condition <- factor(d$condition, levels = c("Humanlike AI", "Standard AI", "Doctor"))
d$ai <- ifelse(d$condition == "Doctor", "Doctor", "AI")

welch <- function(x, y) {
  t <- t.test(x, y)
  data.frame(nA = sum(!is.na(x)), nB = sum(!is.na(y)), diff = mean(x, na.rm = TRUE) - mean(y, na.rm = TRUE),
             t = unname(t$statistic), df = unname(t$parameter), p = t$p.value,
             d = cohens_d(x, y, pooled_sd = TRUE)$Cohens_d)
}
contrasts <- function(v) bind_rows(
  cbind(test = "Doctor versus both AIs", welch(d[[v]][d$condition == "Doctor"], d[[v]][d$condition != "Doctor"])),
  cbind(test = "Humanlike versus standard AI", welch(d[[v]][d$condition == "Humanlike AI"], d[[v]][d$condition == "Standard AI"])),
  cbind(test = "Doctor versus standard AI", welch(d[[v]][d$condition == "Doctor"], d[[v]][d$condition == "Standard AI"])),
  cbind(test = "Doctor versus humanlike AI", welch(d[[v]][d$condition == "Doctor"], d[[v]][d$condition == "Humanlike AI"])))

for (v in c("trust", "belief", "warmth", "competence")) {
  cat("\n==", v, "\n")
  print(summary(aov(reformulate("condition", v), data = d)))
  print(TukeyHSD(aov(reformulate("condition", v), data = d)))
  print(contrasts(v), digits = 3)
}

# Manipulation check: did the humanlike AI seem more humanlike?
print(welch(d$humanlike[d$condition == "Humanlike AI"], d$humanlike[d$condition == "Standard AI"]), digits = 3)

# Regression models (reference group: humanlike AI)
d$AgeGroup <- as.numeric(factor(d$age_group, levels = c("18-44", "45-59", "60-69", "70+")))
d$IsMale <- as.numeric(d$gender == "Man")
for (v in c("trust", "belief")) {
  cat("\n== models for", v, "\n")
  print(summary(lm(reformulate("condition", v), data = d)))
  print(summary(lm(reformulate(c("condition", "IsMale", "AgeGroup"), v), data = d)))
  print(summary(lm(reformulate(c("condition", "IsMale", "AgeGroup", "warmth", "competence"), v), data = d)))
}
