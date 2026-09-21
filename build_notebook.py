"""Create and execute an inspectable analysis notebook from saved source/SQL."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent

def main():
    nb = nbformat.v4.new_notebook()
    nb.metadata['kernelspec'] = {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}
    markdown = nbformat.v4.new_markdown_cell
    code = nbformat.v4.new_code_cell
    nb.cells = [
        markdown('# Bank campaign operations: reproducible evidence\n'
                 'Source: [UCI Bank Marketing](https://archive.ics.uci.edu/dataset/222/bank+marketing), '
                 'bank-additional-full.csv. Grain: published campaign records, not uniquely identified customers or calls. '
                 'The source spans May 2008-November 2010 but lacks exact dates and customer identifiers. '
                 'All comparisons are descriptive associations.'),
        code("from pathlib import Path\nimport pandas as pd\nimport sqlite3, json, hashlib\n"
             "root = Path.cwd()\nif not (root/'data/raw').exists(): root = root.parent\n"
             "raw = pd.read_csv(root/'data/raw/bank-additional-full.csv', sep=';')\n"
             "assert raw.shape == (41188, 21)\nassert set(raw.y.unique()) == {'yes','no'}\n"
             "assert int(raw.y.eq('yes').sum()) == 4640\n"
             "{'records':len(raw), 'subscriptions':int(raw.y.eq('yes').sum()), 'subscription_rate':raw.y.eq('yes').mean()}"),
        markdown('## Quality and missingness\n'
                 'Identical rows are retained: without a business key they are not proven duplicate ingestion. '
                 '`unknown` is an explicit missingness code, while `poutcome=nonexistent` is structural.'),
        code("duplicates = int(raw.duplicated().sum())\nassert duplicates == 12\n"
             "unknown = raw.eq('unknown').sum().sort_values(ascending=False)\n"
             "print('Excess identical rows retained:', duplicates)\n"
             "pd.DataFrame({'unknown_records':unknown[unknown>0], 'unknown_rate':unknown[unknown>0]/len(raw)})"),
        code("recency = raw.pdays.mask(raw.pdays.eq(999))\n"
             "conflicts = int((raw.pdays.eq(999) & raw.previous.gt(0)).sum())\nassert conflicts == 4110\n"
             "print('History conflicts retained without correction:', conflicts)\n"
             "print('Previously contacted recency only (days):')\nrecency.describe()"),
        markdown('## SQL ledger and exported controls\n'
                 'The SQL files in `sql/` define the export queries. Record IDs are generated technical identifiers; '
                 'they do not identify unique people.'),
        code("con = sqlite3.connect(root/'data/processed/campaign.sqlite')\n"
             "pd.read_sql_query('SELECT COUNT(*) records, SUM(subscribed) subscriptions FROM observations', con)"),
        code("pressure = pd.read_csv(root/'reports/contact_pressure.csv')\n"
             "assert int(pressure.records.sum()) == len(raw)\n"
             "assert int(pressure.subscriptions.sum()) == int(raw.y.eq('yes').sum())\n"
             "assert (pressure.ci_low <= pressure.subscription_rate).all()\n"
             "assert (pressure.ci_high >= pressure.subscription_rate).all()\npressure"),
        markdown('## Uncertainty and confounding\n'
                 'Wilson 95% intervals assume independent records. Unidentified repeat clients may violate that '
                 'assumption, so intervals may understate uncertainty. Contact-count groups are subject to selection '
                 'and stopping behavior. No contact cap, channel effect, ROI or cost saving is estimated.'),
        code("strata = pd.read_csv(root/'reports/pressure_strata.csv')\n"
             "assert int(strata.records.sum()) == len(raw)\n"
             "print('Strata with fewer than 30 records:', int(strata.records.lt(30).sum()))\n"
             "strata.sort_values('records', ascending=False).head(12)"),
        code("from IPython.display import Image, display\n"
             "display(Image(filename=str(root/'reports/contact-pressure.png')))\n"
             "display(Image(filename=str(root/'reports/data-quality.png')))"),
        markdown('## Decisions and limitations\n'
                 '- Investigate repeat-contact rules within channel and prior-outcome strata before proposing a pilot.\n'
                 '- Preserve unknown-category reporting and obtain identifiers, timestamps and actual costs for stronger analysis.\n'
                 '- Calendar months pool multiple years; these are not a chronological time series.\n'
                 '- Call duration is known after contact and must not drive prospective targeting.\n'
                 '- See `campaign-operations-brief.pdf` and `validation.json` for the decision brief and full controls.'),
        code("con.close()\nprint('Notebook controls passed; no source rows were changed.')")
    ]
    out = ROOT/'notebooks'
    out.mkdir(exist_ok=True)
    client = NotebookClient(nb, timeout=120, kernel_name='python3', resources={'metadata': {'path': str(ROOT)}})
    client.execute()
    nbformat.write(nb, out/'campaign_operations.ipynb')
    print(f'Executed {sum(c.cell_type == "code" for c in nb.cells)} notebook cells; all controls passed.')

if __name__ == '__main__':
    main()
