# Local verification

Verified against the original `bank-additional-full.csv` source:

- 41,188 records and 4,640 subscriptions retained.
- Six external SQL aggregates reconcile to independent pandas calculations.
- Six unit tests pass, including nested archive extraction, invalid inputs, duplicate controls, recency, SQL reconciliation and Wilson intervals.
- Eight notebook code cells executed successfully. The notebook records 12 excess identical rows and 4,110 history conflicts without rewriting them.
- The three-page PDF was regenerated and rendered for visual inspection. Pages have readable charts and no observed clipping.
- Source checksum and executed validation checks are recorded in `validation.json`.

The analysis is descriptive. Intervals assume independent records; unique clients and exact dates are unavailable. No causal channel effect, optimal contact cap or realized savings is claimed.

GitHub publication is a separate pending step. Local files are backed up under the parent workspace `_backups` directory.
