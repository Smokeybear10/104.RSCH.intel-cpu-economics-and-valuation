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
THESIS = ROOT / 'work/three_hour/active_research/intel_market_share_thesis_2026_11_06'
M = json.loads((THESIS / 'root/active_case.json').read_text())
ROWS = {int(y): r for y, r in M['annual_rows'].items()}
F = {int(y): r for y, r in M['treasury'].items()}
Q = CASH['base']['quarterly_rows']
SUMMARY = {r['case']: r for r in DATA['summary']}
FONT = Path('/System/Library/Fonts/Supplemental')
for name, file in [('Sans', 'Arial.ttf'), ('SansB', 'Arial Bold.ttf'), ('SansI', 'Arial Italic.ttf'), ('Body', 'Georgia.ttf'), ('BodyB', 'Georgia Bold.ttf'), ('Finance', 'Times New Roman.ttf'), ('FinanceB', 'Times New Roman Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT / file)))
pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='SansB', italic='SansI', boldItalic='SansB')
pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyB', italic='Body', boldItalic='BodyB')
INK, MUTED, RULE, ACCENT, PALE, WHITE, RED = [HexColor(h) for h in ['#16283E', '#586575', '#CFD7E0', '#146F67', '#EFF3F7', '#FFFFFF', '#A9483C']]
URL = {
    'fresh_quote': 'https://www.marketscreener.com/quote/stock/INTEL-CORPORATION-4829/quotes/',
    'q1': 'https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000079/intc-20260328.htm',
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
    'trendforce': 'https://www.trendforce.com/presscenter/news/20261022-13279.html',
    'amd_cpu': 'https://newsroom.amd.com/documents/2026/11/84f4476b-f064-4f0f-957c-fe484853e178.pdf?download=1',
    'sp_forecast': 'https://simplywall.st/stocks/us/semiconductors/nasdaq-intc/intel/future',
    'ifast': 'https://fsm.global/sg/article/rcms403584/intel-3q26-pcs-break-the-guide-maintain-sell-at-lower-tp',
    'google_lta': 'https://www.intel.com/content/www/us/en/newsroom/news/artificial-intelligence/intel-google-deepen-collaboration-to-advance-ai-infrastructure.html',
    'ase': 'https://www.sec.gov/Archives/edgar/data/1122411/000095010326016324/dp255760_6k.htm',
    'amkor': 'https://www.sec.gov/Archives/edgar/data/1047127/000104712726000052/amkr-20260930.htm',
    'growth_method': 'https://pages.stern.nyu.edu/~adamodar/New_Home_Page/invfables/growthdeterminants.htm',
    'xeon6980': 'https://www.intel.com/content/www/us/en/products/sku/240777/intel-xeon-6980p-processor-504m-cache-2-00-ghz/specifications.html',
    'xeon8592': 'https://www.intel.com/content/www/us/en/products/sku/237261/intel-xeon-platinum-8592-processor-320m-cache-1-90-ghz/specifications.html',
    'oracle_choices': 'https://www.oracle.com/news/announcement/blog/ai-world-building-the-next-decade-of-oracle-cloud-infrastructure-2026-10-27/',
}


def link(label: str, url: str) -> str:
    return f'<link href="{escape(url, quote=True)}" color="#176A9B"><u>{escape(label)}</u></link>'


W, H, L, R = 1000, 750, 38, 962
INK, MUTED, RULE, ACCENT, PALE, WHITE, RED = [HexColor(h) for h in ['#111111', '#555555', '#C5C5C5', '#0068B5', '#DCE6F1', '#FFFFFF', '#C63F39']]
BLUE2, BLUE3, GRAY = [HexColor(h) for h in ['#5E99C6', '#B9D0E3', '#969696']]
logs = []
screen = OUT / 'm37_intel_initial_screen.pdf'
c = canvas.Canvas(str(screen), pagesize=(W, H), pageCompression=1)
c.setTitle('Intel | Server growth and manufacturing recovery')
c.setAuthor('Thomas Ou')
c.setSubject('M37 initial screen | Conditional LONG at or below $40 | December 2030 target $82.47')


def text(x, top, value, size=12, font='Sans', color=INK, align='left'):
    value = str(value)
    c.setFillColor(color)
    c.setFont(font, size)
    draw = c.drawRightString if align == 'right' else c.drawCentredString if align == 'center' else c.drawString
    draw(x, H - top - size * .84, value)
    width = pdfmetrics.stringWidth(value, font, size)
    start = x - width if align == 'right' else x - width / 2 if align == 'center' else x
    assert start >= 15 and start + width <= W - 15, (c.getPageNumber(), value)
    logs.append({'page': c.getPageNumber(), 'kind': 'text', 'x': start, 'top': top, 'right': start + width, 'bottom': top + size, 'text': value})


def rect(x, top, width, height, color):
    c.setFillColor(color)
    c.rect(x, H - top - height, width, height, fill=1, stroke=0)


def line(x1, top1, x2, top2, color=RULE, width=.7, dash=None):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    c.setDash(dash or [])
    c.line(x1, H - top1, x2, H - top2)
    c.setDash([])


def dot(x, top, radius=3, color=ACCENT):
    c.setFillColor(color)
    c.circle(x, H-top, radius, fill=1, stroke=0)


def para(value, x=L, top=0, width=924, size=13, leading=18, color=INK, font='Sans', align=0):
    value = value.replace('D&A', 'D&amp;A').replace('Q&A', 'Q&amp;A').replace('S&P', 'S&amp;P').replace('R&D', 'R&amp;D')
    p = Paragraph(value, ParagraphStyle('p', fontName=font, fontSize=size, leading=leading, textColor=color, alignment=align))
    _, height = p.wrap(width, 1000)
    p.drawOn(c, x, H - top - height)
    logs.append({'page': c.getPageNumber(), 'kind': 'paragraph', 'x': x, 'top': top, 'right': x+width, 'bottom': top + height, 'text': value})
    assert top + height <= 718, (c.getPageNumber(), top, value[:80])
    return top + height


def logo(x, top, width, alpha=1):
    import re
    import xml.etree.ElementTree as ET
    c.saveState()
    c.setFillAlpha(alpha)
    c.translate(x,H-top)
    c.scale(width/100,-width/100)
    for node in ET.parse(TMP/'intel-logo.svg').getroot().iter():
        if not node.tag.endswith('path'):
            continue
        tokens=re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?',node.attrib['d'])
        path=c.beginPath();i=0;px=py=sx=sy=0;command=None
        while i<len(tokens):
            if tokens[i].isalpha():command=tokens[i];i+=1
            if command=='Z':path.close();px,py=sx,sy;command=None;continue
            count={'M':2,'L':2,'H':1,'V':1,'C':6}[command]
            v=list(map(float,tokens[i:i+count]));i+=count
            if command=='M':px,py=v;sx,sy=v;path.moveTo(px,py);command='L'
            elif command=='L':px,py=v;path.lineTo(px,py)
            elif command=='H':px=v[0];path.lineTo(px,py)
            elif command=='V':py=v[0];path.lineTo(px,py)
            else:path.curveTo(*v);px,py=v[-2:]
        c.setFillColor(HexColor(node.attrib['fill']));c.setFillAlpha(alpha);c.drawPath(path,fill=1,stroke=0)
    c.restoreState()


def page(n, heading, sub, category):
    rect(0,0,W,H,WHITE)
    text(38,31,'M37',30,'SansB')
    text(38,69,'STOCK PITCH COMPETITION',8.5,'SansB')
    line(181,21,181,106,ACCENT,.7)
    rect(198,20,764,36,ACCENT)
    text(210,25,heading,26,'SansB',WHITE)
    para(sub,198,69,764,19,23,font='SansB')
    logo(883,718,47)
    text(956,727,str(n),13,color=MUTED,align='right')
    text(38,733,'Thomas Ou | Class of 2028',8,color=MUTED)


def section(title,x,top,width):
    size=min(14.5,(width-14)/pdfmetrics.stringWidth(title,'SansB',1))
    if c.getPageNumber() in (2,4,5,8,10):
        rect(x,top,width,25,PALE)
        text(x+width/2,top+5,title,size,'SansB',align='center')
    else:
        text(x+3,top+3,title,size,'SansB')
        line(x,top+24,x+width,top+24,INK,.8)


def bullet(value,x,top,width,size=13.5):
    text(x,top+1,'\u2022',size,'SansB')
    return para(value,x+16,top,width-16,size,size+4)


def outline(x,top,width,height,color=RED,dash=(5,3)):
    c.setStrokeColor(color);c.setLineWidth(1.2);c.setDash(dash)
    c.rect(x,H-top-height,width,height,fill=0,stroke=1);c.setDash([])


def foot(value):
    line(L, 679, R, 679, RULE, .5)
    para(value, top=687, size=8.2, leading=10, color=MUTED)


def arrow(x1, y1, x2, y2, color=ACCENT):
    from math import atan2, cos, sin
    line(x1,y1,x2,y2,color,1)
    a=atan2(y2-y1,x2-x1)
    for d in (-.5,.5):
        line(x2,y2,x2-7*cos(a+d),y2-7*sin(a+d),color,1)


def bracket(x1, x2, top, label, color=ACCENT):
    line(x1,top+5,x1,top,color,1)
    line(x1,top,x2,top,color,1)
    line(x2,top,x2,top+5,color,1)
    text((x1+x2)/2,top-16,label,10.5,'SansB',color,align='center')


def note(num, title, body, x, top, width, color=ACCENT):
    dot(x+8,top+8,8,color)
    text(x+8,top+3,str(num),9,'SansB',WHITE,align='center')
    text(x+24,top,title,12,'SansB',color)
    return para(body,x+24,top+20,width-24,11.6,16)



def table(headers, rows, top, widths, x=L, row_h=34, size=12, highlights=(), alignments=None):
    total = sum(widths)
    alignments = alignments or [0] + [2] * (len(widths) - 1)
    finance = c.getPageNumber() == 7
    rect(x, top, total, 29, ACCENT)
    left = x
    for i,h in enumerate(headers):
        para(str(h), left+8, top+7, widths[i]-16, 11.2, 12, WHITE, 'FinanceB' if finance else 'SansB', alignments[i])
        left += widths[i]
    y=top+29
    for i,row in enumerate(rows):
        if i in highlights:
            rect(x,y,total,row_h,PALE)
        left=x
        for j,v in enumerate(row):
            font = ('FinanceB' if i in highlights else 'Finance') if finance else ('SansB' if i in highlights else 'Sans')
            cell_size = size+1 if finance else size
            pp=Paragraph(str(v),ParagraphStyle('cell',fontName=font,fontSize=cell_size,leading=size+3,textColor=INK,alignment=alignments[j]))
            _,ph=pp.wrap(widths[j]-16,500)
            assert ph<=row_h-8,(c.getPageNumber(),str(v),ph,row_h)
            para(str(v),left+8,y+(row_h-ph)/2,widths[j]-16,cell_size,size+3,INK,font,alignments[j])
            left+=widths[j]
        line(x,y+row_h,x+total,y+row_h)
        y+=row_h
    line(x,top,x,y,INK,.6);line(x+total,top,x+total,y,INK,.6)
    col=x
    for w in widths[:-1]:
        col+=w;line(col,top,col,y,INK,.45)
    return y


def number(value):
    return f'({-value:.2f})' if value < 0 else f'{value:.2f}'


def grid(x, top, width, height, maximum, ticks, minimum=0):
    def yy(v): return top+height-(v-minimum)/(maximum-minimum)*height
    for v in ticks:
        y=yy(v)
        line(x,y,x+width,y, RULE if v else GRAY,.5 if v else .8)
        text(x-9,y-5,f'{v:g}',10,color=MUTED,align='right')
    return yy


def legend(items,x,top,gap=125):
    for i,(name,color) in enumerate(items):
        rect(x+i*gap,top+2,10,10,color)
        text(x+16+i*gap,top,name,10.5)


MARKET = json.loads((THESIS / 'market/market_share_bridge_results.json').read_text())
LIQ = json.loads((THESIS / 'root/owned_quarterly_cash_results.json').read_text())
BENCH = json.loads((RUN / 'workload/matched_build_results.json').read_text())
BASE_CPU = MARKET['FY2026_baselines']['favorable_estimate_B']
REPAIR = ROOT / 'work/three_hour/active_research/intel_weakness_repair_2026_11_06'
CPU_CHECK = json.loads((REPAIR / 'cpu/cpu_ramp_results.json').read_text())
FACTORY_CHECK = json.loads((REPAIR / 'factory/factory_results.json').read_text())
VALUE_CHECK = json.loads((REPAIR / 'valuation/current_hurdles_results.json').read_text())
JOINT_CHECK = json.loads((REPAIR / 'valuation/delivery_joint_results.json').read_text())
LIQ_CHECK = json.loads((REPAIR / 'valuation/quarterly_overlay_results.json').read_text())
RESOLUTION = ROOT / 'work/three_hour/active_research/intel_valuation_resolution_2026_11_06'
EXIT_CHECK = json.loads((RESOLUTION / 'valuation/valuation_resolution_results.json').read_text())
FUNDING = json.loads((RESOLUTION / 'claims/claims_and_funding_results.json').read_text())
REBUILD = ROOT / 'work/three_hour/active_research/intel_fundamental_rebuild_2026_11_06'
REVERSE = json.loads((REBUILD / 'valuation/valuation_rebuild_results.json').read_text())
PACK_CHECK = json.loads((REBUILD / 'factory/packaging_margin_controls.json').read_text())
DEFENSE_RUN = ROOT / 'work/three_hour/active_research/intel_defense_strengthening_2026_11_07'
DEFENSE_CASH = json.loads((DEFENSE_RUN / 'valuation/funded_cash_bridge_results.json').read_text())['cases']
COMBINED_FUNDED = DEFENSE_CASH['joint_plus_CPU_delay']
COMBINED_CAPITAL = DEFENSE_CASH['joint_plus_CPU_delay_plus_2031_2040_capital060']
REVERSE_12 = [r for r in REVERSE['reverse_operating_thresholds'] if r['annual_return_hurdle'] == .12]
REFERENCE, ENTRY_LIMIT = 56.28, 40.0
RETURN_YEARS = EXIT_CHECK['quotes_and_horizons']['current']['years_to_exit']
def price_return(target, entry=REFERENCE):
    return (target / entry) ** (1 / RETURN_YEARS) - 1

def funding_case(name, rate=.08):
    return next(r for r in FUNDING['cases'][name] if r['timing']=='concentrated_timing_stress' and r['annual_simple_rate']==rate and r['immediate_cash_tax_benefit_fraction']==0)

CPU_FUND = funding_case('one_quarter_CPU_ramp_delay')
FACTORY_FUND = funding_case('Foundry_breakeven_also_applies_to_terminalROC_joint_cases')
assert LIQ['input_files']['active_case']['sha256'] == hashlib.sha256((THESIS/'root/active_case.json').read_bytes()).hexdigest()

# 1. Recommendation and three investment arguments.
page(1,'Intel: Growing Through Share Loss','Conditional LONG at $40 or below | $82.47 December 2030 target','')
para('NASDAQ: INTC | Reference: $56.28 at the November 6, 2026 close | Core return at this quote: 9.6% per year',38,122,924,12,16,color=MUTED)
text(260,159,'Investment Thesis',17,'SansB',align='center')
line(179,179,341,179,INK,1)
text(738,159,'What Drives the Forecast?',17,'SansB',align='center')
line(623,179,853,179,INK,1)
claims=[
 ("Market expansion can absorb Intel's loss of CPU shipment share",
  '<b>40% industry growth offsets a decline from 50% to 42% share.</b> Intel units still rise 17.6%. The $31.74B revenue forecast also requires 21.9% higher annual ASP.'),
 ('Xeon volume and richer configurations drive sales above consensus',
  '<b>25% unit growth and 8% ASP growth in 2028</b> lift company sales to $90.01B, versus $83.72B consensus. Cloud deployments support adoption; quantities remain a forecast.'),
 ('Factory recovery increases the profit Intel retains from product sales',
  '<b>Foundry and added packaging contribute $7.73B of EBIT growth.</b> That is 31.5% of the 2027-30 increase, with $124.5B of capex over the same period.')]
for i,(claim,argument) in enumerate(claims):
    y=198+i*111
    pth=c.beginPath();pth.moveTo(38,H-y);pth.lineTo(437,H-y);pth.lineTo(469,H-y-46);pth.lineTo(437,H-y-92);pth.lineTo(38,H-y-92);pth.close()
    c.setFillColor(ACCENT);c.drawPath(pth,fill=1,stroke=0)
    text(69,y+20,str(i+1),45,'Sans',WHITE,align='center')
    para(claim,104,y+17,326,15.2,20,WHITE,'SansB')
    rect(495,y,467,92,HexColor('#F2F2F2'));outline(495,y,467,92,INK,(5,3))
    para(argument,512,y+12,433,14.1,19)
rect(38,539,924,28,ACCENT)
text(500,544,'These drivers put 2028 revenue 7.5% above consensus',16,'SansB',WHITE,align='center')
table(['Company revenue ($B)','My forecast','Consensus','Difference'],[
 ['2027E','72.42','69.27','+4.6%'],['2028E','90.01','83.72','+7.5%']
],579,[369,185,185,185],row_h=29,size=13,highlights=(1,))
foot('Sources: '+link('November 6 quote',URL['fresh_quote'])+'; '+link('Intel Q3 filing',URL['q3'])+'; '+link('TrendForce',URL['trendforce'])+'; '+link('S&P Global via Simply Wall St',URL['sp_forecast'])+'; analyst model. No new position at $56.28. A $40 entry clears my 12% return hurdle in the joint stress on page 7; it is not a forecast of a price decline. Values remain conditional on delivery. Returns exclude dividends.')
c.showPage()

# 3. Business and consensus.
page(2,'Business Overview','My 2028 sales forecast is $6.3B above consensus','')
section('Products sell chips; Foundry supplies manufacturing and packaging',38,124,924)
for x,w,title,body in [
 (48,258,'INTEL PRODUCTS','Xeon server CPUs and client CPUs<br/>Custom silicon and network products'),
 (371,258,'INTEL FOUNDRY','Internal manufacturing services<br/>External wafers and packaging'),
 (694,258,'CONSOLIDATED INTEL','External customer sales<br/>Products + Foundry earnings')]:
    text(x+5,167,title,14,'SansB',ACCENT)
    para(body,x+5,195,w-10,12.5,17)
text(336,185,'+',27,'SansB',align='center');arrow(633,202,683,202,INK)
text(494,240,'Internal manufacturing revenue is eliminated from consolidated sales',11,'SansI',MUTED,align='center')
section('CPU sales contribute 60% of revenue growth ($B)',38,270,467)
section('Forecast versus published consensus ($B)',528,270,434)
legend([('Server CPU',ACCENT),('Client CPU',BLUE2),('Other',GRAY)],71,309,141)
yy=grid(83,352,384,185,130,[0,40,80,120])
for i,y in enumerate([2027,2028,2030]):
    r=ROWS[y]; vals=[r['CPU_revenue_B'],r['CCPG_revenue_B'],r['consolidated_revenue_B']-r['CPU_revenue_B']-r['CCPG_revenue_B']];x=112+i*126;cum=0
    for v,col in zip(vals,[ACCENT,BLUE2,GRAY]):
        rect(x,yy(cum+v),53,yy(cum)-yy(cum+v),col)
        text(x+26.5,(yy(cum+v)+yy(cum))/2-5,f'{v:.1f}',12,'FinanceB',WHITE,align='center');cum+=v
    text(x+26.5,yy(cum)-19,f'{cum:.2f}',12.5,'FinanceB',align='center');text(x+26.5,546,str(y)+'E',12,align='center')
table(['Company revenue','2027E','2028E'],[
 ['My forecast','72.42','90.01'],['S&P Global consensus','69.27','83.72'],['Difference ($B)','+3.16','+6.30'],['Difference (%)','+4.6%','+7.5%']
],310,[234,100,100],x=528,row_h=37,size=12.3,highlights=(0,3))
outline(864,451,94,36)
bullet('<b>CPU sales add $28.33B</b> of the $47.33B increase in company revenue from 2027 to 2030.',48,585,447,13.5)
bullet('<b>Products supply 94%</b> of modeled 2027 external sales. The case does not need a new high-volume external wafer win.',48,628,447,13.5)
bullet('<b>The measurable disagreement is sales.</b> I have not established a comparable consensus forecast for CPU shipment share or parent cash.',538,496,414,14)
bullet('Higher product profit must survive <b>factory losses and capital spending</b> before it reaches shareholders.',538,581,414,14)
foot('Sources: '+link('Intel segment definitions and eliminations',URL['q3'])+'; '+link('S&P Global series via Simply Wall St, November 6',URL['sp_forecast'])+'; analyst model. Other includes other DCAI, net Other, legacy external Foundry and gross new packaging. Existing external business and $7B of gross 2030 packaging revenue remain in the case.')
c.showPage()

# 4. Shipment and market-size requirements.
page(3,'Thesis 1: A Larger Server CPU Market','Losing eight share points can still mean selling more processors','')
section('1. Market growth can outweigh falling unit share',38,123,470)
section('2. Volume alone does not reach the sales forecast',532,123,430)
yy=grid(79,191,400,173,150,[0,50,100,150]);xs=[98,200,302,404]
for i,((lo,hi),col,label) in enumerate(zip([(0,100),(100,140),(117.6,140),(0,117.6)],[GRAY,BLUE2,RED,ACCENT],['100','+40.0','-22.4','117.6'])):
    rect(xs[i],yy(hi),48,yy(lo)-yy(hi),col);text(xs[i]+24,yy(hi)-18,label,13,'FinanceB',col,align='center')
    if i<3:line(xs[i]+48,yy([100,140,117.6][i]),xs[i+1],yy([100,140,117.6][i]),GRAY,.7,[3,3])
    para(['2026 Intel','Market<br/>growth','Share<br/>50% to 42%','2027 Intel'][i],xs[i]-16,376,80,11,14,align=1)
text(87,159,'Shipment index: Intel 2026 = 100',11,color=MUTED)
unit_sales=BASE_CPU*1.176;mix_increment=ROWS[2027]['CPU_revenue_B']-unit_sales
ry=grid(572,191,358,173,35,[0,10,20,30]);rx=[585,680,775,870]
vals=[BASE_CPU,unit_sales-BASE_CPU,mix_increment,ROWS[2027]['CPU_revenue_B']];cum=0
for i,v in enumerate(vals):
    start=0 if i in (0,3) else cum;end=v if i in (0,3) else cum+v
    rect(rx[i],ry(end),46,ry(start)-ry(end),[GRAY,BLUE2,ACCENT,INK][i]);text(rx[i]+23,ry(end)-18,('+' if i in (1,2) else '')+f'{v:.2f}',13,'FinanceB',align='center')
    if i<3:cum=end;line(rx[i]+46,ry(cum),rx[i]+95,ry(cum),GRAY,.7,[3,3])
    para(['2026E CPU<br/>revenue','Unit<br/>growth','Required<br/>ASP / mix','2027E CPU<br/>revenue'][i],rx[i]-18,376,82,11,14,align=1)
text(579,159,'CPU revenue bridge ($B)',11,color=MUTED)
outline(764,ry(31.739)-24,68,ry(unit_sales)-ry(31.739)+32)
bullet('<b>1.40 x 42% / 50% - 1 = 17.6% unit growth.</b> The industry forecast can absorb an eight-point decline in Intel shipment share.',48,429,450,13.5)
bullet('<b>Annual ASP / mix must rise 21.9%.</b> At 30% industry shipment growth, the same revenue target needs 31.3% ASP growth.',542,429,410,13.5)
section('Slower market growth puts more pressure on price and mix',38,507,924)
required=[]
for g in [.2,.3,.4,.5]:
    units=(1+g)*.42/.50-1;asp=ROWS[2027]['CPU_revenue_B']/BASE_CPU/(1+units)-1
    required.append((g,units,asp))
table(['Industry shipment growth','20%','30%','40%','50%'],[
 ['Implied Intel unit growth',*[f'{u:.1%}' for _,u,_ in required]],
 ['ASP growth needed for $31.74B sales',*[f'{a:.1%}' for _,_,a in required]]
],544,[420,126,126,126,126],row_h=32,size=12.5,highlights=(1,))
outline(710,544,126,93)
para('<b>Counterexample: 10% ASP growth, same unit path.</b> 2027 company sales fall to $69.33B, essentially consensus. Carrying that lower base through unchanged 2028 growth gives $85.84B, only 2.5% above consensus.',48,642,904,12.6,17)
foot('Source: '+link('TrendForce October 22 outlook',URL['trendforce'])+'; analyst calculations. Industry growth and shares are rounded forecasts. 2026 CPU revenue base: $22.14406B. The shipment bridge checks the quarterly sales forecast rather than independently producing it. ASP includes mix; share is measured in shipments.')
c.showPage()

# 4. Market size and duration.
page(4,'Thesis 1: How Much Share Is Required?','The $60B CPU forecast needs 40% dollar share in a $150B market','')
section('Required 2030 CPU revenue share',38,123,461)
section('Vendor forecasts point to a larger CPU market',523,123,439)
xx=lambda v:86+(v-120)/100*372;yy=grid(86,203,372,212,55,[20,30,40,50],minimum=20)
for rev,col in [(ROWS[2030]['CPU_revenue_B'],ACCENT),(49.87783483684855,GRAY)]:
    pts=[(xx(t),yy(rev/t*100)) for t in [120,150,180,220]]
    for a,b in zip(pts,pts[1:]):line(*a,*b,col,2.2)
    for i,((x,y),t) in enumerate(zip(pts,[120,150,180,220])):
        dot(x,y,4,col)
        label_x=x+15 if i==0 and col==GRAY else x-13 if i==3 and col==GRAY else x
        label_y=y-21 if col==ACCENT else y+7 if i==3 else y+15
        text(label_x,label_y,f'{rev/t:.1%}',12.5,'SansB',col,align='left' if i==0 and col==GRAY else 'right' if i==3 and col==GRAY else 'center')
legend([('$60.07B forecast',ACCENT),('$49.88B lower case',GRAY)],71,164,220)
for t in [120,150,180,220]:text(xx(t),428,f'${t}B',12,align='center')
text(274,453,'Assumed server-CPU market in 2030',12,color=MUTED,align='center')
outline(xx(150)-30,yy(40.0473)-26,60,43)
bullet('<b>Different vendor estimates use different dates.</b> AMD describes about $220B in 2030. Intel describes more than $200B over five years from October 2026, approximately 2031.',533,166,419,14)
bullet('<b>TAM arithmetic does not establish Intel capture.</b> At $150B, Intel needs 40.0% of CPU revenue. A $120B market raises that requirement to 50.1%.',533,274,419,14)
bullet('<b>Dollar share can exceed unit share</b> if Intel sells richer packages. The ASP premium must be earned; captive Arm treatment in vendor estimates remains unclear.',533,382,419,14)
section('The model carries CPU growth beyond 2030',38,495,924)
yg=grid(82,555,409,86,12,[0,6,12]);xg=lambda y:112+(y-2031)/9*366
points=[]
for y in range(2031,2041):points.append((xg(y),yg((ROWS[y]['CPU_revenue_B']/ROWS[y-1]['CPU_revenue_B']-1)*100)))
for a,b in zip(points,points[1:]):line(*a,*b,ACCENT,2)
for i in [0,4,9]:
    x,y=points[i];dot(x,y,3.5);g=(ROWS[2031+i]['CPU_revenue_B']/ROWS[2030+i]['CPU_revenue_B']-1)*100
    text(x,y-18,f'{g:.2f}%',11,'SansB',ACCENT,align='center')
for y in [2031,2035,2040]:text(xg(y),649,str(y),11,align='center')
para('<b>$60.07B to $108.03B of CPU sales in 2030-40.</b> Annual growth fades from 10.16% to 3.00%, a 6.0% CAGR. With 92.9% of operating value coming after 2030, sustained profitability matters more than the near-term ramp alone.',533,540,419,14,19)
foot('Sources: '+link('AMD Q3 prepared remarks, p.3',URL['amd_cpu'])+'; '+link('Intel Q3 prepared remarks',URL['q3remarks'])+'; analyst forecast. Market sizes are scenarios, not observed TAM. Whole-server spending and GPUs are excluded. Revenue share = unit share x Intel ASP / market ASP. Long-run growth and required shares are assumptions.')
c.showPage()

# 5. Actual momentum and a testable forecast ramp.
page(5,'Thesis 2: Underwriting the Xeon Ramp','Retaining the modeled Q4 mix preserves most of the sales upside','')
section('CPU sales: derived actuals and my quarterly forecast ($B)',38,123,575)
section('Why I expect mix to persist',637,123,325)
legend([('DCAI less Other',GRAY),('Forecast',ACCENT)],77,162,249)
yy=grid(79,215,510,188,10,[0,2,4,6,8,10])
qvals=[4.117,5.311,5.918,CPU_CHECK['owned_Q4']['CPU_B']]+[q['CPU_revenue_B'] for q in CPU_CHECK['quarterly_2027']]
for i,v in enumerate(qvals):
    x=92+i*63;col=GRAY if i<3 else BLUE2 if i==3 else ACCENT
    rect(x,yy(v),37,yy(0)-yy(v),col)
    text(x+18.5,yy(v)-18,f'{v:.2f}',11.5,'SansB',col,align='center')
    text(x+18.5,416,'Q'+str(i%4+1),11,align='center')
text(205,437,'2026',12,'SansB',align='center');text(457,437,'2027E',12,'SansB',align='center')
line(267,201,267,411,RED,1,[4,3]);text(276,187,'Forecast begins',10.5,'SansB',RED)
para('<b>Q4 is an allocation, not CPU guidance.</b> The $6.81B estimate assumes DCAI +17% and Other DCAI +25% sequentially. Intel guided DCAI to mid-teens growth, with purpose-built silicon growing faster.',48,468,555,12.8,17.5)
bullet('<b>The transition is visible.</b> Q3 server ASP rose 54% and units 10% year over year. Premium mix drove most of the ASP increase; Granite Rapids is now Intel\'s largest server family.',647,164,305,13.1)
bullet('<b>Customers have committed.</b> Intel reported signed long-term DCAI agreements, including Google. They support demand persistence; quantities and net-price floors are undisclosed.',647,287,305,13.1)
bullet('<b>Flat estimated Q4 ASP in 2027:</b> company sales are $71.17B in 2027 and $88.32B in 2028, still 5.5% above 2028 consensus. The 2028 unit and ASP assumptions stay unchanged.',647,410,305,13.1)
section('A first-half miss makes the required second-half ramp much steeper',38,550,924)
table(['2027 H1 outcome','H1 CPU sales ($B)','H2 needed for $31.74B','Required H2 / H1'],[
 ['My forecast','14.11','17.63','+25.0%'],['5% below forecast','13.40','18.34','+36.8%']
],582,[300,208,208,208],row_h=29,size=12.3,highlights=(1,))
foot('Sources: '+link('Intel Q1',URL['q1'])+' / '+link('Q2',URL['q2'])+' / '+link('Q3 filings',URL['q3'])+'; '+link('Q1 agreements, p.4',URL['q1remarks'])+'; '+link('Q3 product mix and guidance',URL['q3remarks'])+'. CPU residuals inherit rounded Other DCAI; quarterly/YTD totals differ by $14M. Q4 is estimated. Flat-ASP control holds Q4 ASP through 2027 with the same unit path, then applies +25% units / +8% ASP in 2028. Core 2027 growth includes $5.10B of exit carryover and $4.49B of further ramp; no price floor is established.')
c.showPage()

# 6. Distinguish reported improvement from the required factory recovery.
page(6,'Thesis 3: Factory Recovery Has a Hurdle','A two-year delay lowers the target to $79.59; breakeven alone gives $75.32','')
section('Quarterly Foundry operating loss ($B)',38,123,449)
section('What drove the Q3 year-over-year improvement?',511,123,451)
yy=grid(80,193,379,206,3,[0,1,2,3])
for i,(label,v) in enumerate([('Q1 2026',2.437),('Q2 2026',2.089),('Q3 2026',1.853),('2027E avg.',1.0)]):
    x=104+i*91;col=GRAY if i<3 else ACCENT
    rect(x,yy(v),49,yy(0)-yy(v),col)
    text(x+24.5,yy(v)-20,f'{v:.2f}',12.5,'SansB',align='center')
    text(x+24.5,410,label,10.5,align='center')
line(359,181,359,428,RED,1,[4,3])
para('<b>46% lower loss than Q3</b><br/>needed for the 2027 forecast',278,151,193,11.7,15,color=ACCENT,align=1)
table(['Q3 Foundry EBIT change ($M)','Amount'],[
 ['Lower period charges','+793'],['Higher operating expenses','(219)'],['Other net change (calculated)','(106)'],['Reported improvement','+468']
],164,[341,110],x=511,row_h=33,size=12,highlights=(3,))
para('<b>The charge benefit exceeds the reported gain.</b> It includes process and inventory costs; it is not all nonrecurring. Removing it is a diagnostic, not normalized earnings.',521,340,431,13.2,18)
para('<b>Management reports lower node costs:</b> Intel 3 costs down about 15% and Intel 18A costs down about 40% since Q1. Those gains are already in current results.',48,454,904,13.2,18)
section('Foundry paths | 2030 target at 10.625%',38,497,487)
section('Packaging margins alone add little',549,497,413)
fc=FACTORY_CHECK['cases']['0.10625']
table(['Foundry path','EBIT ($B)','Target'],[
 ['Owned forecast','2.50',f"${fc['owned_base']['Dec2030_target_USD']:.2f}"],
 ['Recovery two years late','(0.75)',f"${fc['two_year_delay']['Dec2030_target_USD']:.2f}"],
 ['Breakeven; no later profit','0.00',f"${fc['breakeven_only']['Dec2030_target_USD']:.2f}"]
],531,[287,100,100],row_h=28,size=10.8,highlights=(0,))
pack_controls = PACK_CHECK['results']['0.10625']
table(['Program operating margin','2030 target'],[
 ['20% control',f"${pack_controls['rounded_ASE_ATM_Q3_margin20pct_control']['Dec2030_target_USD']:.2f}"],
 ['Owned: 25%, then 27%','$82.47'],
 ['30% control',f"${pack_controls['Intel_attributed_aspiration30pct_control']['Dec2030_target_USD']:.2f}"]
],531,[281,132],x=549,row_h=28,size=10.8,highlights=(1,))
para('ASE reported 20% assembly/test/material operating margin; its mix differs from Intel. The 30% packaging control gives <b>9.8% annual return</b>, or 6.8% at the higher discount rate.',48,647,904,11.5,14)
foot('Sources: '+link('Intel Q2',URL['q2'])+' / '+link('Q3',URL['q3'])+'; '+link('ASE Q3 results',URL['ase'])+'; analyst scenarios. Values use 10.625% unless stated. Factory stresses hold packaging fixed. Packaging controls change total program margins from 2030 onward, including embedded profit; output and capital stay fixed. Peer margins do not validate Intel fees or scale. $7B sales and factory recovery remain forecasts.')
c.showPage()

# 7. Price discipline and an independently framed exit cash check.
page(7,'Valuation: Require a Better Entry','At $56.28, core return is 9.6%; the higher-rate case returns 6.7%','')
v26,v30=M['values']['2026'],M['values']['2030']
section('Adjusted present value ($B, except per share)',38,123,533)
section('Annual returns at $40 under weaker outcomes',595,123,367)
table(['Value component','Dec. 2026','Dec. 2030'],[
 ['Explicit operating cash value',f'{v26["explicit_operating_PV_B"]:.2f}',f'{v30["explicit_operating_PV_B"]:.2f}'],['Terminal operating cash value',f'{v26["terminal_operating_PV_B"]:.2f}',f'{v30["terminal_operating_PV_B"]:.2f}'],['Financing tax benefits',f'{v26["financing_shield_PV_B"]:.2f}',f'{v30["financing_shield_PV_B"]:.2f}'],['Net assets and commitments',f'{v26["equity_B"]-v26["total_operating_value_B"]-v26["financing_shield_PV_B"]:.2f}',f'{v30["equity_B"]-v30["total_operating_value_B"]-v30["financing_shield_PV_B"]:.2f}'],['Equity value',f'{v26["equity_B"]:.2f}',f'{v30["equity_B"]:.2f}'],['Per share','$56.14','$82.47']
],160,[303,115,115],row_h=31,size=11.2,highlights=(4,5))
table(['Scenario','2030 target','Return'],[
 ['Higher-rate core','$73.56','15.8%'],
 ['Selected joint stress','$64.74','12.3%'],
 ['Joint + CPU delay',f"${COMBINED_FUNDED['funded_target_USD']:.2f}",f"{COMBINED_FUNDED['funded_annual_return_at40']:.1%}"],
 ['Joint + CPU + capital',f"${COMBINED_CAPITAL['funded_target_USD']:.2f}",f"{COMBINED_CAPITAL['funded_annual_return_at40']:.1%}"],
 ['Separate adverse bundle','$38.13','(1.1%)'],
],160,[197,85,85],x=595,row_h=31,size=10.5,highlights=(1,))
para('<b>$40 is an entry condition, not a downside floor.</b> Rebuild sales, cash and the remaining horizon after material news. The selected stress retains the faster CPU path; weaker operations can miss my return requirement.',605,363,347,12.6,17)
para('<b>Use both risk methods.</b> The 10.625% rate uses 4.94% Treasury + 1.5 beta x 3.79% ERP. At 11.555%, December 2026 value falls to $48.56. Equity holdings and outstanding commitments are already in the net-asset bridge.',48,396,513,12.8,17.3)
section('Require 15% in the higher-rate core and 12% in the selected joint stress',38,489,924)
funded_joint=next(r for r in FACTORY_FUND['target_effects'] if r['asset_rate']==.11555 and r['terminal_ROC']==.15)['funded_Dec2030_target_USD']
table(['Required annual return','Core $82.47 target','Higher-rate $73.56','Joint stress $64.74'],[
 [f'{h:.0%}',*[f'${target/(1+h)**RETURN_YEARS:.2f}' for target in [v30['price_USD'],73.56082736404235,funded_joint]]] for h in [.1,.12,.15]
],526,[300,208,208,208],row_h=31,size=12,highlights=(1,))
outline(546,617,208,31);outline(754,586,208,31)
foot('Sources: analyst model; '+link('November 6 quote',URL['fresh_quote'])+'; '+link('NYU ERP data',URL['erp_monthly'])+'. Entry = target / (1 + hurdle)^4.1506; hurdles are my judgments. Joint stress uses Foundry breakeven, 15% return on modeled net investment from 2041 and 11.555% rate. Added CPU delay persists; added capital case changes 2031-40 sales/net-investment from 0.80 to 0.60, with separate packaging investment unchanged. First four rows include 8% revolver costs where needed; access is assumed, fees unmodeled. Planning value and quote differ by 55 days.')
c.showPage()

# 8. Scenario effects and their economic channels.
page(8,'Downside Cases','A lower entry improves returns; it does not remove operating risk','')
text(38,128,'Change from the investment case',11.5,'SansB');text(535,128,'December 2026 value / share',11.5,'SansB',align='center');text(823,128,'2030 target',10.5,'SansB',align='right');text(957,128,'Annual return',10.5,'SansB',align='right');line(38,151,962,151,INK,1)
delay=next(r for r in JOINT_CHECK['cases'] if r['case'].startswith('2027 ramp delayed') and r['rate']==.10625)
joint=next(r for r in JOINT_CHECK['cases'] if r['case'].startswith('Foundry breakeven') and r['rate']==.11555 and r['terminal_ROC_assumption']==.15)
scenarios=[('Investment case',56.14,82.47,'9.6%'),
 ('CPU ramp one quarter late; no catch-up',delay['planning_value_USD'],delay['target2030_USD'],f"{price_return(delay['target2030_USD']):.1%}"),
 ('Foundry breakeven; no later profit',51.30550520634877,75.32398954283198,'7.3%'),
 ('Alternative operating rate: 11.555%',48.56,73.56,'6.7%'),
 ('Foundry zero + 15% terminal return + rate',joint['planning_value_USD'],joint['target2030_USD'],f"{price_return(joint['target2030_USD']):.1%}"),
 ('One $3B packaging program absent',50.97,74.80,'7.1%'),
 ('Joint downside: slower case + 11.555%',25.22,38.13,'(9.0%)')]
x0=361;px=lambda v:x0+328*v/65
for i,(label,value,target,ret) in enumerate(scenarios):
    y=165+i*37
    if i==0:rect(38,y-3,924,33,PALE)
    if i==6:line(38,y-6,962,y-6,INK,1)
    text(46,y+7,label,10.8,'SansB' if i==0 else 'Sans');rect(x0,y+1,px(value)-x0,23,ACCENT if i==0 else RED if i==6 else BLUE2)
    text(740,y+6,f'${value:.2f}',11,'SansB',align='right');text(823,y+6,f'${target:.2f}',11,align='right');text(957,y+6,ret,11,align='right')
line(px(56.28),156,px(56.28),416,RED,1,[3,3]);text(px(56.28),427,'$56.28 reference quote',10,'SansB',RED,align='center')
section('The operating results that would change my forecast',38,463,924)
table(['Risk','How it reaches shareholders','What I would monitor'],[
 ['<b>CPU demand / mix</b>','A one-quarter ramp delay cuts 2027 CPU sales to $29.19B; the shortfall is not recovered.','H1 CPU sales of $14.11B. A 5% miss would require 36.8% H2/H1 growth.'],
 ['<b>Factory / packaging</b>','Committed manufacturing costs limit flexibility; a missed program leaves capital underused.','2028 group EBIT of $24.59B; Foundry reaches $2.50B profit in 2030.'],
 ['<b>Duration / discount rate</b>','92.9% of operating value comes after 2030, magnifying the effect of a higher required return.','Revalue at both 10.625% and 11.555%; test slower long-run CPU growth.']
],501,[194,365,365],row_h=47,size=12,alignments=[0,0,0])
foot('Source: analyst model; scenarios have no assigned probabilities. CPU delay, factory and joint stresses retain $124.5B near-term capex. Terminal return means return on modeled net investment; R&D remains expensed. Changes start in 2041. This table precedes incremental funding costs; pages 7 and 9 show the broader combined, funded stress. The joint downside is a separate adverse bundle. Packaging stress retains committed costs; scenario losses are not additive.')
c.showPage()

# 9. Show how operating profit survives investment and reaches parent cash.
page(9,'Cash Conversion: What Intel Must Deliver','$38.94B of EBIT becomes $19.45B of recurring operating cash','')
section('2030 cash bridge | $B, before financing',38,123,585)
section('The cash recovery comes later',647,123,315)
bridge=DEFENSE_CASH['core']['cash_bridge']['2030']
norm=bridge['normalized_parent_operating_cash_B'];tax=bridge['ordinary_operating_tax_B'];invest=bridge['net_operating_investment_B'];leases=bridge['lease_and_minority_cash_B'];credits=bridge['net_finite_credits_B']
cash_bars=[('Group<br/>EBIT',0,bridge['EBIT_B'],INK),('Operating<br/>tax',bridge['EBIT_B']-tax,bridge['EBIT_B'],RED),('Net<br/>investment',norm+leases,bridge['EBIT_B']-tax,RED),('Leases /<br/>minorities',norm,norm+leases,RED),('Recurring<br/>cash',0,norm,ACCENT),('Finite net<br/>credits',norm,norm+credits,BLUE2),('Cash with<br/>credits',0,norm+credits,INK)]
cy=grid(75,196,538,209,45,[0,15,30,45])
for i,(label,lo,hi,col) in enumerate(cash_bars):
    x=85+i*76
    rect(x,cy(hi),42,cy(lo)-cy(hi),col)
    value=hi-lo;text(x+21,cy(hi)-19,('-' if i in (1,2,3) else '+' if i==5 else '')+f'{value:.2f}',11.4,'FinanceB',col,align='center')
    para(label,x-12,418,68,10.7,13.5,align=1)
    if i in (0,1,2):line(x+42,cy(lo if i else hi),x+76,cy(lo if i else hi),GRAY,.7,[3,3])
table(['Parent cash ($B)','2027','2028','2030'],[
 ['Recurring','(12.24)','(2.42)','19.45'],['Finite net credits','2.12','6.17','3.61'],['With credits','(10.12)','3.75','23.06']
],163,[126,63,63,63],x=647,row_h=33,size=10.2,highlights=(0,))
para('<b>Net investment includes working capital.</b> $30.00B capex - $21.81B depreciation + $3.16B working capital = $11.35B in 2030. Total 2027-30 physical capex is $124.5B.',48,470,565,12.8,17)
bullet('<b>92.9% of operating value is after 2030.</b> The model then assumes $0.80 of incremental sales per dollar of net investment, with packaging modeled separately.',657,322,295,12.8)
bullet('<b>Follow group cash, not just product margins.</b> More sales must cover factory costs and replacement investment. The capital stress on page 7 tests that dependence.',657,435,295,12.8)
section('Financing the combined CPU delay and factory stress',38,554,924)
bullet('<b>$2.65B peak draw; $126M interest at 8%.</b> The model draws in Q2-Q3 2028 and repays in Q4. Debt preserves the $20B buffer; it adds no net asset value.',48,594,445,12.5)
bullet('<b>$15B committed capacity is disclosed.</b> $5B matures in August 2029 and $10B in August 2031. Future access is assumed; pricing, fees and covenant terms remain unverified.',515,594,437,12.5)
foot('Sources: '+link('Intel Q3 facilities, cash and claims',URL['q3'])+'; analyst operating and funding model. Recurring means parent operating cash after tax, net investment, leases and minorities, excluding finite credits and financing. R&D remains expensed. Combined stress retains $124.5B near-term capex; its 2030 recurring cash is $15.33B. Funding assumes full-quarter interest on new draws, no immediate tax benefit or incremental fees. $20B is an assumed quarter-end buffer, not a covenant; daily liquidity is not established.')
c.showPage()

# 10. Show the original reanalysis as an inspectable, labeled exhibit.
page(10,'Workload Cost Comparison','AMD-powered AWS servers cost less in these five builds','')
section('Calculated cost per successful build (US cents)',38,123,495)
section('Same cloud size does not mean equal physical cores',557,123,405)
legend([('AMD-powered AWS server',RED),('Intel-powered AWS server',ACCENT)],49,161,247)
by={}
for r in BENCH['records']:
    if r['instance'] in ('m8a.2xlarge','m8i.2xlarge'):by.setdefault(r['date'],{})[r['instance']]=r
cx=lambda v:139+(v-1.25)/.40*350
for v in [1.3,1.4,1.5,1.6]:line(cx(v),198,cx(v),421,RULE,.5);text(cx(v),433,f'{v:.1f}',10,align='center')
for i,(date,pair) in enumerate(sorted(by.items())):
    y=218+i*45;av=pair['m8a.2xlarge']['normalized_on_demand_EC2_EBS_USD']*100;iv=pair['m8i.2xlarge']['normalized_on_demand_EC2_EBS_USD']*100
    text(48,y-5,__import__('datetime').date.fromisoformat(date).strftime('%b %d'),10.5)
    line(cx(av),y,cx(iv),y,GRAY,1.4);dot(cx(av),y,4,RED);dot(cx(iv),y,4,ACCENT)
    text(cx(av),y-18,f'{av:.3f}',9.8,'SansB',RED,align='center');text(cx(iv),y-18,f'{iv:.3f}',9.8,'SansB',ACCENT,align='center')
text(317,457,'Lower normalized cost is better | paired dates in 2026',10,color=MUTED,align='center')
table(['Purchased shape','Intel','AMD'],[['vCPU / memory','8 / 32 GiB','8 / 32 GiB'],['Physical cores','4 + SMT','8'],['Mean cost / success','1.555 cents','1.382 cents'],['Median job duration','114 sec','87 sec']],162,[193,106,106],x=557,row_h=32,size=10.7,highlights=(1,2))
bullet('<b>AMD costs 11.2% less on average.</b> Changing the shutdown window reduces the advantage to 7.8%, with the same direction.',567,339,385,14)
bullet('<b>I retain Intel shipment-share losses.</b> This result is consistent with competitive pressure; it cannot estimate the size of those losses or Intel\'s supplier margins.',567,433,385,14)
section('Five paired public Rust builds | Original analysis of public records',38,543,924)
bullet('<b>Same vCPU and memory, different cores.</b> Intel m8i.2xlarge has four physical cores plus SMT; AMD m8a.2xlarge has eight. All ten primary logs passed 45 tests.',48,584,441,13.5)
bullet('<b>Normalized cost, not an invoice.</b> Mainly spot executions were repriced at common on-demand EC2 + EBS rates. This is one workload, not enterprise-wide total cost.',515,584,437,13.5)
foot('Sources: '+link('Runs-On benchmark methodology',URL['runson'])+'; '+link('frozen raw logs and harness (CC BY 4.0)',URL['runson_raw'])+'; '+link('AWS on-demand rate file',URL['aws_prices'])+'. Reanalysis of five paired public records, not a new experiment. Cost includes estimated billed runtime and EBS at common on-demand rates; it is not an equal-physical-core comparison or an actual invoice.')

c.save()

if '--screen-only' in __import__('sys').argv:
    reader=PdfReader(screen)
    assert len(reader.pages)==10
    extracted='\n\n'.join(p.extract_text() for p in reader.pages)
    for required in ['82.47','56.14','73.56','48.56','92.9%','56.28','40.45','55 days','31.74','90.01']:
        assert required in extracted,required
    (TMP/'valuation_resolution_review/main_text.txt').write_text(extracted)
    (TMP/'valuation_resolution_review/layout_boxes.json').write_text(json.dumps(logs,indent=2)+'\n')
    receipt={'built_utc':datetime.now(timezone.utc).isoformat(),'path':str(screen),'pages':len(reader.pages),'links':sum(len(p.get('/Annots',[])) for p in reader.pages),'sha256':hashlib.sha256(screen.read_bytes()).hexdigest(),'source_model_sha256':hashlib.sha256((THESIS/'root/active_case.json').read_bytes()).hexdigest(),'visual_qa':'pending','scope':'Nov6 price refresh, conditional entry decision, independent exit cash-yield check and committed-revolver funding stress; operating forecast unchanged'}
    (TMP/'valuation_resolution_review/build_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
    raise SystemExit(0)

INK, MUTED, RULE, ACCENT, PALE, WHITE, RED = [HexColor(h) for h in ['#16283E', '#586575', '#CFD7E0', '#146F67', '#EFF3F7', '#FFFFFF', '#A9483C']]

styles = {
    'title': ParagraphStyle('title', fontName='SansB', fontSize=19, leading=23, textColor=INK, spaceAfter=10),
    'sub': ParagraphStyle('sub', fontName='Sans', fontSize=10, leading=14, textColor=MUTED, spaceAfter=12),
    'body': ParagraphStyle('body', fontName='Sans', fontSize=10.5, leading=14.5, textColor=INK, spaceAfter=8),
    'q': ParagraphStyle('q', fontName='SansB', fontSize=11, leading=15, textColor=INK, spaceBefore=8, spaceAfter=5),
    'small': ParagraphStyle('small', fontName='Sans', fontSize=9, leading=12, textColor=MUTED, spaceAfter=7),
}


def p(value: str, style: str = 'body') -> Paragraph:
    value = value.replace('D&A', 'D&amp;A').replace('Q&A', 'Q&amp;A').replace('S&P', 'S&amp;P').replace('R&D', 'R&amp;D')
    value = value.replace('B oth', 'Both').replace('B usiness', 'Business').replace(',$', ', $')
    return Paragraph(value, styles[style])


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
    [p('The recommendation and the 30-second answer', 'title'), p('Conditional LONG at $40 or below | Current $56.28 | December 2030 target $82.47', 'sub'),
     p('Intel can increase CPU sales while losing share. I forecast $90B of company sales in 2028, about 7.5% above the published S&P estimate, but the current price does not compensate enough for execution risk. I would enter at $40 or below while the operating thesis remains intact. The $82.47 core 2030 target yields 9.6% annually at $56.28; the higher-rate case yields 6.7%.'),
     *qa('Why is the LONG conditional?', 'The operating thesis survives, but the verified November 6 close rose to $56.28 from $52.25. The claims audit found no justified value uplift, and the cash-yield check did not establish cheapness. I require a better entry instead of increasing the target. The forecast was previously the favorable case; all scenario values were known before its selection.'),
     *qa('What are the three claims?', 'Intel can grow through share loss. New Xeon adoption can sustain richer mix beyond the immediate shortage. Factory recovery can turn sales into cash without a new high-volume external wafer win. That last statement still includes existing external business and $7B of gross packaging sales by 2030.'),
     *qa('What is the actual disagreement with expectations?', '$72.42B of company sales in 2027 versus $69.267B, and $90.01B in 2028 versus $83.719B in the public S&P Global series. Those are +4.6% and +7.5%. No matched CPU-unit, CPU-share or cash-flow consensus has been established. The pitch does not claim the market ignores capex or PC weakness.'),
     *qa('How confident should I sound?', 'Confident about the calculations and the reasoning chain; measured about forecasts. This is a conditional investment judgment: no new position at $56.28, and no prediction that the stock reaches $40. It is not a proven bargain or a quantified chance of winning. A correct future forecast is not required to defend a reasonable thesis, but its assumptions must be stated.'),
     p(link('S&P forecast series', URL['sp_forecast']) + ' | ' + link('Public bear case already discussing the risks', URL['ifast']), 'small')],
    [p('Market growth, share and customer value', 'title'), p('Keep CPU units, CPU dollars, full servers and GPUs separate', 'sub'),
     *qa('How does Intel grow while losing eight share points?', 'TrendForce estimates Intel shipment share at 50% in 2026 and 42% in 2027, with industry shipment growth above 40%. At an illustrative 40%, Intel shipments rise 1.40 x 42/50 -1 =17.6%. Rounded source estimates are not exact bounds. This is a forecast consistency test, not an observed shipment series.'),
     *qa('How much ASP growth does our revenue need?', 'The long uses an estimated 2026 CPU base of $22.144B and 2027 CPU sales of $31.739B. With 17.6% unit growth, required annual ASP growth is 21.88%. The earlier lower case uses its own $21.858B base and needs 18.29%. Mixing the long revenue with the lower base would overstate its required ASP. ASP includes mix. The quarterly model needs 4.1% weighted ASP growth above estimated Q4; the annual bridge implies Q4 ASP already 17.1% above the 2026 average. That exit premium is conditional, not observed.'),
     *qa('Why not just multiply Intel share by the $220B TAM?', 'AMD projects a roughly $220B server-CPU market in 2030. Intel discusses over $200B in about 2031. B oth are vendor forecasts; the treatment of captive/custom Arm chip value is not fully specified. A $150B scenario requires 40.0% revenue share for our $60.07B forecast; a $120B pool requires 50.1%. Neither proves delivery, and shipment share is not revenue share.'),
     *qa('What independently supports CPU demand?', 'AMD\'s November 3 Q3 prepared remarks now forecast server revenue doubling in 2027, raised from more than 70% growth. This supports demand and stronger competing capture. The 97% Q3 Data Center growth includes GPUs and is not a CPU estimate. TrendForce supplies a separate shipment forecast; distinct sources can still share assumptions.'),
     *qa('Do better processors automatically mean more Intel revenue?', 'No. More work per core and IPU offload can reduce required CPU content. Google multigeneration collaboration and current cloud deployments support adoption, while AWS testimonials show value in specific workloads. They do not reveal Intel net prices or supplier margins.'),
     p(link('TrendForce and its chart', URL['trendforce']) + ' | ' + link('AMD Q3 prepared remarks, pp.3-5', URL['amd_cpu']) + ' | ' + link('Google collaboration', URL['google_lta']) + ' | ' + link('AWS X8i', URL['aws']), 'small')],
    [p('Profit retention and funded cash', 'title'), p('The accounting bridge is necessary; it does not make the forecasts facts', 'sub'),
     *qa('What actually turns $60.07B of CPU sales into cash?', 'In 2030, CPU product profit is about $26.52B. Other DCAI adds $2.90B, client profit $10.30B, Foundry $2.50B and net packaging $1.18B, less $4.45B of Other/corporate cost. Group EBIT is $38.94B. Deduct $5.84B tax,$11.35B net investment and $2.30B lease/minority cash; add $3.61B net credits to reach $23.06B parent cash before financing.'),
     *qa('Does the CPU margin already include all factory economics?', 'No. Product profit includes internal manufacturing charges. Add Foundry profit and eliminate internal revenue to evaluate the group. The near-term 50% revenue-to-EBIT response is an analyst group convention, informed by management incremental gross-profit commentary, not a measured CPU elasticity. Do not add a second factory absorption penalty for the same revenue miss.'),
     *qa('How much depends on factories and packaging?', 'Foundry improves from a $4B loss in 2027 to $2.5B profit in 2030. Together with added packaging, that supplies 31.5% of group EBIT improvement. The $7B packaging program assumes two $3B families and $1B smaller work; neither public orders nor an interview establish those fee amounts. Embedded $2B sales/$0.5B profit is removed from the incremental addition.'),
     *qa('What does the same capex budget imply?', 'B oth operating cases spend $124.5B of physical capex in 2027-30. The stronger case needs more saleable output from that budget, so manufacturing yield and utilization are material assumptions. The model does not turn missed revenue into an immediate capex refund. After 2030, host growth investment uses $0.80 of incremental sales per $1 of net investment.'),
     *qa('What about credits, grants, SBC and minority claims?', '2027-30 cash after financing totals $27.20B and includes $17.92B of finite net capital credits. Mechanically excluding those credits leaves $9.28B; it is not a fresh tax-policy scenario. Mobileye grant receivables sit inside working capital once. Economic SBC stays in costs; minority cash is an explicit allowance, not reported NCI earnings treated as distributions.'),
     *qa('Does the quarterly cash test leave enough room?', 'Base quarter-end cash bottoms at $31.19B in Q2 2028. Front-loading spending and delaying receipts lowers the minimum to $20.36B in Q3 2028, only $0.36B above the chosen $20B buffer. Adding the one-quarter CPU delay takes the low to $18.54B. An illustrative 8% revolver draws up to $1.50B, preserves $20B quarter-end cash and repays in Q4 2028 at $64M interest cost. Access is assumed; incremental fees are not modeled.'),
     p(link('Intel Q3 financial and claim disclosures', URL['q3']) + ' | ' + link('MediaTek packaging engineering discussion, pp.7-8', URL['mediatek']) + ' | ' + link('Mobileye grant timing', URL['mobileye']), 'small')],
    [p('Valuation and the strongest objections', 'title'), p('Target dates, operating cases and risk methods must stay visible', 'sub'),
     *qa('Why choose a 10.625% operating rate?', 'It equals 4.94% Treasury +1.5 asset beta x 3.79% trailing-cash implied ERP. This pre-existing method avoids imposing the sustainable-payout model\'s assumed future payout uplift. It is a method preference, not proof Intel has lower risk. The alternative 11.555% calibration is equally visible: the same operations produce $48.56 planning value and $73.56 target.'),
     *qa('Is the $82.47 target a large margin of safety?', 'No. The target is for December 2030. December 2026 planning value is $56.14, slightly below the November 6 close of $56.28, and the dates differ by 55 days. The higher-rate planning value is $48.56. Future retained cash and shorter discounting help explain why the future target is much higher.'),
     *qa('Which forecast changes hurt most?', 'Keeping other long inputs, the lower 2028-30 delivery path gives $49.91 planning/$73.20 target. Normalizing post 2030 CPU growth to 4.04% gives $50.69/$74.31. A YTD CPU-margin anchor still gives $53.61/$78.69. Growth and delivery matter more than the difference between the two margin anchors.'),
     *qa('How much is really long-run value?', '92.9% of December 2026 operating value comes after 2030, and 49.8% comes after 2040. CPU revenue grows 23.7% annually in 2027-30 and 6.04% in 2030-40. At 3% terminal growth, the rule implies 23.1% return on modeled net investment. R&D remains expensed; this is not a fully capitalized economic return on capital. Future growth and expense adequacy remain assumptions.'),
     *qa('Does packaging have to work perfectly?', 'No. Removing one assumed $3B program while retaining near-term capex gives a $79.66 target if cash costs adjust proportionally, or $74.80 if they remain committed. Corresponding planning values are $54.25 and $50.97. That demonstrates limited cushion, not immunity to execution risk.'),
     *qa('Why not short Intel instead?', 'The lower case gives a $53.43 future target at 11.555%, about 1.2% annual price decline from $56.28. That small gross decline does not establish an attractive short after costs. A short also bears borrow cost and uncapped price risk. The adverse $38.13 case is a downside scenario, not its probability-weighted expectation.'),
     p(link('NYU implied ERP data', URL['erp_monthly']), 'small')],
    [p('Milestones and hostile questions', 'title'), p('Use the answer structure: observation, interpretation, forecast consequence', 'sub'),
     *qa('What happens if the next earnings report misses?', 'Reconstruct Q4 CPU sales from DCAI less Other and compare with the $6.81B thesis estimate. H1:2027 CPU sales are about $14.11B. A miss resets the annual starting point; do not assume H2 recovers it automatically. If product profit rises but group profit does not, revisit manufacturing costs and transfer allocations.'),
     *qa('What are the later cash tests?', 'The 2028 thesis needs $90.01B company sales,$24.59B group EBIT and $3.75B parent unlevered cash before financing. In 2030 it needs $60.07B CPU sales and $2.50B Foundry profit. These are analyst monitoring thresholds, not company guidance or announced earnings dates. More capital or slower delivery should reduce the target through the same model.'),
     *qa('What original work can I honestly claim?', 'Original reanalysis of five paired public Rust build records, not an experiment run by us. All ten primary logs passed 45 tests. At normalized on-demand EC2+EBS rates, AMD cloud shapes were 11.2% cheaper on average; an alternative shutdown window gives 7.8%. Intel used four physical cores with SMT and AMD eight. This is a purchasable-shape comparison, not an equal-core architecture test, actual invoice or production-wide TCO result.'),
     *qa('Did an original interview validate the thesis?', 'No completed interview is claimed. Public customer reports and reproducible reanalysis are the evidence available. Do not call an unanswered email or a quoted analyst question a completed interview.'),
     *qa('What remains before submission?', 'Include a current resume with the ten-page PDF. Thomas Ou, Class of 2028 is already included. The official page directs email submission and does not require an interview, three supplements or special approval for an entry-price condition. The conditional LONG must still be persuasive on its merits. The deadline is November 9, 2026; no exact hour or timezone is published. Nothing has been submitted.'),
     p(link('Frozen public benchmark archive', URL['runson_raw']) + ' | ' + link('M37 rules', URL['rules']), 'small')],
]
notes_pages.append([
    p('Entry discipline and financing the stress','title'),
    p('November 6, 2026 | Reference $56.28 | Conditional LONG at $40 or below','sub'),
    *qa('Why $40, and what does that number establish?',
        'The joint case combines Foundry breakeven, 15% return on modeled net investment from 2041, an 11.555% operating rate and the revolver response. Its 2030 target is $64.74. I require 15% annually in the higher-rate core and 12% in this joint stress. Entry ceilings are $41.18 and $40.45; I round down to $40. These are judgmental hurdles, not M37 requirements or a floor. Setting the terminal return assumption equal to the discount rate lowers the 12% entry ceiling to $39.01; it does not establish that all economic rents vanish.'),
    doc_table(['Case','2030 target','Return at $56.28','Return at $40'],[
        ['Core operating case','$82.47',f'{price_return(82.47015162680005):.1%}',f'{price_return(82.47015162680005,40):.1%}'],
        ['Same operations; 11.555% rate','$73.56',f'{price_return(73.56082736404235):.1%}',f'{price_return(73.56082736404235,40):.1%}'],
        ['Joint factory / investment / financing stress','$64.74',f'{price_return(funded_joint):.1%}',f'{price_return(funded_joint,40):.1%}'],
        ['Separate adverse operating bundle','$38.13',f'{price_return(38.13):.1%}',f'{price_return(38.13,40):.1%}'],
    ],[228,84,102,102]),Spacer(1,8),
    *qa('Does a second valuation method show Intel is cheap?',
        'No. The model turns $38.94B of 2030 EBIT into $19.45B of parent operating cash after tax, investment, leases and minorities. Finite net credits add $3.61B separately. Core DCF implies about 20 times forward 2031 cash, or a 5.00% yield. Earning 12% from $56.28 needs a $90.08 exit and roughly 22 times that same cash. These are diagnostics, not observed peer evidence.'),
    *qa('Can Intel fund the modeled cash-buffer shortfall?',
        'Intel discloses $15B of committed revolvers, including $5B maturing in August 2029. At an assumed 8%, CPU delay plus timing alone draws $1.50B and costs $64M. Adding the factory stress raises borrowing to $2.65B and interest to $126M, repaid in Q4 2028. Amended pricing, fees and covenants were not located in reviewed filings. Access is assumed and fees unmodeled. Capacity and maturity fit do not establish legal availability. Debt creates no planning-value uplift.'),
    *qa('Was value missing from assets or lease treatment?',
        'No justified positive correction was established. Equity holdings, SLP receivables, cash income, minorities, Ireland and escrow were already addressed. A $0.9B tax-receivable mapping residual cannot be added without excluding overlap. Lease cash is a capacity-funding assumption, not proven duplicate rent; it is not an asset-level lease schedule.'),
    *qa('What would change the entry decision?',
        'Price alone is insufficient. Reassess $6.81B Q4 CPU sales, $14.11B H1 2027 sales, saleable output and group cash conversion. A 5% H1 miss raises required H2/H1 growth to 36.8%; do not presume catch-up. Recalculate the entry after earnings or material news and update the horizon for a later entry. No price decline or order execution is forecast.'),
    p(link('November 6 regular-session quote',URL['fresh_quote'])+' | '+link('Intel Q3 facilities and claims',URL['q3'])+' | '+link('M37 rules',URL['rules']),'small'),
])

notes_pages.append([
    p('What would justify buying at $56.28?', 'title'),
    p('Reverse requirements; no forecast increase or new recommendation', 'sub'),
    p('A 12% annual price return to December 2030 requires a $90.08 exit. The table isolates an additional stream of parent operating cash, starting in 2031 and growing 3% forever. Existing cash flows, finite credits, financing and net assets are unchanged. The cash is after tax, investment, leases and minorities. This is one equivalent way to close the gap, not a unique market-implied forecast.'),
    doc_table(['Requirement ($B unless stated)','10.625% rate','11.555% rate'],[
        ['Additional normalized 2031 cash','+3.20','+7.79'],
        ['Equivalent total normalized 2031 cash','23.92','28.51'],
        ['Increase over the existing $20.73B','15.4%','37.6%'],
    ],[308,104,104]), Spacer(1,8),
    *qa('Could better CPU margins generate that value?',
        'As a separate diagnostic, phase a CPU-margin uplift through 2027-30 and retain it afterward. The required 2030 margin rises from 44.1% to 48.5% at the core rate, or 54.6% at the higher rate. This generous test assumes no additional investment or other cost. Most added value comes after 2030. A temporary price spike does not satisfy it, and these margins are not adopted forecasts.'),
    *qa('How much depends on the factory profit paths?',
        'Combine Foundry breakeven with zero positive incremental packaging profit, retaining all capital, working capital and the packaging startup loss. The targets fall to $71.84 / $63.97 at the two rates, or 6.1% / 3.1% annually. This still requires factories to improve from present losses and retains the CPU growth assumptions. It is not protected downside.'),
    p('Earlier exit-yield check, retained for comparison: use $20.73B of forward 2031 normalized cash, finite credits separately, and the core net-asset bridge once.', 'small'),
    doc_table(['Assumed cash yield','4%','5%','6%','7%'],[
        ['2030 target','$101.29','$82.48','$69.95','$60.99'],
        ['Annual return','15.2%','9.6%','5.4%','2.0%'],
    ],[164,88,88,88,88]), Spacer(1,7),
    p('Cash yields are sensitivity inputs, not observed comparable-company valuations. The 12% hurdle is an investor choice, not an M37 rule. Re-labeling growth investment does not create cash: the model expenses R&D and has not capitalized a research asset. '+link('Growth and reinvestment definitions',URL['growth_method']),'small'),
])

notes_pages.append([
    p('CPU mix and packaging: what the evidence supports', 'title'),
    p('Separate package price, useful work, supplier margin and customer commitment', 'sub'),
    doc_table(['Current Intel catalog','Xeon 8592+','Xeon 6980P'],[
        ['Nominal physical cores','64','128'],
        ['Recommended customer price','$12,992','$13,955'],
        ['Price per nominal core','$203.00','$109.02'],
    ],[264,126,126]), Spacer(1,8),
    *qa('Does higher package ASP require higher prices for the same compute?',
        'No. This selected pair lists 7.4% higher package price but 46.3% lower price per nominal core. Different cores, memory and power make this an illustration, not a performance or TCO result. List prices are not Intel realized prices, and two SKUs do not establish the sales mix. The 21.9% annual ASP forecast still needs delivered mix and retained profit.'),
    *qa('Does the AMD-cheaper build result invalidate the long?',
        'It challenges a broad Intel cost-leadership claim. The thesis already permits shipment-share loss and does not require Intel to win every workload. The five builds cannot estimate industry share or Intel margin. Oracle also plans Intel X14 and AMD E7 while offering NVIDIA Vera CPUs; customer relationships do not establish exclusive demand.'),
    *qa('Are packaging margins grounded in comparable economics?',
        'ASE reported 20.0% operating margin in assembly/test/materials; Amkor reported 11.3%. Materials were about 27% and 50.7% of sales, respectively. Dividing operating profit by sales less materials gives 27.4% and 22.9%, but this is only a denominator diagnostic. Testing, R&D, depreciation and utilization differ. Neither company proves Intel can earn 25% on $7B of fees.'),
    *qa('What did the new margin controls establish?',
        'Keeping output and capital fixed, a 20% package margin from 2030 gives an $81.27 target; 30% gives $83.03, versus the existing $82.47. Both embedded and incremental package profit change once. Even 30% yields only 6.8% annually at the higher discount rate. Better packaging margins alone do not close the gap.'),
    *qa('What commercial evidence would carry more weight?',
        'Accepted package volumes, fee terms, material ownership and quantified customer funding. Amkor discloses $1.9B of advances expected over the next 12 months and an October agreement for $1.3B expected in 2027. These are different reporting periods, not profit or a combined annual forecast. Intel has not disclosed equivalent packaging-program economics in the reviewed sources.'),
    p(link('Intel 8592+',URL['xeon8592'])+' | '+link('Intel 6980P',URL['xeon6980'])+' | '+link('Oracle compute choices',URL['oracle_choices'])+' | '+link('ASE Q3',URL['ase'])+' | '+link('Amkor Q3',URL['amkor']),'small'),
])

notes_pages.append([
    p('Defending the mix forecast', 'title'),
    p('Observed premium mix supports retention; the estimated Q4 level still has to be earned', 'sub'),
    p('The case is that Intel retains a richer package mix while expanding supply. Holding estimated Q4 ASP flat through 2027 preserves a meaningful sales advantage. The weaker 10% annual ASP case represents a lower starting point or mix normalization. Both controls retain the modeled unit path.'),
    doc_table(['Company revenue ($B)','2027','2028'],[
        ['Selected forecast','72.42','90.01'],
        ['Estimated Q4 ASP held flat in 2027','71.17','88.32'],
        ['10% annual ASP counterexample','69.33','85.84'],
        ['Published aggregate consensus','69.27','83.72'],
    ],[308,104,104]), Spacer(1,7),
    p('Each control carries its lower CPU base into unchanged 2028 growth: +25% units and +8% ASP, with no catch-up. Other businesses stay fixed. Flat estimated Q4 ASP leaves sales 2.75% / 5.50% above consensus; the 10% annual ASP case leaves 0.09% / 2.53%. These are conditional controls, not independent forecasts.','small'),
    *qa('Judge: What evidence makes retention plausible?',
        'Q3 server ASP rose 54% and units 10% year over year, with premium mix the main ASP driver. Granite Rapids is now Intel\'s largest server family. Intel also reported signed long-term DCAI agreements, including Google. Those observations support continued adoption as supply grows. They do not reveal contractual volumes, net prices or a floor under the mix.'),
    *qa('Judge: Why does a 10% ASP case undermine so much upside?',
        'The annual comparison hides the starting level. The model implies Q4 ASP 17.1% above the 2026 average. Holding that estimate fixed, 10% annual growth means average 2027 ASP falls 6.0% from Q4; the core needs a 4.1% increase. Flat Q4 ASP produces $30.49B CPU sales versus $31.74B core. A weaker Q4 anchor or later mix decline remains a valid objection.'),
    *qa('Judge: Is 2028 another unsupported acceleration?',
        'The core annualizes forecast Q4 2027 CPU sales to $37.46B, then needs $5.39B more to reach $42.85B. Average units and ASP must exceed that exit by 10.1% and 3.9%. This explains the timing burden; it does not prove the exit or added supply. AMD\'s doubling outlook supports demand and competing capture simultaneously.'),
    *qa('Judge: What would make you abandon the faster path?',
        'Q4 CPU sales below the $6.81B starting estimate, weaker reported mix, or H1 sales below $14.11B would force a rebase. A revenue beat alone cannot verify both price and volume. More product profit must also survive factory costs and investment. I would not restore the forecast with automatic catch-up.'),
    p(link('Intel Q3 filing',URL['q3'])+' | '+link('Signed DCAI agreements: Q1 remarks, p.4',URL['q1remarks'])+' | '+link('Q3 product and supply commentary',URL['q3remarks'])+' | '+link('AMD outlook',URL['amd_cpu']),'small'),
])

notes_pages.append([
    p('Defending the entry and cash conversion', 'title'),
    p('Keep the return requirements fixed; update the business forecast when evidence changes', 'sub'),
    doc_table(['Scenario','2030 target','Annual return at $40'],[
        ['Selected funded factory / terminal / rate stress','$64.74','12.3%'],
        ['Add the existing CPU delay; fund the gap','$59.50','10.0%'],
        ['Also increase 2031-40 investment needs','$56.08','8.5%'],
        ['Previously disclosed lower case; higher rate','$53.43','7.2%'],
        ['Previously disclosed adverse operating bundle','$38.13','-1.1%'],
    ],[300,92,124]), Spacer(1,7),
    p('First three cases include illustrative 8% revolver costs where required; access is assumed and fees unmodeled. Capital control changes 2031-40 sales/net-investment from 0.80 to 0.60 on the delayed path, with separate packaging investment unchanged. All retain $124.5B of near-term capex. Returns use November 6, 2026 to December 31, 2030; cases are unweighted.','small'),
    *qa('Judge: Why keep $40 if joint setbacks miss your hurdle?',
        'It meets my chosen 15% hurdle in the higher-rate core and 12% in the selected factory/terminal stress. It is a price for a particular operating view, not insurance against every failure. If slower CPU delivery becomes my preferred forecast, I must recalculate entry. The joint stress with CPU delay has a funded 12% ceiling of $37.17; that diagnostic is not a new recommendation.'),
    *qa('Judge: Does borrowing solve the combined downside?',
        'It solves the modeled timing gap only. The combined CPU/factory case draws $2.65B, incurs $126M of interest and repays in Q4 2028. Its target remains $59.50. Added capital needs lower it to $56.08. Debt proceeds and the liability offset; legal access, fees and daily liquidity are not established by the quarterly model.'),
    *qa('Judge: What demonstrates that earnings reach shareholders?',
        'The core converts $38.94B EBIT into $19.45B of 2030 parent operating cash after tax, net investment, leases and minorities; finite net credits add $3.61B separately. The combined CPU/factory case has $15.33B before credits. Core cash without credits is negative in 2027 and 2028. Reported product-profit improvement supports the mechanism; these future cash levels and durable capital efficiency remain forecasts.'),
    *qa('Judge: What is the rule after new earnings?',
        'First rebuild CPU revenue, mix and group cash without presumed catch-up. Then rerun both risk rates and the same stress definitions, using the remaining horizon. The updated entry ceiling is the lower of the higher-rate target discounted at 15% and the selected stress target discounted at 12%. Keep those hurdles fixed. Reaching $40 after a fundamental miss does not automatically qualify.'),
    p('The present action remains no new position at $56.28. This is a defensible conditional decision, not an established current-price mispricing or a quantified chance of winning. The forecast and return requirements were selected with prior scenario results known.','small'),
])

build_letter(OUT / 'm37_intel_defense_notes.pdf', notes_pages, 'DEFENSE NOTES')

if '--pitch-and-notes' in __import__('sys').argv:
    files=[]
    for name,pages in [('m37_intel_initial_screen.pdf',10),('m37_intel_defense_notes.pdf',len(notes_pages))]:
        path=OUT/name;reader=PdfReader(path);assert len(reader.pages)==pages
        files.append({'path':str(path),'pages':pages,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'links':sum(len(p.get('/Annots',[])) for p in reader.pages)})
    (TMP/'valuation_resolution_review/two_pdf_build.json').write_text(json.dumps({'built_utc':datetime.now(timezone.utc).isoformat(),'files':files,'visual_qa':'pending'},indent=2)+'\n')
    (TMP/'valuation_resolution_review/layout_boxes.json').write_text(json.dumps(logs,indent=2)+'\n')
    print(json.dumps(files,indent=2));raise SystemExit(0)

comparison_pages = [
    [p('The pitch now includes an entry decision', 'title'), p('Comparison with public winning pitches | November 6, 2026', 'sub'),
     p('The screen remains a conditional LONG at $40 or below. The November 6 price of $56.28 does not meet that entry rule. New research quantifies the recurring cash needed to justify buying now and compares packaging margins with reported industry economics. The operating forecast is unchanged: $82.47 core target, or $73.56 at the higher discount rate.'),
     doc_table(['Area', 'Useful pattern in examples', 'Revised Intel pitch'], [
         ['Business mechanism', 'Connect a specific driver to revenue and cash.', 'Market units x Intel unit share x ASP; then consolidated profit and investment.'],
         ['Disagreement', 'Use a comparable dated expectation.', '2028 sales $90.01B versus S&P $83.72B, a 7.5% difference.'],
         ['Recommendation', 'Own a forecast and show what changes it.', 'Conditional LONG at $40 or below; $82.47 core 2030 target; no new position at $56.28.'],
         ['Evidence', 'Research constrains the forecast.', 'Unit/mix bridge; customer alternatives; packaging margin controls; contrary workload results retained.'],
         ['Cash', 'Make growth investment visible.', '$124.5B near-term physical capex; tax, credits, minority cash and SBC counted once.'],
         ['Failure tests', 'Tie risks to observable milestones.', 'Q4/H1 CPU, 2028 group profit/cash, 2030 factory recovery.'],
     ], [90, 185, 241]), Spacer(1, 10),
     p('The comparison is a selected sample across different competitions, horizons and rules. It cannot estimate the probability of winning M37. The conditional entry is a completed investment judgment under chosen return requirements. Its competition appeal still depends on the reasoning; no published special-approval requirement was found.', 'small'),
     p(link('Official M37 rules', URL['rules']) + ' | ' + link('UNC award archive', URL['unc']) + ' | ' + link('CFA past champions', URL['cfa']), 'small')],
    [p('What the examples teach', 'title'), p('Borrow the reasoning, not their conclusions or numerical targets', 'sub'),
     *qa('WMS | UNC 2024 first place', 'The deck connects material conversion, mix and market access to a forecast above consensus. Intel now has a similarly explicit sales disagreement, but its public market forecast is not proprietary evidence. The reader can check each step. ' + link('Official deck', URL['wms'])),
     *qa('JBI | Columbia 2023 first place', 'Its renovation-versus-construction distinction explains why a business might be misclassified. Intel\'s analogous distinction is that lost shipment share need not mean shrinking sales. This is an analytical interpretation of public data, not a claim every investor misunderstands it. ' + link('Official deck', URL['jbi'])),
     *qa('Cargojet | Waterloo 2024 global winner', 'Fleet utilization, routes and capital spending explain cash generation. Intel\'s counterpart is saleable factory output at a funded capital budget. The revised cash page makes the dependence visible rather than treating revenue as free cash. ' + link('Official presentation', URL['cargo'])),
     *qa('What remains weaker?', 'The pitch does not establish a compelling entry at $56.28 under my chosen return requirements. A 12% annual return requires an equivalent $3.20B additional recurring cash stream from 2031 at the core rate, or $7.79B at the higher rate. Research has not justified adopting that increase. The 12% requirement is my judgment, not an M37 rule; 9.6% is not inherently an inadequate return.'),
     *qa('What should stay out of the main ten pages?', 'Long accounting explanations, the whole source ledger and every scenario combination. Put them in the workbook and defense notes. The main screen should remain about the three claims and the consequences if they fail.')],
    [p('What the research establishes', 'title'), p('A completed decision can still depend on uncertain forecasts', 'sub'),
     *qa('The entry decision is made', 'Conditional LONG at $40 or below; no new position at the $56.28 reference quote. Core annual appreciation is 9.6%, or 6.7% at the higher discount rate. The chosen return requirements demand more compensation for execution risk. Research has not justified raising the forecast or adding omitted asset value. This is a decision, not a pending search for a higher target.'),
     *qa('CPU growth and factory recovery remain forecasts', 'The model assumes $31.74B of 2027 CPU sales, $7B gross packaging sales and $2.50B of Foundry profit in 2030. Exact mix and customer economics are not observed. These assumptions have explicit stresses and monitoring thresholds. They are not facts that another research pass can make certain.'),
     *qa('Calculations and asset treatment have been checked', 'Cash-flow and valuation reconciliations passed. Equity holdings, receivables, cash income and minority claims were reviewed; no justified extra asset value was established. R&D stays expensed, so the terminal metric is return on modeled net investment. A negative finding closes an investigation without increasing the target.'),
     *qa('Financing has a defined evidence limit', 'Disclosed revolver capacity and maturities fit the illustrative draw. Amended pricing, fees and covenants were not located in reviewed filings. The 6%/8%/10% scenarios measure interest; future access is assumed and incremental fees are not modeled. That limits the funding claim without turning it into an endless research task.'),
     *qa('Only one required package item is outstanding', 'The current resume is not yet included. The ten-page screen has Thomas Ou, Class of 2028 and a 2030 horizon. The official page requires neither an interview nor three supplements, and no special approval rule for an entry condition was found. The defense notes and comparison are preparation materials. Nothing has been submitted.'),
     *qa('What would reopen the analysis?', 'Material earnings, customer terms, capital needs, a calculation error or a changed price and horizon. An interview reply could contribute evidence, but silence is not a blocker. A conditional long may be less compelling than a strong current-price opportunity; more sensitivity tables alone do not solve that competition weakness.')],
]
build_letter(OUT / 'm37_intel_pitch_comparison.pdf', comparison_pages, 'COMPARATIVE REVIEW')
manifest = {'built_utc': datetime.now(timezone.utc).isoformat(), 'submitted': False, 'recommendation_finalized': True, 'recommendation': 'CONDITIONAL LONG AT OR BELOW $40', 'conviction': 'conditional entry only', 'administratively_ready': False, 'model_sha256': hashlib.sha256((THESIS / 'root/active_case.json').read_bytes()).hexdigest(), 'files': [], 'visual_qa': 'pending'}
for name, expected in [('m37_intel_initial_screen.pdf', 10), ('m37_intel_defense_notes.pdf', len(notes_pages)), ('m37_intel_pitch_comparison.pdf', 3)]:
    file = OUT / name
    reader = PdfReader(file)
    assert len(reader.pages) == expected, (name, len(reader.pages))
    content = '\n\n'.join(p.extract_text() for p in reader.pages)
    (TMP / (name.replace('.pdf', '_completion_extracted.txt'))).write_text(content)
    assert '82.47' in content and '73.56' in content, name
    manifest['files'].append({'path': str(file), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'pages': expected, 'links': sum(len(p.get('/Annots', [])) for p in reader.pages)})
(TMP / 'completion_build_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(TMP / 'completion_layout_boxes.json').write_text(json.dumps(logs, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
