# Psycho_Robot

The source for Matthew Leitao's website: research, projects, skills and a live CV, written for both academic and industry readers.

This README doubles as a build log. It records how the site was made and why, so the choices can be checked, changed or reused.

## Contents

1. [What the site is for](#what-the-site-is-for)
2. [Stack and why](#stack-and-why)
3. [Design decisions](#design-decisions)
4. [How the data and charts work](#how-the-data-and-charts-work)
5. [The pages](#the-pages)
6. [The live CV](#the-live-cv)
7. [Study 1 data release](#study-1-data-release)
8. [Study 1 in full](#study-1-in-full)
9. [Content rules](#content-rules)
10. [Everyday tasks](#everyday-tasks)
11. [Deploying](#deploying)
12. [How it was built, and what went wrong](#how-it-was-built-and-what-went-wrong)
13. [License](#license)

## What the site is for

Two readers, one site. Academic readers want the papers and methods. Industry recruiters and hiring managers want to see that the same skills (experiment design, statistics, data work, communicating findings) solve their problems. The goal is to show the work rather than describe it: real data, real figures, and charts a visitor can interact with.

That goal drives the biggest rule in the project: **wherever possible, a chart uses data or results from work that has actually been done**, so each claim on the site points at something a visitor can inspect.

## Stack and why

- **Astro** (static site generator), **plain CSS**, a little client-side TypeScript for interactive charts.
- **GitHub Pages**, deployed by a GitHub Actions workflow on every push to `main`.

Why Astro instead of hand-written HTML/CSS/JS: the site repeats the same pieces (page frame, chart components, publication lists) and reads its content from data files. Astro gives components and data imports at build time and ships plain HTML, with no framework running in the browser. Why not a heavier framework: nothing here needs client-side routing or state, so shipping one would cost speed for no benefit. Why not a template or theme: the point is custom charts, and a theme would have to be fought.

Charts are hand-built SVG with small scripts rather than a charting library. This keeps them light, lets every mark follow the same style rules, and makes tooltips, keyboard focus and table views consistent. The trade-off is that each new chart type needs a component.

## Design decisions

- **Two meaning-bearing colors.** Cobalt (`--doctor`) stands for the human, marigold (`--ai`) for the AI. The same color means the same thing in every chart, so a visitor learns the code once. A neutral grey is used for in-between cases, such as a doctor using AI.
- **Cool paper background, deep ink text.** Chosen to read as a lab notebook rather than a template. Dark mode follows the visitor's system setting and is its own set of values, not an inversion.
- **Type.** Bricolage Grotesque for headings and interface text, Source Serif 4 for reading. Self-hosted through `@fontsource`, so no request goes to a third party.
- **Chart rules** (from a data visualization checklist): thin marks, one axis per chart, a legend whenever there are two or more series, selective labels, recessive grid lines, text in text colors rather than series colors, and a hover tooltip on every chart.
- **Accessibility floor.** Every chart can be reached and read by keyboard (rows and bars take focus and show the same tooltip), has a text label for screen readers, and offers a "View as a table" fold. Color is never the only signal: filled and hollow dots mark significance, and legends name every group.
- **Honest scales.** Effect sizes are shown as reported. Confidence intervals appear only when they were computed from data in this repository. Nothing is smoothed or estimated.
- **Placeholders are labeled.** Pages that still need material show a clearly marked placeholder that says what is needed, so unfinished parts are obvious rather than faked.

## How the data and charts work

Each project has a folder, `src/data/<project>/`, with a `meta.json` (source, what each file holds, and what may be shared) and the numbers a chart reads. A page imports those files and passes them to a chart component in `src/components/`. The source is cited on the page next to the chart. See [`src/data/README.md`](src/data/README.md) for the sharing rules.

What may go in the repository, because it is public:

- summary statistics, estimates and figures from published work;
- simulated data, labelled as simulated;
- public datasets with a license that allows reuse;
- participant-level data only if it is de-identified **and** the author is entitled to release it.

What stays out: restricted-access cohorts, anything that could identify a participant, and raw files from collaborators' projects without their agreement.

Chart components so far:

| Component | Shows |
| --- | --- |
| `ForestPlot` | Differences with a zero line, one row per group |
| `EffectDots` | Effect sizes per study, filled when significant |
| `RankDots` | Ranked means with 95% intervals |
| `OutcomePairs` | Doctor versus AI on several outcomes, side by side |
| `Study1Live` | Demographic filters that rerun the chart, the tests and the histograms |
| `PowerCurve` | Power for a paired t test: effect size, people needed, and what Study 1 could detect |
| `EvidenceMatrix` | Skills against the evidence that supports each |

## The pages

- **Home**: who I am and what I do, with a first chart.
- **Projects**: one page per project, starting with the dissertation on trust in medical AI. The Study 1 part of that project has its own page with every table and figure (see below).
- **Skills**: each skill is tagged with how strong the evidence is (direct, project-supported, applied coursework, developing), so a skill is never listed without saying how it is known.
- **Research**: publications, from the same data file as the CV.
- **CV**: a live CV (below).
- **Contact**: email and LinkedIn.

## The live CV

The CV page is generated from two data files, `src/data/cv/cv.json` and `src/data/cv/publications.json`. Adding a paper, talk or role to a file adds it to the page on the next build, and a paper added to `publications.json` appears on both the CV and Research pages. The "Updated" date is read from the last git commit that touched `src/data/cv` at build time, falling back to a date in `cv.json`, so it moves without anyone remembering to edit it. Long lists are folded, the section index highlights as you read, and the page prints cleanly (folds open and navigation hides).

The CV was assembled from the existing CV, a skills inventory, a record of experience and the LinkedIn profile, and then checked against the dissertation. Author order and role wording follow the papers themselves.

## Study 1 data release

The Study 1 section of the trust-in-medical-AI page has two parts. A static chart shows the main finding: doctor versus AI on trust, quantitative reasoning and intuition, side by side as in the paper. Below it, visitors can filter to a demographic group and the chart, the table of tests and the histograms rerun on the spot. This section records how the released file was made and how the live part works. The data are released as part of an open science commitment.

**Release approval.** The author confirms the study's IRB approval allows public release of the de-identified data.

**Source.** The raw Qualtrics export of the Study 1 survey (Chapter 1 of the dissertation). It is not in this repository: it contains IP addresses, coordinates, response IDs, panel IDs and detailed demographic answers.

**Cleaning**, as implemented in [`analysis/study1-deidentify.py`](analysis/study1-deidentify.py):

1. Drop Qualtrics preview and test rows.
2. Keep participants who consented, which gives the N = 188 analyzed in the dissertation.
3. Keep the analysis variables: 15 decision ratings (0 to 100 sliders) and 33 recommender ratings (trust, quantitative reasoning and intuition, for 11 recommenders; 0 to 10).
4. Recode the 0 to 10 ratings from the export's codes 1 to 11 (see Checks).
5. Add six coarse demographic groups so visitors can filter: age group (4), gender (2), race (3), education (2), political views on social issues (3) and experience with AI (2). Each is collapsed so no group is small. Gender has two groups because only woman and man were reported. **A group gets its own filter button only if at least 30 people are in it** (the author's rule). For race that means White (122) and Black (44), each only when it is the sole group selected; Asian, Native American, Pacific Islander, self-described and everyone who chose more than one are combined into "Another or multiple" because none of them reaches 30. Hispanic or Latino/a/x ethnicity is a separate question and is not released: 15 people said yes. One invalid age and a few missing answers are left blank.
6. Release nothing else: no IP address, coordinates, timestamps, response, panel or device IDs, free text, and none of the sensitive items (income, disability, mental health, transgender status, employment, first language, birthplace, parents' education).
7. Replace response IDs with participant numbers assigned after a seeded shuffle, so row order does not reveal when someone took the survey.

**Re-identification risk, stated plainly.** There are no direct identifiers, and the groups are broad, but the six demographic columns together are not anonymous in the strict sense: in the released file, 77 of 188 people have a combination of the six that no one else shares. Anyone who already knew a person's age band, gender, race, education, politics and AI experience, and knew they took this survey, could find their row. The ratings are not sensitive, and the site refuses to show results for fewer than 10 people. To release less, delete entries from `DEMOGRAPHICS` in the script and rebuild.

**Files** (in `public/`, so they download from the site):

- `data/study1-ratings.csv`: the cleaned data, 188 rows.
- `data/study1-codebook.csv`: every variable, what it measures and its scale.
- `code/study1-analysis.R`: the seven preregistered tests plus one exploratory test, written to read top to bottom, with a note on filtering to a subgroup.
- `code/study1-original-analysis.Rmd`: the author's original analysis notebook, run on the raw export. Only two lines changed for release: the author's local file paths became `raw-data/...` placeholders. It cannot run on the released file, because it reads the raw `.sav`; it is there so the full analysis is visible.
- `docs/study1-preregistration.pdf`: the preregistration, made from the author's Word file. A reviewer's margin comment was removed first, and nothing else was changed. The PDF's author field is the author's own name.
- `data/LICENSE.md`: the data license, kept beside the data.

**Derived files.** [`analysis/study1-summaries.py`](analysis/study1-summaries.py) writes `trust-by-recommender.json`, `study1-tests.json` and `study1-outcomes.json` (the static charts read these). The tests themselves are defined once, in `study1-test-defs.json`, which both the Python script and the live table read, so they cannot drift apart.

**How the live part works.** [`Study1Live.astro`](src/components/Study1Live.astro) loads the CSV in the visitor's browser, filters the rows, and recomputes everything with a small statistics routine written for the page (paired t test, p value from the t distribution, confidence intervals). Nothing is sent anywhere. Choices within a demographic row combine as "or", and choices across rows combine as "and". The page shows results only when at least 10 people match, and it warns that subgroup results are exploratory.

**Power analysis.** `PowerCurve` and the "smallest detectable effect" line under the filters use `src/utils/power.ts`, an implementation of the noncentral t distribution (Lenth, 1989, AS 243), with `src/utils/stats.ts` for the t distribution. `analysis/check-stats.py` and `analysis/check-stats.mjs` print the same cases from scipy and from the browser code so they can be compared: they agree to five decimals. The chart is a sensitivity view (what the study could detect) and not "observed power", which adds nothing beyond the p value.

**Checks.**

- With no filters, every test matches the dissertation exactly: mean difference, t, df, p and d for H1 to H7 and the exploratory test. For example H7 is t(184) = 10.73, d = 0.79.
- The browser calculation matches an independent Python run on a test subgroup (women aged 60 and over).
- **Missing items.** The original script averages items without ignoring missing values, so a composite is missing if any item is. An early draft of the summaries skipped missing values, which changed H1, H2 and H4 slightly (for example H2 gave t = 5.22 instead of the dissertation's 5.58). It now follows the original rule.
- **A coding catch.** Qualtrics stored the 0 to 10 scale as codes 1 to 11. The original script analyzed the codes, which is harmless for differences, t, p and d, but means read one point high. The released file is recoded to the scale participants saw, and an early draft of the ranked chart on this site (which used the raw codes) was corrected. The R file notes this.
- The R script has not been run by whoever built the site (the build environment had no R). Its expected output is `study1-tests.json`, which was computed independently in Python. Run it and compare before relying on it.

## Study 1 in full

The page `src/pages/projects/trust-in-medical-ai/study-1.astro` rebuilds every table and figure of the Study 1 analysis notebook from the released file: sample, descriptives, reliability, the factor analysis, the paired tests with a person-level count, the eleven-recommender descriptives and maps, the regressions, and the mixed models. All numbers come from [`analysis/study1-full-results.py`](analysis/study1-full-results.py), which writes `study1-full.json` (tables and models) and `study1-points.json` (every person's value, for the dot plots).

The same page has a second tab, "Humans versus AI", which compares the six human recommenders with the four AI recommenders (paired tests, every person's averages, each recommender, who shows the gap, and the slopes). Its numbers come from [`analysis/study1-human-vs-ai.py`](analysis/study1-human-vs-ai.py), which writes `study1-human-vs-ai.json`. It is exploratory and was not preregistered. The factor diagram (Figure 4b) completes the set of figures in the notebook; the notebook's last mixed model (3D) uses variables the notebook never creates, so it is the one piece not reproduced.

**What matches the dissertation, and what does not.** H1 to H7 and the exploratory test were checked against the dissertation text (see Checks above). The other tables come from the notebook's exploratory sections, recomputed from the public file. They have not been compared with the dissertation's own tables, and the sample table is coarser than the dissertation's because the public file groups demographics.

**Where Python stands in for R.**

| Notebook | Here |
| --- | --- |
| `psych::describe` | skew and kurtosis use the type 3 estimates `describe` reports |
| `psych::alpha` | raw alpha from pairwise covariances |
| `psych::fa`, minchi, oblimin | minimum residual extraction with oblimin rotation; the two are the same when every correlation rests on the same n (everyone with all 12 answers here) |
| `lme4::lmer` | a random-intercept model written out directly (`lmm()` in the script), fitted by REML. A general-purpose fitter stopped with a singular matrix on some models because a person's random intercept shrinks to zero there; the script handles that case the way lme4 does |
| `MuMIn::r.squaredGLMM` | Nakagawa marginal and conditional R squared |

As a check, the mixed-model slopes for AI and for human recommenders (0.273 and 0.430; 0.445 and 0.353) match the ones typed into the notebook's plot code. The notebook's last model (3D) uses grand-mean variables it never creates, so it is left out, and a doctor using AI counts as AI, as in the notebook. Run the R code on the released file and compare line by line before relying on any exploratory number.

**Not copied from the notebook.** The notebook counted people who rated a doctor above, equal to or below an AI for trust only; the page does the same count for every test and says so. The notebook's jittered violin plots used a very wide smoothing setting; the page uses a narrower one so the shape of the answers shows. Notes to self and presentation versions of the plots (white text on transparent backgrounds) are not reproduced.

**Narrow screens.** The dot plots, the map and the slopes chart keep a minimum width and scroll sideways, because shrinking them to a phone screen would make the labels unreadable. Each has a table view.

## Content rules

- Claims match the papers: author order, role and what was done are written as they are in the work.
- Skills carry an evidence level. A skill still being learned says so.
- No private contact details in the repository (no home address or phone).
- No raw or restricted data. See the data rules above.

## Everyday tasks

```bash
npm install
npm run dev        # local site at http://localhost:4321/Psycho_Robot/
npm run build      # build to dist/
npm run preview    # serve the built site
```

- **Add a paper:** add an entry to `src/data/cv/publications.json`. It appears on the CV and Research pages.
- **Add a CV entry:** edit `src/data/cv/cv.json` and add a line to `changes`.
- **Add a chart:** add the data file and update `meta.json`, import it in the page, pass it to a component, cite the source next to it.
- **Rebuild the Study 1 summaries** after changing the data file: `python3 analysis/study1-summaries.py` (needs pandas, scipy).

## Deploying

A push to `main` runs `.github/workflows/deploy.yml`, which builds the site and publishes it to GitHub Pages at `https://mrleitao.github.io/Psycho_Robot/`. In the repository settings, Pages must use the "GitHub Actions" source. The workflow checks out full git history because the CV page reads its date from it.

Work happens on a branch (`astro-scaffold`) and goes live only when it is merged to `main`. Do that once the placeholders are filled or removed.

## How it was built, and what went wrong

The site was built in conversation with Claude (Anthropic's AI model, through Claude Code), working in this repository, with the author deciding direction and checking facts. In order:

1. **Choice of approach.** Compared examples of static-site options, then chose Astro on GitHub Pages for components plus data-driven pages.
2. **Scaffold and design system.** Palette, type, layout, deploy workflow, and a data folder convention, with a placeholder wherever real material was still needed.
3. **First real data.** The dissertation's published tables became the first charts (the domain-by-domain gap and effect sizes across studies), and each chart was checked against the dissertation text.
4. **A second pass** on readability: chart sizes, label halos, layout on narrow screens, and screenshots at desktop and phone widths.
5. **The live CV and publications**, from the CV and project files, then corrections from review (paper details, DOIs, spellings).
6. **Study 1 data and code**, with a de-identified file and this documentation, then demographic filters that rerun the paper's tests in the browser.

Things that went wrong, kept here on purpose:

- A source discrepancy: the dissertation text gives signs for two humanlike-AI comparisons that contradict the condition means. Those comparisons are left out of the charts instead of guessing.
- The scale-coding offset and the missing-item rule described above: both found by checking the released data against the dissertation, fixed, and documented.
- Several early drafts needed checking for overclaiming (role wording, evidence levels); the evidence tags exist because of that.

## License

The code, including the R script and the original notebook, is under the MIT license, see [LICENSE](LICENSE). The released data, the codebook and the preregistration are under [CC BY 4.0](LICENSE-DATA.md): anyone may reuse them, including commercially, if they credit the work. CC BY was chosen over CC0 so that reuse carries a citation back to the dissertation, and over a non-commercial license because those restrict reuse in ways that are hard to define. The license does not permit trying to identify participants. [`CITATION.cff`](CITATION.cff) makes GitHub show a "Cite this repository" button. To get a DOI, link the repository to Zenodo and make a release.
