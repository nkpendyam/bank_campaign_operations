# Local verification

Verified against the original `bank-additional-full.csv` source:

- 41,188 records and 4,640 subscriptions retained.
- Six external SQL aggregates reconcile to independent pandas calculations.
- Seven unit tests pass, including nested archive extraction, invalid inputs, duplicate controls, recency, SQL reconciliation, Wilson intervals, and rejection of altered source data with the same schema and row count.
- Eight notebook code cells executed successfully. The notebook records 12 excess identical rows and 4,110 history conflicts without rewriting them.
- The three-page PDF was regenerated and rendered for visual inspection. Pages have readable charts and no observed clipping.
- Source checksum and executed validation checks are recorded in `validation.json`.

The analysis is descriptive. Intervals assume independent records; unique clients and exact dates are unavailable. No causal channel effect, optimal contact cap or realized savings is claimed.

GitHub publication is a separate pending step. Local files are backed up under the parent workspace `_backups` directory.
