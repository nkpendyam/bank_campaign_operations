"""Render a decision brief from reconciled SQL outputs, not hand-entered results."""
from pathlib import Path
import json
from html import escape
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'reports'
BLUE = '#235b78'
INK = '#18303e'
SOURCE = 'https://archive.ics.uci.edu/dataset/222/bank+marketing'

def rate_plot(frame, category, title, filename):
    fig, ax = plt.subplots(figsize=(9, 3.6), layout='constrained')
    y = frame.subscription_rate.to_numpy()
    ax.errorbar(range(len(frame)), y,
                yerr=[y-frame.ci_low.to_numpy(), frame.ci_high.to_numpy()-y],
                fmt='o', markersize=8, capsize=5, color=BLUE, linewidth=2)
    labels = [f'{value}\nn={n:,}' for value, n in zip(frame[category], frame.records)]
    ax.set_xticks(range(len(frame)), labels, fontsize=10)
    ax.set_ylim(0, max(frame.ci_high) * 1.25)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel('Subscription proportion')
    ax.set_title(title, loc='left', color=INK, fontsize=14, pad=14)
    ax.grid(axis='y', alpha=.18)
    for side in ['top', 'right']:
        ax.spines[side].set_visible(False)
    for i, value in enumerate(y):
        ax.annotate(f'{value:.1%}', (i, value), xytext=(12, 5), textcoords='offset points', fontsize=10)
    fig.savefig(OUT / filename, dpi=170, facecolor='white')
    plt.close(fig)

def main():
    pressure = pd.read_csv(OUT / 'contact_pressure.csv')
    channel = pd.read_csv(OUT / 'channel.csv')
    unknowns = pd.read_csv(OUT / 'unknowns.csv').sort_values('unknown_records', ascending=False)
    prior = pd.read_csv(OUT / 'prior_outcome.csv')
    validation = json.loads((OUT / 'validation.json').read_text())
    controls = validation['controls']
    rate_plot(pressure, 'contact_band', 'Observed outcomes by reported contact-count band', 'contact-pressure.png')
    rate_plot(channel, 'contact', 'Channel comparison: association, not treatment effect', 'channel-comparison.png')
    fig, ax = plt.subplots(figsize=(9, 3.6), layout='constrained')
    missing = unknowns[unknowns.unknown_records > 0].sort_values('unknown_records')
    ax.barh(missing.field, missing.unknown_rate, color=BLUE, height=.6)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlim(0, max(missing.unknown_rate)*1.3)
    for i, row in enumerate(missing.itertuples()):
        ax.text(row.unknown_rate+.003, i, f'{row.unknown_rate:.1%} ({row.unknown_records:,})', va='center', fontsize=10)
    ax.set_title('Unknown is a missingness code, not a null cell', loc='left', color=INK, fontsize=14)
    for side in ['top', 'right']:
        ax.spines[side].set_visible(False)
    fig.savefig(OUT / 'data-quality.png', dpi=170, facecolor='white')
    plt.close(fig)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Hero', fontName='Helvetica-Bold', fontSize=26, leading=29, textColor=colors.HexColor(INK), spaceAfter=16))
    styles.add(ParagraphStyle(name='BodyCopy', fontName='Helvetica', fontSize=10.5, leading=15, spaceAfter=10, textColor=colors.HexColor(INK)))
    styles.add(ParagraphStyle(name='Eyebrow', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor(BLUE), spaceAfter=10))
    styles.add(ParagraphStyle(name='SmallCopy', fontSize=8, leading=11, spaceAfter=7, textColor=colors.HexColor('#455761')))
    story = []
    def p(text, style='BodyCopy'):
        story.append(Paragraph(text, styles[style]))
    def chart(filename):
        story.append(Image(str(OUT / filename), width=505, height=202))
        story.append(Spacer(1, 12))
    def table(headers, rows, widths):
        cells = [[Paragraph(escape(str(v)), styles['SmallCopy']) for v in row] for row in [headers]+rows]
        t = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf1f5')),
            ('VALIGN',(0,0),(-1,-1),'TOP'), ('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor(BLUE)),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f6f8f9')])]))
        story.append(t)
        story.append(Spacer(1, 12))

    p('01 / CAMPAIGN OPERATIONS', 'Eyebrow')
    p('Contact pressure &amp;<br/>subscription outcomes', 'Hero')
    p('Independent portfolio analysis | Portuguese bank campaigns | Historical source: May 2008-November 2010', 'SmallCopy')
    p(f'<b>{controls["records"]:,} records</b> &nbsp; | &nbsp; <b>{controls["subscriptions"]:,} subscriptions</b> &nbsp; | &nbsp; <b>{controls["subscription_rate"]:.2%} observed proportion</b>')
    chart('contact-pressure.png')
    first = pressure.loc[pressure.contact_band.astype(str).eq('1')].iloc[0]
    last = pressure.loc[pressure.contact_band.astype(str).eq('6+')].iloc[0]
    p(f'Records with one reported current-campaign contact show a {first.subscription_rate:.2%} subscription proportion; the 6+ contact group shows {last.subscription_rate:.2%}. These are different observed groups, not an experiment.')
    p('<b>Decision supported:</b> review repeat-contact rules and investigate selection/stopping behavior. A controlled pilot with identified customers, contact timestamps and agreed outcomes is needed before choosing a contact cap.')
    p('<b>Do not infer:</b> that fewer contacts cause higher conversion, or that a cap would deliver a quantified saving. Successful subscriptions may themselves stop further contacts.')
    p('Points show record-level proportions; bars show 95% Wilson intervals. Repeated clients cannot be identified. Independence may fail, making these intervals too narrow.', 'SmallCopy')
    story.append(PageBreak())

    p('02 / COMPARISON & CONTEXT', 'Eyebrow')
    p('Compare like with like', 'Hero')
    chart('channel-comparison.png')
    p('Channel rates differ, but channel was not randomly assigned. Prior campaign history and pooled calendar-month composition can differ too. Use the exported contact-by-prior-outcome strata to investigate these associations.')
    table(['Previous campaign outcome', 'Records', 'Subscriptions', 'Observed rate'],
          [[r.poutcome, f'{r.records:,}', f'{r.subscriptions:,}', f'{r.subscription_rate:.2%}'] for r in prior.itertuples()], [205,90,100,110])
    p('<b>Available evidence:</b> <font face="Courier">pressure_strata.csv</font> retains every contact-band/channel/prior-outcome group, including small samples. <font face="Courier">channel_by_month.csv</font> pools matching calendar months across years; it is not a chronological monthly series.')
    p('<b>Next measurement:</b> assign stable customer and campaign IDs, preserve every contact timestamp, record actual costs and define a follow-up window. These additions permit customer-level workload analysis and a defensible pilot; they are recommendations, not implemented outcomes.')
    p('The file lacks unique customer identifiers and exact dates. Reported contact counts include the last contact; their sum is not a verified count of distinct calls. No ROI, revenue or staffing benefit is estimated.', 'SmallCopy')
    story.append(PageBreak())

    p('03 / TRUST & REPRODUCIBILITY', 'Eyebrow')
    p('Quality before conclusions', 'Hero')
    chart('data-quality.png')
    p(f'<b>{controls["exact_duplicate_rows"]} excess identical rows retained.</b> Without business keys, identical records are not proven ingestion duplicates. Dropping them could remove legitimate observations.')
    conflicts = controls['history_conflicts']['pdays_never_but_previous_positive']
    p(f'<b>History ambiguity:</b> {conflicts:,} records have <font face="Courier">pdays=999</font> but positive previous contacts. The dictionary describes 999 as no previous contact; these records conflict with that interpretation. They remain flagged, not rewritten. Sentinel values are excluded from numeric recency summaries.')
    p('<b>Leakage boundary:</b> call duration is known after the contact. It is excluded from targeting and prospective recommendations. This project is descriptive operations analysis, not a predictive model.')
    p('<b>Reproduction:</b> run <font face="Courier">python build.py</font>, the unittest suite, then <font face="Courier">python render_report.py</font>. Source fingerprint, controls and query outputs accompany this brief. The executed notebook exposes the main quality checks and SQL results.')
    p('Source: Moro, S., Rita, P., &amp; Cortez, P. (2014). Bank Marketing. UCI Machine Learning Repository. DOI: 10.24432/C5K306. CC BY 4.0.', 'SmallCopy')
    p(f'<link href="{SOURCE}" color="#235b78">UCI source and license</link> | Dataset variant: bank-additional-full.csv, 20 inputs plus outcome.', 'SmallCopy')
    def footer(canvas, doc):
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(colors.HexColor('#637680'))
        canvas.drawString(44,28,'BANK CAMPAIGN OPERATIONS / portfolio evidence')
        canvas.drawRightString(A4[0]-44,28,str(doc.page))
    doc = SimpleDocTemplate(str(OUT/'campaign-operations-brief.pdf'), pagesize=A4,
                            rightMargin=44,leftMargin=44,topMargin=42,bottomMargin=45,
                            title='Bank campaign operations: evidence brief', author='Naveen Kumar Pendyam')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print('Created 3 figures and campaign-operations-brief.pdf')

if __name__ == '__main__':
    main()
