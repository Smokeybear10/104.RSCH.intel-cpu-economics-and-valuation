import hashlib
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, PageBreak, Table, TableStyle


ROOT = Path('/Users/thomasou/Documents/Codex/2026-11-02/lo')
RUN = ROOT / 'work/three_hour/active_research/intel_two_hour_completion_2026_11_06'
TMP = ROOT / 'tmp/pdfs/intel_long'
OUT = ROOT / 'output/pdf'
DATA = json.loads((RUN / 'root/integrated_results.json').read_text())
CASH = json.loads((RUN / 'root/quarterly_cash_results.json').read_text())
M = DATA['cases']['preferred']
ROWS = {int(y): r for y, r in M['annual_rows'].items()}
F = {int(y): r for y, r in M['treasury'].items()}
Q = CASH['base']['quarterly_rows']
SUMMARY = {r['case']: r for r in DATA['summary']}
FONT = Path('/System/Library/Fonts/Supplemental')
for name, file in [('Sans', 'Arial.ttf'), ('SansB', 'Arial Bold.ttf'), ('SansI', 'Arial Italic.ttf'), ('Body', 'Georgia.ttf'), ('BodyB', 'Georgia Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT / file)))
pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='SansB', italic='SansI', boldItalic='SansB')
pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyB', italic='Body', boldItalic='BodyB')
INK, MUTED, RULE, ACCENT, PALE, WHITE, RED = [HexColor(h) for h in ['#16283E', '#586575', '#CFD7E0', '#146F67', '#EFF3F7', '#FFFFFF', '#A9483C']]
URL = {
    'q3': 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm',
    'q2': 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000157/intc-20260627.htm',
    'q1remarks': 'https://download.intel.com/newsroom/2026/earnings/1Q2026-Earnings-Call.pdf',
    'q2remarks': 'https://download.intel.com/newsroom/2026/earnings/Intel-Q22026-Earnings-Call.pdf',
    'q3remarks': 'https://d1io3yog0oux5.cloudfront.net/_47986fe477a6ac84fe34efbcbf38dd13/intel/db/887/9273/prepared_remarks/Q3%2726_Prepared_Remarks.pdf',
    'call': 'https://www.marketbeat.com/earnings/reports/2026-10-29-intel-co-stock/',
    'consensus': 'https://stockanalysis.com/stocks/intc/forecast/',
    'quote': 'https://www.schwab.wallst.com/Research/Public/stocks/summary/?symbol=intc',
    'rules': 'https://www.m37.com/spc2026',
    'aws': 'https://aws.amazon.com/ec2/instance-types/x8i/',
    'google': 'https://cloud.google.com/blog/products/compute/c4-vms-based-on-intel-6th-gen-xeon-granite-rapids-now-ga',
    'oracle': 'https://www.intel.com/content/www/us/en/newsroom/news/corporate/intel-oracle-collaborate-on-enterprise-and-agentic-ai.html',
    'mobileye': 'https://ir.mobileye.com/news-releases/news-release-details/mobileye-releases-third-quarter-2026-results-updates-guidance',
    'altera': 'https://www.sec.gov/Archives/edgar/data/50863/000005086325000063/intc-20250414.htm',
    'ireland': 'https://stockanalysis.com/stocks/intc/transcripts/736613-deutsche-bank-2026-technology-conference/',
    'wms': 'https://www.kenan-flagler.unc.edu/wp-content/uploads/2024/12/First-Place-Equity_Team1_Universe_WMS.pdf',
    'jbi': 'https://www.kenan-flagler.unc.edu/wp-content/uploads/2023/12/Equity-1st-place_Columbia-_JBI.pdf',
    'cargo': 'https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-2024-winning-presentation-university-of-waterloo.pdf',
    'unc': 'https://www.kenan-flagler.unc.edu/alpha-challenge-2/archives/',
    'cfa': 'https://www.cfainstitute.org/insights/events/research-challenge/past-champions',
    'runson': 'https://runs-on.com/benchmarks/methodology/',
    'runson_raw': 'https://github.com/runs-on-demo/benchmark-public/tree/3691c0856de7597b2c73d86e4e2f0ee3cd934849/results',
    'aws_prices': 'https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/US%20East%20(N.%20Virginia)/Linux/index.json',
    'mediatek': 'https://www.mediatek.com/hubfs/MediaTek-Assets/Pdfs/Quarterly%20Earnings%20Release/2026/Quarterly%20Earnings%20Release-2026Q3/Transcript.pdf',
    'erp': 'https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPNov26.xlsx',
    'erp_monthly': 'https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx',
}


def link(label: str, url: str) -> str:
    return f'<link href="{escape(url, quote=True)}" color="#176A9B"><u>{escape(label)}</u></link>'


W, H, L, R = 960, 540, 40, 920
logs = []
screen = OUT / 'm37_intel_initial_screen.pdf'
c = canvas.Canvas(str(screen), pagesize=(W, H), pageCompression=1)
c.setTitle('Intel | The price edge still depends on future profits')
c.setAuthor('Thomas Ou')
c.setSubject('Updated research review; not a finalized M37 submission')


def text(x: float, top: float, value: str, size: float = 11, font: str = 'Sans', color=INK, align: str = 'left') -> None:
    c.setFillColor(color)
    c.setFont(font, size)
    draw = c.drawRightString if align == 'right' else c.drawCentredString if align == 'center' else c.drawString
    draw(x, H - top - size * .84, str(value))
    width = pdfmetrics.stringWidth(str(value), font, size)
    start = x - width if align == 'right' else x - width / 2 if align == 'center' else x
    assert start >= 8 and start + width <= W - 8, (c.getPageNumber(), value)


def rect(x: float, top: float, width: float, height: float, color) -> None:
    c.setFillColor(color)
    c.rect(x, H - top - height, width, height, fill=1, stroke=0)


def line(x1: float, top1: float, x2: float, top2: float, color=RULE, width: float = .6) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.line(x1, H - top1, x2, H - top2)


def para(value: str, x: float = L, top: float = 0, width: float = 880, size: float = 12, leading: float = 17, color=INK, font: str = 'Sans') -> float:
    value = value.replace('D&A', 'D&amp;A').replace('Q&A', 'Q&amp;A')
    p = Paragraph(value, ParagraphStyle('p', fontName=font, fontSize=size, leading=leading, textColor=color))
    _, height = p.wrap(width, 1000)
    p.drawOn(c, x, H - top - height)
    logs.append({'page': c.getPageNumber(), 'x': x, 'top': top, 'bottom': top + height, 'text': value})
    assert top + height <= 505, (c.getPageNumber(), top, value[:80])
    return top + height


def page(n: int, heading: str, sub: str) -> None:
    rect(0, 0, W, H, WHITE)
    text(L, 19, 'INTEL | NASDAQ: INTC', 9, 'SansB')
    text(R, 19, 'THOMAS OU | 06 NOV 2026', 9, color=MUTED, align='right')
    para(heading, top=48, size=25, leading=29, font='SansB')
    line(L, 86, R, 86, ACCENT, 1.2)
    para(sub, top=98, size=11, leading=15, color=MUTED)
    line(L, 513, R, 513, ACCENT)
    text(L, 522, 'RESEARCH REVISION | NOT A FINALIZED SUBMISSION', 8, color=MUTED)
    text(R, 522, f'{n:02d} / 10', 8, color=MUTED, align='right')


def foot(value: str) -> None:
    para(value, top=485, size=8.2, leading=10, color=MUTED)


def banner(value: str, top: float = 443) -> None:
    rect(L, top, 880, 34, INK)
    para(value, x=L + 12, top=top + 8, width=856, size=11.5, leading=15, color=WHITE, font='SansB')


def table(headers: list, rows: list, top: float, widths: list, x: float = L, row_h: float = 34, size: float = 11) -> float:
    rect(x, top, sum(widths), 28, INK)
    left = x
    for i, h in enumerate(headers):
        text(left + 8 if i == 0 else left + widths[i] - 8, top + 9, h, 9, 'SansB', WHITE, 'left' if i == 0 else 'right')
        left += widths[i]
    y = top + 28
    for i, row in enumerate(rows):
        if i % 2 == 0:
            rect(x, y, sum(widths), row_h, PALE)
        left = x
        for j, v in enumerate(row):
            text(left + 8 if j == 0 else left + widths[j] - 8, y + (row_h - size) / 2, v, size, color=INK, align='left' if j == 0 else 'right')
            left += widths[j]
        line(x, y + row_h, x + sum(widths), y + row_h)
        y += row_h
    return y


page(1, "Intel's price edge still depends on future profits.", 'Research review | December 2030 horizon | Reference price: $52.25 at the November 5 regular close')
para('<b>The operating recovery is credible.</b> New Xeon products have real customers, richer product mix and improved segment profit. The unresolved question is how much cash Intel keeps after the capacity ramp, manufacturing costs and customer renewals.', top=136, size=15, leading=22, width=860)
for x, title, value, detail in [(40, 'SELECTED PLANNING CASE', '$53.43', '0.5% annual price return'), (340, 'FAVORABLE OPERATIONS + RATE', '$82.47', '11.6% annual price return'), (640, 'REFERENCE ENTRY', '$52.25', 'November 5, 2026 close')]:
    rect(x, 236, 280, 108, PALE)
    text(x + 14, 250, title, 9, 'SansB', MUTED)
    text(x + 14, 274, value, 31, 'BodyB', ACCENT)
    text(x + 14, 318, detail, 11)
para('These are <b>unweighted scenarios</b>, not probabilities. Favorable operations use stronger Q4 starting points, faster CPU growth and the 44.9% pooled margin anchor. They give $73.56 at the selected 11.555% asset rate, or $82.47 at the alternative 10.625% calibration. Neither operating path is a proved expectation.', top=366, size=12, leading=17)
banner('Research conclusion: the evidence does not yet establish a strong LONG or SHORT at $52.25.')
foot(link('Reference quote', URL['quote']) + ' | Model dates and assumptions are on pages 7-8. M37 requires LONG or SHORT; this review does not finalize that choice.')
c.showPage()

page(2, 'Intel must turn product demand into manufacturing profit.', 'Business overview and selected operating-profit bridge | USD billions; all forward figures are analyst forecasts')
para('Intel sells PC processors to device makers and server / custom chips to cloud and enterprise customers. Products generate 94% of selected 2027 external sales. Foundry manufactures chips, develops processes and sells external wafer / packaging services. Other includes Mobileye driving systems and IMS mask-writing equipment.', top=135, size=12, leading=17)
profit_rows = []
for label_text, field in [('PCs and client platforms (CCPG)', 'CCPG_profit_B'), ('Servers, custom and network (DCAI)', 'DCAI_profit_B'), ('Foundry, including embedded packaging', 'Foundry_profit_B'), ('New packaging: net added profit', 'net_packaging_profit_B'), ('Other profit less corporate costs', 'Other_profit_less_corporate_B'), ('Group EBIT after economic SBC', 'EBIT_B')]:
    a, b = ROWS[2027][field], ROWS[2030][field]
    profit_rows.append([label_text, f'{a:.2f}', f'{b:.2f}', f'{b-a:+.2f}'])
table(['Operating profit', '2027', '2030', 'Change'], profit_rows, 213, [475, 135, 135, 135], row_h=27, size=10.8)
para('Gross packaging sales grow from $0.5B to $7.0B: a 14x forecast ramp. Of the 2030 program, $2B sales / $0.5B profit is already allowed inside Foundry. Only incremental profit is added; capital is funded.', top=412, size=10.5, leading=13)
banner('Foundry supplies 32.6% of the modeled 2027-30 EBIT increase. This is a major execution assumption.')
foot(link('Intel Q3 segment economics and Foundry costs', URL['q3']) + ' | Products pay internal manufacturing charges; internal sales are eliminated. DCAI product-profit recovery does not by itself prove Foundry cost recovery.')
c.showPage()

page(3, 'After consolidation, the near-term forecast is close to consensus.', 'All sales are external; internal Foundry transfers are eliminated | USD billions')
table(['External revenue', '2026E', '2027 selected', '2027 favorable'], [
    ['Server CPUs', '21.86', '30.41', '31.74'], ['Other DCAI', '5.19', '8.30', '8.08'], ['CCPG', '30.77', '26.92', '28.39'],
    ['Products subtotal', '57.82', '65.63', '68.21'], ['Net All Other + legacy Foundry', '3.81', '3.71', '3.71'], ['Gross new packaging', '-', '0.50', '0.50'], ['Consolidated revenue', '61.63', '69.85', '72.42'],
], 135, [340, 180, 180, 180], row_h=31)
para('<b>Published 2027 company-sales proxy: $69.27B.</b> The selected case is 0.8% higher; the favorable starting-point case is 4.6% higher. The chosen PC recovery and server ramp are assumptions. This source does not provide a matched CPU consensus.', top=394, size=11.5, leading=16)
banner('A correct revenue bridge closes an accounting gap; it does not create new operating profit.')
foot(link('Intel Q3: segment consolidation', URL['q3']) + ' | ' + link('Intel Q2: external Foundry', URL['q2']) + ' | ' + link('S&P forecast proxy, November 5', URL['consensus']) + '. Legacy Foundry and All Other forecasts are analyst assumptions.')
c.showPage()

page(4, 'The delivery forecast is explicit. Its starting point is still uncertain.', 'Quarterly CPU sales = Q4 estimated sales x unit index x ASP index | Indices are not physical chip counts')
table(['2027 CPU forecast', 'Q1', 'Q2', 'Q3', 'Q4'], [
    ['Unit index, Q4:26 = 100', '100.0', '105.0', '115.5', '127.1'], ['ASP index, Q4:26 = 100', '100.0', '102.0', '105.1', '108.2'], ['CPU sales ($B)', '6.53', '6.99', '7.92', '8.97'],
], 135, [344, 134, 134, 134, 134], row_h=37)
para('<b>Selection rationale.</b> Hold Q1 flat under tight supply, allow modest Q2 improvement, then stronger H2 deliveries as capacity and substrates arrive. After 2027, sequential growth fades rather than assuming another acceleration.', top=289, width=420, size=12, leading=17)
para('<b>A stronger Q4 anchor also matters.</b> A guide-compatible starting point produces $31.74B CPU and $28.39B CCPG sales in 2027. Its Q4 company revenue is $15.89B, inside the $15-16B range. The lower anchor is not uniquely identified by guidance.', x=500, top=289, width=420, size=12, leading=17)
para('Ireland output, wafer throughput and announced substrate additions do not identify customer-accepted package counts. The quarterly path makes the required execution measurable; it does not prove that execution.', top=390, size=11.5, leading=16, color=MUTED)
banner('The evidence supports the timing story more strongly than any one exact growth rate.')
foot(link('Q3 guidance and timing', URL['q3remarks']) + ' | ' + link('Published Q3 Q&A', URL['call']) + ' | ' + link('August Ireland output comments', URL['ireland']) + '. Q4 anchors, quarterly rates and allocation choices are forecasts.')
c.showPage()

page(5, 'The margin case needs two businesses, not one fixed percentage.', 'CPU product economics and lower-margin custom / network products can evolve differently')
table(['Conditional CPU operating margin', 'Margin', 'What it tells us'], [
    ['YTD 2026 residual; Other at 20%', '41.7%', 'Selected mature anchor'], ['Pooled Q2 + Q3 residual', '44.9%', 'Credible stronger anchor'], ['Q3 residual', '46.6%', 'Latest-quarter economics'], ['Needed for 40% DCAI at selected mix', '48.1%', 'Future operating hurdle'],
], 136, [455, 100, 325], row_h=39)
para('<b>The stronger margin case has an economic mechanism.</b> At selected later mix and 20% Other margin, 40% DCAI needs CPU margin about 1.5 points above the Q3 residual. Expense leverage and costs rising more slowly than price could deliver it.', top=331, width=420, size=12, leading=17)
para('<b>It is also not established by a pricing agreement.</b> Contract coverage, net prices, cost allocation and renewal terms are not public. The selected mix-based result reaches 35.4% DCAI margin in 2040.', x=500, top=331, width=420, size=12, leading=17)
banner('Margin anchors are conditional allocations. They are not disclosed CPU margins or future floors.')
foot(link('Q2 segment economics', URL['q2']) + ' | ' + link('Q3 segment economics and cost discussion', URL['q3']) + ' | ' + link('Q1 signed DCAI agreements', URL['q1remarks']) + '. Other margin and future costs are explicit assumptions.')
c.showPage()

page(6, 'Cash conversion pays for the ramp before it rewards shareholders.', 'Selected 2027-30 cumulative cash bridge and quarterly liquidity | USD billions')
sumrow = lambda key: sum(ROWS[y][key] for y in range(2027, 2031))
netcredit = sumrow('old_credit_collection_B') + sumrow('new_credit_collection_B') - sumrow('credit_basis_loss_tax_B')
financing = sum(F[y]['owner_cash_B'] - ROWS[y]['parent_unlevered_cash_B'] for y in range(2027, 2031))
table(['Cumulative bridge', '$B'], [
    ['Operating profit after economic SBC', f'{sumrow("EBIT_B"):.2f}'], ['Ordinary operating tax', f'({sumrow("ordinary_operating_tax_B"):.2f})'], ['Net investment: capex - D&A + WC', f'({sumrow("net_operating_investment_B"):.2f})'], ['Lease + minority-owner cash', f'({sumrow("lease_cash_B") + sumrow("minority_cash_B"):.2f})'], ['Net capital-credit cash / tax cost', f'{netcredit:.2f}'], ['Net financing cash', f'({-financing:.2f})'], ['Owner cash after financing', f'{sum(F[y]["owner_cash_B"] for y in F):.2f}'],
], 135, [365, 105], row_h=31, size=10.7)
text(545, 139, 'QUARTER-END ECONOMIC CASH', 10, 'SansB', MUTED)
plot_x, plot_y, plot_w, plot_h = 555, 180, 340, 145
for level in [20, 30, 40, 50]:
    yy = plot_y + plot_h * (55 - level) / 40
    line(plot_x, yy, plot_x + plot_w, yy)
    text(plot_x - 10, yy - 5, str(level), 8, color=MUTED, align='right')
for key, color in [('base', ACCENT), ('concentrated_timing_stress', RED)]:
    vals = CASH[key]['quarterly_rows']
    for i in range(15):
        p1 = plot_y + plot_h * (55 - vals[i]['ending_cash_B']) / 40
        p2 = plot_y + plot_h * (55 - vals[i + 1]['ending_cash_B']) / 40
        line(plot_x + plot_w * i / 15, p1, plot_x + plot_w * (i + 1) / 15, p2, color, 1.8)
text(555, 337, '2027', 9, color=MUTED)
text(895, 337, '2030', 9, color=MUTED, align='right')
para('<b>Base minimum: $29.33B.</b><br/><font color="#A9483C">Concentrated timing: $18.03B.</font><br/>Positive cash, but about $1.97B below the chosen $20B buffer. That buffer is not a covenant.', x=545, top=361, width=370, size=11.5, leading=16)
banner('The grant receivable, capital credits, SBC and minority cash are each counted once.')
foot(link('Intel balance sheet and commitments', URL['q3']) + ' | ' + link('Mobileye grant timing', URL['mobileye']) + '. Stress moves receipts and spending within each year; it does not change annual totals. Daily access and refinancing are not guaranteed.')
c.showPage()

page(7, 'Most of the value still comes after the competition horizon.', 'Adjusted present value | Annual-end discounting | 11.555% operating rate, 3% terminal growth, 5.51B share claims')
v26, v30 = M['values']['2026'], M['values']['2030']
table(['Equity bridge ($B, except per share)', 'Dec. 2026', 'Dec. 2030'], [
    ['Explicit operating cash value', f'{v26["explicit_operating_PV_B"]:.2f}', f'{v30["explicit_operating_PV_B"]:.2f}'],
    ['Terminal operating cash value', f'{v26["terminal_operating_PV_B"]:.2f}', f'{v30["terminal_operating_PV_B"]:.2f}'],
    ['Financing tax-benefit value', f'{v26["financing_shield_PV_B"]:.2f}', f'{v30["financing_shield_PV_B"]:.2f}'],
    ['Cash - debt + other assets / commitments', f'{v26["equity_B"]-v26["total_operating_value_B"]-v26["financing_shield_PV_B"]:.2f}', f'{v30["equity_B"]-v30["total_operating_value_B"]-v30["financing_shield_PV_B"]:.2f}'],
    ['Equity value', f'{v26["equity_B"]:.2f}', f'{v30["equity_B"]:.2f}'], ['Per share', '$35.40', '$53.43'],
], 135, [500, 190, 190], row_h=33)
para('<b>93.2%</b> of December 2026 operating value comes from cash after 2030; <b>44.2%</b> comes from the terminal period after 2040. The business can deliver a good 2027 without validating the later cash flows.', top=377, size=12, leading=17)
banner('A $53.43 future target is not $53.43 of value today. Dates and retained cash matter.')
foot('Reproduced operating-cash model. No dividend, multiple rerating or declining discount rate is credited. The November 5 quote precedes the December 31 planning value by 56 days. Implied incremental terminal returns are assumptions, not measured ROIC.')
c.showPage()

page(8, 'Both operating execution and the risk calibration affect the decision.', 'Same $52.25 entry and December 2030 horizon | Fixed asset rate shown for each case; no assigned probabilities')
table(['Scenario', 'Dec. 2026 value', '2030 target', 'Annual return'], [
    ['Selected operations | 11.555%', '$35.40', '$53.43', '0.5%'], ['Selected operations | 10.625%', '$40.77', '$59.68', '3.3%'], ['Favorable operations | 11.555%', '$48.56', '$73.56', '8.6%'], ['Favorable operations | 10.625%', '$56.14', '$82.47', '11.6%'], ['Selected sales; Foundry recovery delayed 2 years | 11.555%', '$33.67', '$50.95', '(0.6%)'], ['Selected sales; Foundry only breaks even | 11.555%', '$31.48', '$47.45', '(2.3%)'], ['Slower deliveries | 11.555%', '$25.22', '$38.13', '(7.3%)'],
], 135, [475, 135, 135, 135], row_h=30, size=10.2)
para('<b>The alternative rate is a pre-existing method control.</b> Both use 4.94% Treasury and 1.5 asset beta. NYU\'s sustainable-payout premium is 4.41%; its trailing-cash premium is 3.79%. Choosing a payout method does not establish Intel\'s operating outcome.', top=385, size=11.2, leading=15)
banner('A plausible favorable long exists. The research has not established the conviction to make it the recommendation.')
foot(link('NYU monthly ERP data: November 1, 2026', URL['erp_monthly']) + '. Both future payout conventions and the asset beta are assumptions. Foundry stresses hold product sales, depreciation and capital fixed; cost misses are not charged twice.')
c.showPage()

page(9, 'A matched workload check limits the broad pricing-power claim.', 'Original reanalysis of public RunsOn records | Five paired Rust builds, October 25-November 4; no workload run by us')
table(['Same advertised 8-vCPU / 32-GiB x64 shape', 'Intel Xeon 6', 'AMD Turin'], [
    ['Median successful job time', '114 seconds', '87 seconds'], ['Mean normalized EC2 + EBS cost / success', '$0.015553', '$0.013818'], ['Correctness checks in each of 10 logs', '45 / 45 pass', '45 / 45 pass'],
], 135, [540, 170, 170], row_h=37)
para('<b>AMD was faster and cheaper at normalized on-demand rates in all five pairs.</b> Estimated direct cost is 11.2% lower; the alternate shutdown window narrows the advantage to 7.8%. Intel has four physical cores with SMT here; AMD has eight. This compares purchasable cloud shapes, not equal-core architecture.', top=287, size=11.5, leading=16)
para('<b>Still unproved:</b> a complete actual bill, production-wide TCO, Intel procurement prices and supplier margins. Named AWS customer testimonials support Intel value in other workloads. This test does not justify a company-wide revenue or margin haircut.', top=363, size=11.5, leading=16)
banner('We can verify successful work and bounded cost arithmetic. We cannot infer Intel net pricing from it.')
foot('Data attribution: ' + link('RunsOn methodology (CC BY 4.0)', URL['runson']) + ' | ' + link('Frozen raw archive', URL['runson_raw']) + ' | ' + link('Official AWS price feed', URL['aws_prices']) + '. Repriced at on-demand rates; most observed runs used spot. Costs are estimates, not invoices.')
c.showPage()

page(10, 'Sources, model boundaries and submission status', 'Public evidence reviewed through November 6, 2026; source facts are separate from analyst forecasts')
source_groups = [
    ('Financial reporting', [('Intel Q3 2026 filing', 'q3'), ('Intel Q2 2026 filing', 'q2'), ('Mobileye Q3 results and grant timing', 'mobileye')]),
    ('Management and customer evidence', [('Intel Q1 signed agreements', 'q1remarks'), ('Intel Q3 prepared remarks', 'q3remarks'), ('Published Q3 Q&A', 'call'), ('AWS X8i customers', 'aws'), ('Google C4 launch', 'google'), ('MediaTek customer-side packaging work', 'mediatek')]),
    ('Market, contracts and original reanalysis', [('S&P revenue proxy', 'consensus'), ('Reference quote', 'quote'), ('Altera agreement', 'altera'), ('RunsOn method', 'runson'), ('Frozen raw data', 'runson_raw')]),
]
top = 134
for title, items in source_groups:
    text(L, top, title, 12, 'SansB')
    para(' | '.join(link(label, URL[key]) for label, key in items), top=top + 22, size=10.5, leading=16)
    top += 75
para('<b>Model boundaries.</b> Volume indices are not physical chip counts. Segment residuals are not disclosed CPU margins. New packaging has explicit capital and profit overlap deductions. Revenue growth, tax rates, capital productivity, post-2030 renewals and the discount rate remain assumptions.', top=365, size=11, leading=15)
banner('M37 requires LONG or SHORT. This research review does not yet provide a finalized recommendation.')
foot(link('Official M37 rules', URL['rules']) + ': initial PDF <=10 pages, due November 9, 2026; name, class year and resume required. No exact deadline hour/timezone is published on the reviewed page. Nothing has been submitted.')
c.save()


styles = {
    'title': ParagraphStyle('title', fontName='SansB', fontSize=19, leading=23, textColor=INK, spaceAfter=10),
    'sub': ParagraphStyle('sub', fontName='Sans', fontSize=10, leading=14, textColor=MUTED, spaceAfter=12),
    'body': ParagraphStyle('body', fontName='Sans', fontSize=10.5, leading=14.5, textColor=INK, spaceAfter=8),
    'q': ParagraphStyle('q', fontName='SansB', fontSize=11, leading=15, textColor=INK, spaceBefore=8, spaceAfter=5),
    'small': ParagraphStyle('small', fontName='Sans', fontSize=9, leading=12, textColor=MUTED, spaceAfter=7),
}


def p(value: str, style: str = 'body') -> Paragraph:
    return Paragraph(value.replace('D&A', 'D&amp;A').replace('Q&A', 'Q&amp;A'), styles[style])


def qa(question: str, answer: str) -> list:
    return [p(question, 'q'), p(answer)]


def doc_table(headers: list, rows: list, widths: list) -> Table:
    content = [[p(str(x), 'small') for x in row] for row in [headers] + rows]
    t = Table(content, colWidths=widths, hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), PALE), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('LINEBELOW', (0, 0), (-1, -1), .4, RULE)]))
    return t


def build_letter(destination: Path, pages: list, label: str) -> None:
    story = []
    for i, content in enumerate(pages):
        if i:
            story.append(PageBreak())
        story.extend(content)

    def frame(cv, doc):
        cv.setStrokeColor(ACCENT)
        cv.line(48, 752, 564, 752)
        cv.setFillColor(MUTED)
        cv.setFont('Sans', 8)
        cv.drawString(48, 764, f'THOMAS OU | INTEL | {label}')
        cv.line(48, 39, 564, 39)
        cv.drawString(48, 25, 'Research preparation - excluded from the competition screen')
        cv.drawRightString(564, 25, f'{doc.page} / {len(pages)}')

    doc = SimpleDocTemplate(str(destination), pagesize=(612, 792), leftMargin=48, rightMargin=48, topMargin=59, bottomMargin=51, title=f'Intel | {label}', author='Thomas Ou')
    doc.build(story, onFirstPage=frame, onLaterPages=frame)
    assert len(PdfReader(destination).pages) == len(pages), destination


notes_pages = [
    [p('The decision you need to defend', 'title'), p('Updated research, not a promised competition result', 'sub'),
     *qa('Did the research disprove the old long?', 'No. The old 2027 forecast can be reached with guide-compatible starting points or modestly stronger second-half deliveries. The new model improves accounting and exposes assumptions; it does not establish which future scenario is most likely.'),
     *qa('What is the main weakness now?', 'Conviction in the operating and valuation assumptions together. Selected operations give $53.43 and 0.5% annual appreciation. Favorable operations give $73.56 at the selected asset rate, or $82.47 and 11.6% at a pre-existing alternative 10.625% calibration. The latter has $56.14 December 2026 planning value versus the $52.25 quote. These are conditional cases, not assigned probabilities.'),
     *qa('Why not simply call it a short?', 'A low current DCF estimate is not enough to establish a profitable 3-5-year short. The selected future target is slightly above the reference price; favorable execution can be much higher. Borrow costs, timing and upside risk also matter. A weak long is not automatically a strong short.'),
     *qa('Could a long still be valid?', 'Yes. New-platform economics, customer value and manufacturing learning provide a coherent positive mechanism. The favorable operating case and alternative risk calibration can support a long. That does not establish it as the most likely case. M37 specifies LONG or SHORT but no minimum upside or required valuation method.'),
     *qa('Is this submission-ready?', 'No finalized LONG/SHORT recommendation is claimed. The research screen is ten pages; the workbook and notes are supporting material. Confirm class year and attach the required resume before submission. The reviewed rules state November 9, 2026 without an exact deadline hour.'),
     p(link('M37 rules', URL['rules']) + ' | ' + link('Current quote reference', URL['quote']), 'small')],
    [p('Revenue and profit: defend the assumptions', 'title'), p('What the arithmetic proves, and what it does not', 'sub'),
     *qa('Why do the quarterly indices not prove shipped units?', 'Intel publishes percentage changes and rounded revenue categories, not a matched physical shipment series. Quarterly and YTD Other revenue do not add exactly. The index is a transparent calibration; another feasible calibration changes the split between annual volume and ASP without changing the selected forecast dollars.'),
     *qa('What supports the timing?', 'Management describes tighter first-half supply and later relief from substrates and manufacturing additions. The PC inventory correction is concentrated around Q4 and Q1, possibly Q2. These statements support timing and direction more strongly than the exact chosen 5%, 10% or 15% quarterly increases.'),
     *qa('Why does a sales miss reduce group EBIT by 50%?', 'The CFO gives a 40-60% annual incremental gross-profit rule. If nonmanufacturing operating expense is fixed, the gross-profit change reaches EBIT. This is a group scenario convention including manufacturing, not a measured CPU elasticity. We do not add a second Foundry absorption loss. A pure price cut at unchanged cost has 100% EBIT fall-through; 75% and 100% whole-gap controls expose that risk.'),
     *qa('How is the mature CPU margin obtained?', '(7.055 - 20% x 3.3) / (18.632 - 3.3) = 41.71%, using YTD DCAI operating profit and an assumed Other margin. Pooled Q2/Q3 gives 44.91%; Q3 gives 46.62%. These are conditional residuals. The new-platform transition makes recent-quarter economics a credible favorable interpretation; the full-YTD anchor is not statistically superior.'),
     *qa('How much depends on Foundry recovery?', 'Host Foundry supplies $6.5B, or 32.6%, of the 2027-30 group profit increase. Its $2.5B 2030 profit includes embedded packaging and external services. Intel reports node-cost learning, but lower period charges still explain its YTD Foundry improvement. With sales, D&A and capex fixed, a two-year cash-cost recovery delay lowers the target to $50.95; breakeven without later profit gives $47.45.'),
     p(link('Q3 filing', URL['q3']) + ' | ' + link('Q3 Q&A', URL['call']) + ' | ' + link('Q2 prepared remarks', URL['q2remarks']), 'small')],
    [p('Cash, claims and funding', 'title'), p('Avoid counting the same benefit or cost twice', 'sub'),
     *qa('How are external sales consolidated?', 'Products are external. Add net All Other, legacy external Foundry and gross new packaging once. Legacy external Foundry is normalized at $0.934B from first-half 2026; Q3 includes a nonrecurring contract effect. All Other is $2.8B gross less $0.02B internal sales. Completing the revenue denominator does not create new EBIT.'),
     *qa('What about the Mobileye grant?', '2026 adjusted operating-income guidance includes about $190M of grant benefit; associated cash is expected to start in 2028. The model already includes receivables in working capital. We allocate the grant receivable build inside that envelope, rather than subtracting another $190M. The estimated opening grant asset and cash cohorts are assumptions, not a second AMIC credit pool.'),
     *qa('How are SBC, minority claims and interest treated?', 'Economic SBC remains in corporate or program cost once. Minority-owner cash is an explicit proxy, not a statement that reported NCI earnings equal cash distributions. Ordinary cash interest and capitalized cash interest are deducted separately. Only the specified ordinary-interest tax benefit is credited immediately.'),
     *qa('Does quarterly cash prove liquidity is safe?', 'Base quarter-end cash bottoms at $29.33B. Front-loaded capex and delayed receipts reduce it to $18.03B; delaying financing tax benefits too gives approximately $17.83B. Cash remains positive, but the model misses its chosen $20B buffer. This is not a covenant breach or proof of an available credit line. Daily payment timing and legal cash access remain outside this model.'),
     *qa('What is actually source-anchored in the debt calendar?', 'Scheduled senior-note maturities and municipal mandatory tender dates reconcile to $3.826/$3.173/$3.288/$2.750B principal in 2027-30. Tender dates are not final legal maturities. Other treasury timing is disclosed as allocation. The base assumes payment, not successful refinancing.'),
     p(link('Intel commitments and financial claims', URL['q3']) + ' | ' + link('Mobileye grant and guidance', URL['mobileye']) + ' | ' + link('Altera manufacturing agreement', URL['altera']), 'small')],
    [p('Valuation and the strongest long argument', 'title'), p('Use the same entry, cash scope and horizon in every comparison', 'sub'),
     *qa('How does the APV bridge work?', 'Discount parent unlevered cash through 2040; add the 2041 cash tail at 3% growth and separately valued financing tax benefits with zero tail growth. Then add economic cash, subtract ordinary debt, add $4.502B net other assets after claims and remaining escrow less acquisition commitments. Divide by 5.51B planning claims. The $1.215B claim reserve is already deducted once.'),
     *qa('Why are the two valuation dates so different?', 'December 2030 includes cash accumulated during 2027-30 and fewer years of discounting on later operating cash. The November 5 quote is compared with a December 31 planning estimate, a 56-day mismatch clearly disclosed. No dividends, risk-rate compression or multiple rerating are assumed.'),
     *qa('What is the strongest case for the old margin?', 'New Xeon platforms create measurable customer benefits; richer mix need not disappear when shortages ease. At selected later revenue mix, a 40% DCAI margin with Other at 20% needs about 48.12% CPU margin, only 1.50 points above the Q3 residual. With Other at 30%, the required CPU margin is about 44.06%. These are coherent favorable hypotheses, not disproven scenarios.'),
     *qa('Does the favorable case survive a packaging miss?', 'At the same 10.625% rate, remove one assumed $3B customer program and keep all planned 2027-30 capex. Proportional cash-cost avoidance gives $54.25 planning / $79.66 target and 10.7% annual appreciation. With no cash-cost avoidance, those become $50.97 / $74.80 and 9.0%. These endpoints show dependence on cost flexibility; neither assumes that a customer has actually been lost.'),
     *qa('Why are there two legitimate risk calibrations?', 'The 11.555% asset rate uses 4.94% Treasury + 1.5 beta x 4.41% sustainable-payout ERP. The 10.625% alternative uses the same Treasury and beta with 3.79% trailing-cash ERP. Sustainable payout adjusts market distributions as growth matures; trailing cash keeps recent payout behavior. Both are pre-existing methods with assumptions, not evidence that Intel is safer. ' + link('NYU November data, Historical ERP row 220', URL['erp_monthly'])),
     *qa('Is the selected case conservative in every respect?', 'No. Its long-run reinvestment implies about 20.5% incremental return on capital, above its 11.555% asset rate, and it retains a substantial Foundry recovery. Conversely, its faded CPU growth and YTD margin anchor are not proved central estimates. No one scenario should be described as uniquely correct.')],
    [p('What evidence would change the conclusion?', 'title'), p('Prepared answers should identify both the claim and the missing observation', 'sub'),
     doc_table(['Claim', 'What can be checked now', 'What remains unknown'], [
         ['Buyer value', 'Five paired public builds: matching tests; AMD faster and cheaper at normalized on-demand rates', 'Complete paid bill, production TCO and Intel procurement price'],
         ['Delivery capacity', 'Disclosed output, tools, product availability and customer launches', 'Accepted package counts, yields and cancellation rights'],
         ['Profit retention', 'Segment profit and charge bridges; cost-recovery stress at unchanged sales', 'CPU costs, Foundry yield economics and post-LTA renewals'],
         ['Cash conversion', 'Accounting identities, grant lag, debt dates and spending envelopes', 'Exact invoices, cash access and future collections'],
         ['Price edge', 'Required return versus each explicitly funded operating case', 'Future state probabilities and realized market prices'],
     ], [96, 210, 210]), Spacer(1, 12),
     *qa('What does the new workload result establish?', 'The same Rust workflow passes 45 tests in each of ten public logs. Five matched cloud-shape pairs favor AMD by 11.2% in estimated on-demand EC2 + EBS cost; the alternate shutdown window gives 7.8%. Intel has four physical cores here, AMD eight. This is original reanalysis, not our own experiment, a complete invoice or a claim about Intel margins. ' + link('Frozen RunsOn records', URL['runson_raw'])),
     *qa('What would the next earnings report need to show?', 'Rebuild the Q4 CPU anchor from reported DCAI and Other revenue. The selected H1 2027 CPU target is $13.51B. If shipments or mix fall short, recalculate remaining revenue and cash; do not assume the miss reverses automatically. Track total group profit as well as Products, because internal transfer accounting can move profit between segments.'),
     *qa('Can the $7B packaging forecast be verified now?', 'Not from the public evidence reviewed. It assumes two $3B programs plus $1B smaller work. Intel discloses committed demand; MediaTek describes engineering an unnamed US IDM process for 2028. Neither gives Intel accepted package volumes or net fees. No completed original interview is claimed. ' + link('MediaTek CEO answer, pp. 7-8', URL['mediatek'])),
     p('A competition-winning probability cannot be estimated from these scenarios. The work can improve the argument and expose mistakes; it cannot guarantee the judges\' decision.', 'small')],
]
build_letter(OUT / 'm37_intel_defense_notes.pdf', notes_pages, 'DEFENSE NOTES')

comparison_pages = [
    [p('The remaining gap is the investment decision', 'title'), p('Intel versus selected public winning pitches | Updated November 6, 2026', 'sub'),
     p('The revised research now has a full external-revenue bridge, quarterly operating cash, explicit margin components and reproducible valuation. The strongest examples also explain why the purchase price is attractive. That final link remains unresolved here.'),
     doc_table(['Area', 'Useful pattern in strong examples', 'Current Intel assessment'], [
         ['Mechanism', 'Tie a specific business driver to sales, profit and cash.', 'Now explicit: units x ASP, mix, manufacturing, capital and claims.'],
         ['Forecast disagreement', 'Compare the same dated metric with consensus.', 'Selected 2027 sales $69.85B versus $69.27B proxy: only 0.8% higher.'],
         ['Evidence', 'Research changes a forecast input or rejects a case.', 'Five public matched builds limit a broad Intel cost-advantage claim; supplier economics remain unknown.'],
         ['Return at entry', 'Match target date, dividends, cash and downside.', 'Favorable operations: $73.56 at 11.555%, or $82.47 at a pre-existing 10.625% risk calibration.'],
         ['Failure tests', 'State what would change the view.', 'Quarterly revenue, group profit and cash checkpoints are measurable.'],
         ['Presentation', 'Use one claim and a small number of exhibits per page.', 'Ten-page research screen, with detailed model and notes separate.'],
     ], [83, 211, 222]), Spacer(1, 10),
     p('This is a selected sample of public winners from different competitions and horizons. It does not estimate winning odds or establish a numerical quality score. M37 has no published minimum upside, but it does require LONG or SHORT.', 'small'),
     p(link('M37 rules', URL['rules']) + ' | ' + link('UNC official awards archive', URL['unc']) + ' | ' + link('CFA past champions', URL['cfa']), 'small')],
    [p('What to borrow from the examples', 'title'), p('Borrow the reasoning structure; do not treat their forecasts as proved', 'sub'),
     *qa('WMS | UNC 2024 first place', 'Its main argument links material conversion and margin mix to forecasts above consensus. The core narrative fits nine pages; the long appendix supports it. Its forward target and current DCF use different dates. The lesson is a traceable forecast disagreement, not simply presenting a large upside number. ' + link('Official deck', URL['wms'])),
     *qa('JBI | Columbia 2023 first place', 'The deck distinguishes renovation from new construction and connects an ownership overhang to a possible discount. It explains a reason investors might misclassify the business. Intel\'s research explains operational recovery better than it identifies a current investor mistake. ' + link('Official deck', URL['jbi'])),
     *qa('Cargojet | Waterloo 2024 global winner', 'Fleet, utilization, route economics and capital spending connect the operating thesis to cash. The Intel analogue is accepted delivery capacity and the cost to sustain it. A wafer-output announcement alone cannot fill that role. ' + link('Winning presentation', URL['cargo'])),
     *qa('What is different about Intel?', 'Internal manufacturing charges, large reinvestment, government credits, minority owners and a changing product mix make revenue-to-shareholder cash less direct. Those complications must be modeled once. More pages or valuation methods do not compensate for a weak entry price.'),
     *qa('Does a winner need a huge upside?', 'No universal rule follows from the examples. Some prior winners offered modest returns or HOLD recommendations under different rules. M37\'s explicit LONG/SHORT requirement still applies here. A well-reasoned modest-conviction long can be valid, but its assumptions must be chosen and defended honestly.')],
    [p('What this research round actually resolved', 'title'), p('Separate facts repaired from forecasts reconsidered', 'sub'),
     *qa('Accounting and model mechanics: resolved', 'The external-revenue bridge includes legacy Foundry, All Other eliminations and gross new packaging once. Quarterly cash ties to annual totals; principal dates are sourced. The grant receivable, claims, economic SBC and investment overlap are reconciled. Independent annual and quarterly rebuilds match the model.'),
     *qa('Forecast timing: specified, not proved', 'The 2027 model now has separate unit and ASP paths. The 2028-30 CPU path fades sequentially rather than hiding a later reacceleration inside annual growth rates. Favorable Q4 anchors consistent with guidance can restore most of the original 2027 sales. The selected lower path is not uniquely supported by public evidence.'),
     *qa('Margin economics: made explicit', 'CPU and Other margins are separated; 40% blended DCAI remains plausible under favorable scale and mix. Foundry supplies 32.6% of modeled profit growth. Holding sales fixed, breakeven without later Foundry profit lowers the target to $47.45. Packaging backlog supports an opportunity, not the assumed $7B fee base.'),
     *qa('Price edge: sensitive to operating and risk judgment', 'The selected $53.43 target gives about 0.5% annual appreciation. Favorable operations give $73.56 and 8.6%, or $82.47 and 11.6% using the pre-existing trailing-cash ERP method. With that lower rate, a missing $3B packaging program leaves $54.25 planning value if costs adjust, or $50.97 if they stay committed. This preserves a plausible long, with a limited cushion dependent on judgment.'),
     *qa('Submission status', 'The revised ten-page file is a research review, not a finalized competition recommendation. A PASS conclusion is honest but does not satisfy M37\'s LONG/SHORT field. No submission or external message was sent. The next decision is a substantive investment judgment, not a formatting task.'),
     p('The old screen and its $77.46 target remain preserved in the research archive. This revision does not silently present the old target as a calculation error or the new target as a proven outcome.', 'small')],
]
build_letter(OUT / 'm37_intel_pitch_comparison.pdf', comparison_pages, 'COMPARATIVE REVIEW')

manifest = {'built_utc': datetime.now(timezone.utc).isoformat(), 'submitted': False, 'recommendation_finalized': False, 'model_sha256': hashlib.sha256((RUN / 'root/integrated_results.json').read_bytes()).hexdigest(), 'files': [], 'visual_qa': 'pending'}
for name, expected in [('m37_intel_initial_screen.pdf', 10), ('m37_intel_defense_notes.pdf', 5), ('m37_intel_pitch_comparison.pdf', 3)]:
    file = OUT / name
    reader = PdfReader(file)
    assert len(reader.pages) == expected, (name, len(reader.pages))
    content = '\n\n'.join(p.extract_text() for p in reader.pages)
    (TMP / (name.replace('.pdf', '_completion_extracted.txt'))).write_text(content)
    assert '53.43' in content and '73.56' in content, name
    manifest['files'].append({'path': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'pages': expected, 'links': sum(len(p.get('/Annots', [])) for p in reader.pages)})
(TMP / 'completion_build_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(TMP / 'completion_layout_boxes.json').write_text(json.dumps(logs, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
