# Data for charts

This repository is public. Anything committed here is public, so only put data here that you are allowed to publish.

## Layout

Each project gets its own folder:

```
src/data/<project>/
  meta.json        where the data came from, what it covers, and what may be shared
  <name>.json|csv  the numbers a chart reads
```

`meta.json` records the source, what each file contains, and the sharing limits. Write the limits down before the data goes in.

## What can go in

- Summary statistics, model estimates and figures from published work.
- Simulated data, labelled as simulated on the page.
- Public datasets with a license that allows reuse.
- Participant-level data only if the study's consent form and any data use agreement allow public release.

## What stays out

- Restricted-access cohorts such as TARCC. Use published statistics from them instead.
- Anything that could identify a participant.
- Raw files from a collaborator's project without their agreement.

## Adding a chart

1. Add the data file and update `meta.json`.
2. Import the file in the page and pass it to a chart component in `src/components/`.
3. Cite the source on the page, next to the chart.
