# Methodology

## Question and decision use

The project evaluates whether historical records reveal operational patterns around reported repeat contacts and communication channel. The intended decision is whether to investigate repeat-contact rules and design a controlled measurement pilot. The analysis is not a predictive model and cannot justify a contact cap or channel allocation by itself.

## Source and grain

The source is UCI's `bank-additional-full.csv`: 41,188 records, 20 inputs and the binary outcome `y`, with 4,640 `yes` outcomes (11.265%). The dictionary describes the source as ordered from May 2008 through November 2010, while the file provides no exact date, year, or unique customer identifier. Every count is therefore a count of observed campaign records. A generated `row_id` is only a technical row key.

`campaign` means reported contacts performed during the current campaign for the client and includes the last contact. It is binned into `1`, `2`, `3`, `4-5`, and `6+`. The sum of this field is not a verified count of unique calls. `pdays=999` is the dictionary's sentinel for no previous contact and is excluded from numeric recency summaries. The source also contains 4,110 rows with `previous > 0` alongside that sentinel; this history ambiguity remains flagged and is not silently repaired. `poutcome=nonexistent` is retained as a structural category.

## Validation and query ledger

Python validates the 21-column schema, allowed categories, numeric domains, row count, and binary outcome before writing the SQLite `observations` table. Six grouped queries export contact pressure, channel, channel by calendar month, prior outcome, pooled month, and contact/channel/prior-outcome strata. Each output includes records, subscriptions, observed subscription proportion, summed reported contacts, and a Wilson 95% interval. Small groups are marked rather than discarded. Explicit `unknown` category values are counted and exported in `unknowns.csv`.

The raw file contains 12 excess identical rows across 12 groups, affecting 24 records. They are retained: without a customer or campaign key, identical rows are not proven duplicate ingestion. Removing them would change the observed record distribution without an evidentiary basis.

## Uncertainty and interpretation

Wilson intervals are useful record-level uncertainty summaries, but they assume independent records. Because repeat people cannot be identified, the intervals may be too narrow. Contact pressure is observational and affected by selection, successful conversion, and stopping behavior. Channel assignment is also non-random. Consequently, differences are associations, not causal treatment effects; no uplift, cap benefit, ROI, revenue, or staffing saving is estimated.

Calendar-month outputs pool matching month labels across multiple years, so they do not establish a chronological trend. Call `duration` is known only after a contact and is excluded from targeting or prospective recommendations to avoid post-contact leakage.

## Reproducibility and scope

Run `pip install -r requirements.txt`, `python build.py`, `python -m unittest discover tests`, `python render_report.py`, and `python build_notebook.py`. The renderer reads reconciled CSV and JSON outputs to create three PNG charts and the three-page `campaign-operations-brief.pdf`; it does not hand-enter analytical values. In the current build, all six unittest tests passed, the notebook executed eight code cells without errors, and the PDF was regenerated with three figures. Final visual review of the PDF remains a separate release check.

The source is [UCI Bank Marketing](https://archive.ics.uci.edu/dataset/222/bank+marketing), DOI `10.24432/C5K306`, CC BY 4.0. Citation: Moro, S., Cortez, P., & Rita, P. (2014), “A Data-Driven Approach to Predict the Success of Bank Telemarketing.”
