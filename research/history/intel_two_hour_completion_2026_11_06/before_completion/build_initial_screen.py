from pathlib import Path
import hashlib
import json
import re
from html import escape
from decimal import Decimal, ROUND_HALF_UP

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

ROOT = Path('/Users/thomasou/Documents/Codex/2026-11-02/lo')
OUT = ROOT / 'output/pdf/m37_intel_initial_screen.pdf'
RESEARCH = ROOT / 'work/three_hour/active_research'
HOUR = RESEARCH / 'intel_hour_verification_2026_11_04'
BASE = RESEARCH / 'pricing_and_competition_review_2026_11_04'
model_path = BASE / 'intel_ASP20_mature_margin35_valuation.json'
model = json.loads(model_path.read_text())
policy = json.loads((BASE / 'intel_server_ASP_mix_operating_policy.json').read_text())
rates = json.loads((HOUR / 'corrected_rate_valuation.json').read_text())
weak = json.loads((HOUR / 'weak_demand_results.json').read_text())
horizon = json.loads((RESEARCH / 'intel_short_horizon_repair_2026_11_05/root_horizon_boundaries.json').read_text())
position_dir = RESEARCH / 'intel_position_resolution_2026_11_05'
relative = json.loads((position_dir / 'relative_framework_review.json').read_text())
duration = json.loads((position_dir / 'early_normalization_root_results.json').read_text())
completion_dir = RESEARCH / 'intel_pitch_completion_2026_11_05'
operating_bridge = json.loads((completion_dir / 'operating_value_bridge.json').read_text())
repair_dir = RESEARCH / 'intel_thesis_repair_2026_11_05'
repair = json.loads((repair_dir / 'cpu_anchor_valuation.json').read_text())
entry_price = 52.25
tsmc = json.loads((HOUR / 'tsmc_multiyear_capital_benchmark.json').read_text())
central = next(s for s in rates['scenarios'] if s['name'] == 'central')
favorable = next(s for s in rates['scenarios'] if s['name'] == 'more_productive')
v = central['values']['2026']['corrected_central_flat']

FONTDIR = Path('/System/Library/Fonts/Supplemental')
for name, file in [('Body', 'Georgia.ttf'), ('BodyB', 'Georgia Bold.ttf'),
                   ('BodyI', 'Georgia Italic.ttf'), ('Sans', 'Arial.ttf'),
                   ('SansB', 'Arial Bold.ttf'), ('SansI', 'Arial Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONTDIR / file)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='BodyB', italic='BodyI', boldItalic='BodyB')
pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='SansB', italic='SansI', boldItalic='SansB')


W, H = 960, 540
L, R, CW = 40, 920, 880
INK = HexColor('#16283E')
MUTED = HexColor('#586575')
RULE = HexColor('#CFD7E0')
ACCENT = HexColor('#146F67')
BLUE = HexColor('#176A9B')
SLATE = HexColor('#73889B')
PALE = HexColor('#EFF3F7')
PAPER = WHITE = HexColor('#FFFFFF')
logs = []
c = canvas.Canvas(str(OUT), pagesize=(W,H), pageCompression=1)
c.setTitle('Intel | Server growth can outweigh the PC decline')
c.setAuthor('Thomas Ou')
c.setSubject('M37 initial screen | LONG Intel | November 6, 2026')

def text(x, top, s, font='Sans', size=11, color=INK, align='left'):
    c.setFillColor(color); c.setFont(font,size)
    fn = {'left':c.drawString,'right':c.drawRightString,'center':c.drawCentredString}[align]
    fn(x,H-top-size*.84,str(s))
    tw = pdfmetrics.stringWidth(str(s),font,size)
    xx = x if align=='left' else (x-tw if align=='right' else x-tw/2)
    if xx < 8 or xx+tw > W-8: raise ValueError(f'Text outside page {c.getPageNumber()}: {s}')

def rect(x, top, w, h, color):
    c.setFillColor(color);c.rect(x,H-top-h,w,h,stroke=0,fill=1)

def line(x1,y1,x2,y2,color=RULE,width=.65,dash=None):
    c.setStrokeColor(color);c.setLineWidth(width);c.setDash(dash or [])
    c.line(x1,H-y1,x2,H-y2);c.setDash([])

def arrow(x,top,w=16):
    line(x,top,x+w,top,ACCENT,1.5)
    line(x+w-5,top-4,x+w,top,ACCENT,1.5)
    line(x+w-5,top+4,x+w,top,ACCENT,1.5)

def para(s,x=L,top=0,width=CW,size=12,leading=17,font='Sans',color=INK):
    s = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;)', '&amp;',s)
    st=ParagraphStyle('p',fontName=font,fontSize=size,leading=leading,textColor=color,
                      allowWidows=0,allowOrphans=0,spaceBefore=0,spaceAfter=0)
    p=Paragraph(s,st);_,ph=p.wrap(width,1000);p.drawOn(c,x,H-top-ph)
    logs.append({'page':c.getPageNumber(),'x':x,'top':top,'bottom':top+ph,'width':width,'text':s})
    if top+ph>505: raise ValueError(f'Paragraph overrun {c.getPageNumber()}: {s[:70]} -> {top+ph}')
    return top+ph

def label(s,top,x=L,color=MUTED,size=9):text(x,top,s,'SansB',size,color)
def note(s,top,x=L,width=CW,size=9):return para(s,x,top,width,size,12,font='Sans',color=MUTED)
def source(s):para(s.replace('\n','<br/>'),top=484,size=8.3,leading=10,font='Sans',color=MUTED)

def link(label_text,url):
    return f'<link href="{escape(url,quote=True)}" color="#176A9B"><u>{escape(label_text)}</u></link>'

def page(n, section, heading, sub=None):
    rect(0,0,W,H,WHITE)
    label('INTEL  |  NASDAQ: INTC',19,color=INK,size=9)
    text(R,19,'THOMAS OU  |  06 NOV 2026','Sans',9,MUTED,'right')
    para(heading,top=48,font='SansB',size=25,leading=29)
    line(L,85,R,85,ACCENT,1.2)
    if sub:para(sub,top=96,size=11.3,leading=15.5,color=MUTED)
    line(L,513,R,513,ACCENT,.6)
    sections=['Business','Delivery','Durability','Cash & value','Decision','Sources']
    for i,s in enumerate(sections):
        xx=L+i*143
        if s==section:rect(xx,511,120,3,ACCENT)
        text(xx,522,s,'SansB' if s==section else 'Sans',8,INK if s==section else MUTED)
    text(R,521,f'{n:02d} / 10','Sans',8,MUTED,'right')
    c.bookmarkPage(f'p{n}');c.addOutlineEntry(heading,f'p{n}',0,False)

def banner(s,top=447,color=INK,size=12):
    rect(L,top,CW,31,color);para(s,x=L+12,top=top+7,width=CW-24,size=size,leading=16,font='SansB',color=WHITE)

def table(headers,rows,top,widths,x=L,row_h=34,size=11,emphasize=None):
    total=sum(widths);rect(x,top,total,28,INK)
    xx=x
    for j,h in enumerate(headers):
        text(xx+9 if j==0 else xx+widths[j]-9,top+9,h,'SansB',9,WHITE,'left' if j==0 else 'right');xx+=widths[j]
    yy=top+28
    for i,row in enumerate(rows):
        if i%2==0 or (emphasize and i in emphasize):rect(x,yy,total,row_h,PALE)
        xx=x
        for j,a in enumerate(row):
            text(xx+9 if j==0 else xx+widths[j]-9,yy+11,a,'SansB' if emphasize and i in emphasize else 'Sans',size,INK,'left' if j==0 else 'right');xx+=widths[j]
        line(x,yy+row_h,x+total,yy+row_h,RULE,.4);yy+=row_h
    return yy

cash_bridge=json.loads((RESEARCH/'intel_business_pitch_rebuild_2026_11_05/cumulative_cash_bridge.json').read_text())


directional_dir = RESEARCH / 'intel_directional_build_2026_11_05'
from datetime import date
years = (date(2030,12,31)-date(2026,11,5)).days/365.25
bridge2026 = next(r for r in operating_bridge['decomposition'] if r['endpoint']==2026 and r['risk']=='corrected_central_flat')
base2030 = next(r for r in operating_bridge['decomposition'] if r['endpoint']==2030 and r['risk']=='corrected_central_flat')['cases']['margin_only']
bull2030 = next(r for r in operating_bridge['decomposition'] if r['endpoint']==2030 and r['risk']=='corrected_maturing_risk')['cases']['margin_only']
v = dict(v)
v.update(bridge2026['cases']['margin_only'])
target = base2030['price_USD']
upside = target/entry_price-1
cagr = (target/entry_price)**(1/years)-1
mix = json.loads((directional_dir/'independent_policy_before_new_returns.json').read_text())

stress = json.loads((directional_dir/'joint_downside_results.json').read_text())
stress2030 = stress['values']['2030']['corrected_central_flat']['price_USD']
benchmark_dir = RESEARCH / 'intel_benchmark_rebuild_2026_11_05'
return_bridge = json.loads((benchmark_dir / 'return_value_bridge.json').read_text())
earnings_bridge = json.loads((benchmark_dir / 'evidence_to_operating_profit_bridge.json').read_text())
margin_evidence = json.loads((benchmark_dir / 'margin_evidence.json').read_text())

two_hour = RESEARCH / 'intel_two_hour_comparison_2026_11_05'
new_scenarios = json.loads((two_hour/'model_audit/extended_scenario_results.json').read_text())
duration_check = json.loads((two_hour/'model_audit/structural_review_results.json').read_text())
client_check = json.loads((two_hour/'root_comparison/client_and_other_underwriting.json').read_text())
claims_overlay_path = two_hour/'model_audit/explicit_claims_overlay_results.json'
claims_overlay = json.loads(claims_overlay_path.read_text())
edge_dir = RESEARCH / 'intel_edge_resolution_2026_11_06'
price_refresh = json.loads((edge_dir/'price/price_refresh_52_25_overlay.json').read_text())
by_case = {name: case['summary'] for name, case in claims_overlay['cases'].items()}
v.update(claims_overlay['base_APV']['2026'])
base2030 = claims_overlay['base_APV']['2030']
target = base2030['price_USD']
upside = target/entry_price-1
cagr = (target/entry_price)**(1/years)-1
assert abs(claims_overlay['additional_reserve_B']/5.51-claims_overlay['per_share_claim_deduction_USD']) < 1e-12
assert abs(v['equity_B']/5.51-v['price_USD']) < 1e-10

# 1
page(1,'Business','Intel | Server growth can outweigh the PC decline.','LONG | M37 Initial Screen | December 2030 horizon | Thomas Ou, Class of 2027')
for xx,num,cap,col in [(40,f'${entry_price:.2f}','NOVEMBER 5, 2026 CLOSE',INK),(263,f'${target:.2f}','DECEMBER 2030 BASE TARGET',ACCENT),(486,f'+{upside:.1%}','TOTAL PRICE APPRECIATION',BLUE),(709,f'{cagr:.1%}','ANNUAL PRICE APPRECIATION',BLUE)]:
    rect(xx,135,211,79,PALE);text(xx+14,148,num,'SansB',28,col);label(cap,189,x=xx+14,size=8)
note('Conditional price returns over 4.15 years. No interim dividends, trading costs or investor taxes are included.',223)
for yy,num,head,detail in [
 (250,'1','Server growth can outweigh a weak PC market.','Q3 DCAI margin reached 41.5%. My 2027 forecast adds $5.09B of DCAI profit while CCPG profit falls $1.38B, with 20% more server CPUs at a 20% higher average selling price.'),
 (334,'2','The server ramp has production plans and customer commitments.','Intel targets more than double Ireland output in 2027 and has signed multiyear DCAI agreements. If deliveries and margins follow, my owner-cash forecast reaches $21.9B in 2030 after investment.')]:
    rect(L,yy,48,65,ACCENT);text(L+24,yy+18,num,'SansB',24,WHITE,'center')
    rect(88,yy,832,65,PALE);para(head,x=104,top=yy+9,width=800,size=15,leading=18,font='SansB')
    para(detail,x=104,top=yy+32,width=800,size=11.3,leading=15)
para('The long depends on profits lasting beyond the capacity shortage.',top=416,font='SansB',size=12,leading=16)
para('Moderate conviction. My $51.07 December 2026 planning value is close to the entry. The base offers about 10% a year if it materializes; it does not show a large initial discount. A 12% return requires an entry near $48.38. Persistent customer or pricing losses matter much more than a temporary production delay.',top=438,size=10.6,leading=15)
source('Sources: price [1]; Intel [2,10,19-21]; my operating and valuation models. 2026E includes a Q4 forecast. Owner cash precedes separately reserved claim payments.\nThe planning date is 56 days after the quote. The future target includes cash after 2030; its appreciation is not evidence of immediate mispricing.')
c.showPage()

# 2
page(2,'Business','Servers can add more profit than PCs lose.','Business model and 2026E-to-2027 product-profit forecast | USD billions')
for x,w,head,body in [(40,275,'CCPG: PCs and edge products','Sells client processors and adjacent products. Memory costs and inventory cuts are weakening PC demand.'),(342,275,'DCAI: servers and related silicon','Sells CPUs, networking and purpose-built silicon. Server mix and output drive the profit recovery.'),(644,276,'Foundry: manufacturing and packaging','Supplies Intel Products and outside customers. Internal sales are eliminated in group revenue.')]:
    rect(x,140,w,85,PALE);para(head,x=x+13,top=151,width=w-26,font='SansB',size=11.7,leading=15);para(body,x=x+13,top=177,width=w-26,size=10.3,leading=13.5)
label('2026E -> 2027 PRODUCTS OPERATING PROFIT',246,color=BLUE)
profit=client_check['Products_profit_bridge_B']
steps=[('2026E',profit['2026E'],True),('DCAI',profit['DCAI_change'],False),('CCPG',profit['CCPG_change'],False),('2027',profit['2027'],True)]
yf=lambda z:384-z/26*107
for tick in [0,10,20]:line(65,yf(tick),482,yf(tick),RULE,.4);text(58,yf(tick)-5,str(tick),'Sans',8,MUTED,'right')
cur=0
for i,(cap,d,total) in enumerate(steps):
    xx=79+i*104;aa,bb=(0,d) if total else (cur,cur+d);co=INK if total else (BLUE if d>0 else SLATE)
    rect(xx,yf(max(aa,bb)),62,max(abs(yf(aa)-yf(bb)),1.2),co)
    text(xx+31,yf(max(aa,bb))-17,f'{d:.2f}' if total else f'{d:+.2f}','SansB',11,co,'center')
    text(xx+31,397,cap,'Sans',9.3,INK,'center')
    if i<3:line(xx+62,yf(bb),xx+104,yf(bb),MUTED,.5,[2,2])
    cur=bb
anchor=json.loads((RESEARCH/'intel_competition_screen_2026_11_04/product_operating_forecast_2026_11_04.json').read_text())['FY2026_estimated_anchor']
table(['Product forecast','2026E','2027'],[
 ['CCPG revenue',f"{anchor['CCPG_revenue_B']:.2f}",f"{policy['annual_rows'][0]['CCPG_revenue_B']:.2f}"],
 ['DCAI revenue',f"{anchor['DCAI_revenue_B']:.2f}",f"{policy['annual_rows'][0]['DCAI_revenue_B']:.2f}"],
 ['CCPG operating margin','26.8%','24.0%'],['DCAI operating margin','38.2%','38.8%']],248,[230,85,85],x=520,row_h=30,size=10.2)
note('2027 client units fall 12%; modest recovery returns 2030 units approximately to 2026 levels. This case does not require a PC-volume boom.',426,width=430,size=9.6)
note('Products profit excludes Foundry losses and central costs. Q3 actual group revenue / EBIT: $16.51B / $2.52B; DCAI margin: 41.5%.',426,x=520,width=400,size=9.6)
source('Sources: Intel Q3 filing and prepared remarks [2,10]; my product forecast. 2026E = nine months reported plus my Q4 estimate.\nOther DCAI includes more than custom silicon. Its standalone profitability is undisclosed; group expenses and intersegment eliminations remain separate.')
c.showPage()

# 3
page(3,'Delivery','The revenue case requires $31.5B of CPU sales in 2027.','My estimated 2026 CPU-sales base -> shipment growth -> richer mix and pricing | USD billions')
cols=[40,315,600]; widths=[275,285,320]
for xx,ww,head in zip(cols,widths,['EVIDENCE','FORECAST','REVENUE EFFECT']):
    rect(xx,141,ww,27,INK);text(xx+12,150,head,'SansB',9,WHITE)
rows=[
 ('<b>Growth can offset share loss.</b><br/>TrendForce forecasts >40% market growth and Intel share of 50% -> 42%, implying roughly 18%+ Intel unit growth. [3]',
  '<b>Intel server units +20%.</b><br/>Industry growth can absorb share loss, provided Intel delivers enough qualified packages.',
  '<b>+$4.37B from units.</b><br/>20% x my estimated $21.86B 2026 CPU-sales base, before the ASP effect.'),
 ('<b>The product mix is richer.</b><br/>Q3 ASP +54%, units +10%. Granite Rapids is the largest server family; larger products also cost more. [2,10]',
  '<b>ASP +20%, then +8/4/2%.</b><br/>Annual carryover and product mix contribute; this is not a 20% same-chip price increase.',
  '<b>+$5.25B from ASP.</b><br/>$21.86B x 1.20 x 1.20 = $31.48B. The interaction is included once.'),
 ('<b>Purpose-built silicon is growing.</b><br/>Management expects that business to triple over the next few years. Its scope differs from all Other DCAI. [10]',
  '<b>Other DCAI: $5.19B -> $17.44B.</b><br/>2026E to 2030: 3.36x growth. Its lower-margin mix remains a risk to DCAI.',
  '<b>2027 total DCAI: $39.78B.</b><br/>$31.48B CPUs + $8.30B Other. No separate new-GPU windfall is added.')]
for i,row in enumerate(rows):
    yy=168+i*84
    for xx,ww,body in zip(cols,widths,row):
        if i%2==0:rect(xx,yy,ww,84,PALE)
        para(body,x=xx+12,top=yy+10,width=ww-24,size=10.2,leading=13.5)
    line(L,yy+84,R,yy+84,RULE,.5)
rect(L,426,CW,48,PALE)
para('<b>Exit-rate hurdle:</b> 2027 is 20.6% above forecast Q4 annualized. If H1 holds that $6.53B quarterly CPU-sales pace, H2 must average $9.21B per quarter (+41%). Q4 and flat H1 are assumptions.',x=53,top=432,width=414,size=9.5,leading=12.5)
para('<b>Current forecast check:</b> my $68.33B Products forecast leaves only $0.94B within the $69.27B S&P total-sales estimate for external Foundry and net All Other. This exposes optimism, not a matched sales beat. [12]',x=493,top=432,width=414,size=9.5,leading=12.5)
source('Sources: Intel [2,10], TrendForce [3], S&P Global via Stock Analysis, updated Nov. 5 [12]; my model. The residual is conditional, not segment consensus; consolidation remains approximate.\nCPU sales use rounded allocation disclosures. My 2028-30 unit growth of 25% / 18% / 12% needs 18.2% annual market growth to avoid share recovery; no matched forecast establishes it.')
c.showPage()

# 4
page(4,'Delivery','Capacity must become customer-accepted output.','Investment, production load and delivery dates are different parts of the shipment forecast.')
for i,(head,body) in enumerate([
 ('Wafer output','Installed tools, cycle time and good-die yield determine available silicon.'),
 ('Substrate & assembly','Larger, more complex packages consume more manufacturing resources.'),
 ('Qualified CPU','Testing, reliability and platform qualification determine usable supply.'),
 ('Accepted shipment','The customer must still want the product at an economic price.')]):
    xx=40+i*224;rect(xx,140,208,82,PALE);label(str(i+1),151,x=xx+12,color=ACCENT,size=12);para(head,x=xx+32,top=152,width=164,font='SansB',size=11,leading=14);para(body,x=xx+12,top=177,width=184,size=9.8,leading=13)
    if i<3:arrow(xx+211,181,10)
label('A QUANTIFIED IRELAND RAMP',245,color=BLUE)
text(40,268,'>2x','SansB',27,BLUE)
para('Ireland output in 2027: CFO target from August 26, discussing Intel 3 / Granite Rapids. October remarks report rising output and tool installation. [10,19]',x=122,top=269,width=343,size=10.3,leading=14)
para('The existing site gives the ramp a physical basis. The output definition, mix and quarterly conversion to qualified CPUs are undisclosed. Oregon Intel 3 output is separately planned for H2 2027. [18,19]',top=331,width=425,size=10.3,leading=14)
note('Fab 28: ~$0.3B Q4 sales impact is already in my guidance-based anchor. Similar early Q1 estimate; no quarterly reconciliation yet. [10,18]',382,width=425,size=9.1)
label('PACKAGING STILL GATES SHIPMENTS',245,x=520,color=BLUE)
para('<b>Intel:</b> 40% more substrate capacity, much in H2 2027. Two agreements require $5.3-6.1B, about $3.3B by end-2027. Capacity is not customer-accepted output. [2,18]',x=520,top=273,width=400,size=10.3,leading=14)
para('<b>Ibiden:</b> 1.3x server CPU market growth x 1.9x load per product describes production demand. Added Gama investment ramps in second-half FY2029; no Intel allocation is disclosed. [11,14]',x=520,top=340,width=400,size=10.3,leading=14)
rect(L,412,CW,61,PALE)
para('<b>What the H2 revenue hurdle requires:</b> with flat H1 at my Q4 sales estimate, H2 needs +41% units at flat sequential ASP, +28% units at ASP +10%, or +18% units at ASP +20%. These are required combinations, not capacity forecasts.',x=53,top=425,width=854,size=11,leading=15)
source('Sources: Intel [2,10,18,19], Ibiden [11,14]; my conditional arithmetic. The model\'s annual ASP +20% is not H2/H1 ASP +20%.\nIreland, substrate capacity and finished CPU units have different denominators. Do not multiply them or add committed funding again without reconciling the cash budget.')
c.showPage()

# 5
page(5,'Durability','Contracts support the ramp; renewals determine durability.','Multiyear pricing visibility strengthens the near-term case, while the 40% mature DCAI margin remains a forecast.')
table(['Reported DCAI','Q1 2026','Q2 2026','Q3 2026'],[
 ['Revenue, $B','5.05','6.26','7.32'],['Operating margin','30.5%','39.5%','41.5%'],['Server ASP, YoY','+27%','+48%','+54%']],140,[220,220,220,220],row_h=26,size=11,emphasize=[1])
note('Intel attributes $4.5B of the $4.88B YTD operating-profit increase to product profit. The improvement is more than lower charges. [2,5,13]',255,size=9.7)
for xx in [40,500]:rect(xx,292,420,122,PALE)
label('MULTIYEAR VOLUME AND PRICING TERMS',304,x=53,color=ACCENT,size=8.7)
para('<b>Signed DCAI agreements include Google.</b> The CFO described most agreements as covering volume and pricing for 3-5 years. In August, he reported stable or rising like-for-like ASP per core. [19-21]',x=53,top=327,width=394,size=10.8,leading=14.5)
para('This supports pricing visibility; coverage, cancellation terms and net contribution margins are undisclosed.',x=53,top=384,width=394,size=9.6,leading=13)
label('CONTRACT VISIBILITY ENDS BEFORE THE VALUE DOES',304,x=513,color=BLUE,size=8.3)
para('<b>2026 starts imply roughly 2029-31 expiries.</b> They do not establish 40% DCAI margins through 2031-40. Pricing visibility alone does not protect margins from rising input costs.',x=513,top=327,width=394,size=10.8,leading=14.5)
para('Retention is workload-specific: Azure HANA certification favors Intel; managed HANA Cloud and Datadog show Arm alternatives. [15-17]',x=513,top=376,width=394,size=9.6,leading=13)
para('<b>Why I use 40%:</b> recent product economics and richer mix can sustain profit as Other DCAI grows. But 2023 / 2024 / 2025 margins were 5.9% / 8.8% / 20.2%. Contract renewals and consolidated costs must validate persistence. Margin erosion to 35% by 2030 lowers the target to $68.14.',top=433,size=10.5,leading=14)
source('Sources: Intel [2,4,5,13,19-21]; customer evidence [15-17]. Terms are management descriptions in published transcripts, not reviewed executed contracts.\nGoogle\'s signed agreement is verified in original remarks. Exact starts, revenue coverage and renewal economics are unknown. No extra pricing benefit is added to the forecast.')
c.showPage()

# 6
page(6,'Cash & value','Higher profit first pays for the investment required to earn it.','My 2027-2030 cumulative cash bridge | USD billions')
steps=[('Operating\nprofit',cash_bridge['EBIT_B']),('D&A',cash_bridge['DA_B']),('Physical\ncapex',-cash_bridge['physical_cash_capex_B']),('Working\ncapital',-cash_bridge['WC_use_B']),('Net tax /\nincentives',cash_bridge['net_tax_incentives_B']),('Leases /\nminorities',-cash_bridge['leases_NCI_B']),('Net\nfinancing',cash_bridge['net_financing_B'])]
assert abs(sum(s[1] for s in steps)-cash_bridge['owner_cash_B'])<1e-9
wy=lambda z:158+(200-z)/200*145;curr=0
for tick in [0,50,100,150,200]:line(65,wy(tick),920,wy(tick),RULE,.4);text(58,wy(tick)-5,str(tick),'Sans',8.5,MUTED,'right')
for i,(name,delta) in enumerate(steps+[('Owner\ncash',cash_bridge['owner_cash_B'])]):
    xx=74+i*106;total=i==7;start,finish=(0,delta) if total else (curr,curr+delta);tt,bb=wy(max(start,finish)),wy(min(start,finish));co=INK if i in [0,7] else (ACCENT if delta<0 else BLUE)
    rect(xx,tt,67,max(bb-tt,1),co);text(xx+33.5,tt-17 if delta>=0 or total else bb+5,f'{delta:+.1f}' if i not in [0,7] else f'{delta:.1f}','SansB',11,co,'center')
    for j,part in enumerate(name.split('\n')):text(xx+33.5,326+j*12,part,'Sans',9,INK,'center')
    if not total and i<6:line(xx+67,wy(finish),xx+106,wy(finish),MUTED,.6,[2,2])
    curr=finish
label('DCAI AND FOUNDRY DRIVE 89% OF 2027-28 EBIT GROWTH',368,color=BLUE)
para('$14.43B + $5.56B DCAI sales + $0.37B DCAI margin + $3.25B Foundry recovery + $1.11B other changes = <b>$24.73B.</b>',top=390,width=425,size=11,leading=15)
note('Q3 Foundry loss narrowed $0.47B YoY, helped by $0.79B lower period charges. Further factory profit recovery remains a forecast.',433,width=425,size=9.5)
rows=[]
for key,caption in [('EBIT_after_economic_SBC_B','Group EBIT'),('owner','Owner cash')]:
    vals=[]
    for i,y in enumerate(range(2027,2031)):
        val=model['treasury_rows'][i]['owner_cash_after_financing_and_incentives_B'] if key=='owner' else model['annual_operating_rows'][i][key];vals.append(f'{val:.1f}')
    rows.append([caption]+vals)
table(['Forecast, $B','2027','2028','2029','2030'],rows,370,[164,64,64,64,64],x=500,row_h=27,size=10.1,emphasize=[1])
note('$70.3B net investment = capex - D&A + working capital.',459,width=425,size=9.3)
note('Q3 cash + short-term investments: $54.0B; debt: $50.1B.',459,x=500,width=420,size=9.3)
source('Intel [2,4]; my model. Owner cash includes incentives, financing and economic SBC/NCI reserves. It precedes debt principal, acquisitions and separately reserved Altera/VLSI payments.\nNot GAAP FCF or a dividend. Minority payouts and investment sufficiency remain estimates.')
c.showPage()

# 7
page(7,'Cash & value','The current price leaves little room for the forecast to miss.','Adjusted present value: operating cash and financing tax benefits, plus cash and other financial claims | 5.51B planning shares')
table(['Base valuation','Dec. 2026','Dec. 2030'],[
 ['Operating cash through 2040, PV',f"${v['explicit_operating_PV_B']:.1f}B",f"${base2030['explicit_operating_PV_B']:.1f}B"],
 ['Operating cash after 2040, PV',f"${v['terminal_operating_PV_B']:.1f}B",f"${base2030['terminal_operating_PV_B']:.1f}B"],
 ['Net claims and tax benefits',f"${v['equity_B']-v['explicit_operating_PV_B']-v['terminal_operating_PV_B']:.1f}B",f"${base2030['equity_B']-base2030['explicit_operating_PV_B']-base2030['terminal_operating_PV_B']:.1f}B"],
 ['Equity value per share',f"${v['price_USD']:.2f}",f"${target:.2f}"]],142,[300,130,130],row_h=28,size=10.4,emphasize=[3])
label('SAME TARGET, DIFFERENT ENTRY REQUIREMENTS',145,x=635,color=ACCENT,size=8.1)
table(['Annual return','Entry ceiling'],[['10%','$52.14'],['12%','$48.38'],['15%','$43.35']],170,[145,140],x=635,row_h=25,size=11,emphasize=[0])
note('Includes a $1.215B Altera / VLSI reserve; restricted EC collateral remains excluded. [2,4]',287,size=8.8)
label('DURATION IS THE MAIN VALUATION DEPENDENCY',305,color=BLUE)
text(40,333,'92.3%','SansB',30,BLUE)
para('of operating value at December 2026 comes from cash after 2030. A good 2027 does not, by itself, validate that duration.',x=166,top=333,width=345,size=11,leading=15)
label('MATURE MARGIN THAT MATCHES $52.25*',309,x=555,size=8.7)
table(['CPU revenue after 2030','DCAI margin'],[['2030-40: 6.0% CAGR','41.4%'],['3% annual growth','48.8%']],332,[235,130],x=555,row_h=29,size=10.7)
para(f'<b>Base conventions:</b> mature DCAI margin 40%, phased during 2031-40; capital productivity 0.80; flat operating discount rate 11.555%; terminal growth 3% with continuing investment. The base price return is {cagr:.2%} a year, conditional on this forecast.',top=429,size=10.5,leading=14)
source('*Conditional one-variable solutions, holding other inputs fixed; not unique market expectations. The $52.25 quote precedes the planning date by 56 days.\nSources: my valuation; rate method/inputs [6,7]. Capital productivity is incremental modeled sales / net operating investment, not independently measured factory capacity. No multiple expansion is assumed.')
c.showPage()

early_growth = json.loads((two_hour/'model_audit/early_growth_deceleration_results.json').read_text())['summary']

# 8
page(8,'Decision','Lasting profit damage matters more than a temporary delay.','Same $52.25 entry and December 2030 horizon | Conditional scenarios, not probabilities or loss limits')
paired=return_bridge['paired_scenarios']
cases=[
 ('Base LONG',by_case['base']['December2026_planning_value_USD'],target,cagr),
 ('Foundry recovery delayed one year',by_case['foundry_recovery_delayed_one_year']['December2026_planning_value_USD'],by_case['foundry_recovery_delayed_one_year']['December2030_target_USD'],by_case['foundry_recovery_delayed_one_year']['annual_price_return_from52_22']),
 ('DCAI margin reaches 35% by 2030',by_case['profit_retention_erosion_from_2028']['December2026_planning_value_USD'],by_case['profit_retention_erosion_from_2028']['December2030_target_USD'],by_case['profit_retention_erosion_from_2028']['annual_price_return_from52_22']),
 ('CPU units +10% annually, 2028-30; 2027 unchanged',early_growth['planning_value_USD'],early_growth['target_2030_USD'],early_growth['annual_price_return']),
 ('CPU revenue grows 3% from 2031',by_case['CPU_growth_normalizes_2031']['December2026_planning_value_USD'],by_case['CPU_growth_normalizes_2031']['December2030_target_USD'],by_case['CPU_growth_normalizes_2031']['annual_price_return_from52_22']),
 ('Persistently lower CPU demand',by_case['persistent_lower_CPU_demand']['December2026_planning_value_USD'],by_case['persistent_lower_CPU_demand']['December2030_target_USD'],by_case['persistent_lower_CPU_demand']['annual_price_return_from52_22']),
 ('Joint downside',by_case['joint_downside']['December2026_planning_value_USD'],by_case['joint_downside']['December2030_target_USD'],by_case['joint_downside']['annual_price_return_from52_22'])]
cases=[(n,a,b,(b/entry_price)**(1/years)-1) for n,a,b,_ in cases]
table(['Scenario','Dec. 2026 value','Dec. 2030 value','Annual return'],[[n,f'${a:.2f}',f'${b:.2f}',f'{d:+.1%}'] for n,a,b,d in cases],140,[340,180,180,180],row_h=26,size=10.7,emphasize=[0])
para('<b>Temporary delay:</b> Foundry profit follows the prior year\'s path through 2030 and rejoins the base in 2031; planned investment stays. The lost cash reduces the target by $1.70.',top=361,size=10.1,leading=13.5)
para('<b>Growth and margins:</b> the 35% margin case erodes from 2028. The illustrative 10% unit case keeps 2027 unchanged and preserves the lower later sales level; planned capex and Foundry profit stay fixed through 2030. The 3% case changes CPU revenue from 2031.',top=397,size=10.1,leading=13.5)
para('<b>Lower demand / joint downside:</b> 2027 CPU sales $26.45B versus $31.48B; the lower level persists. The joint case also uses 30% mature margin and 0.60 productivity. Its $30.23 planning value is about 42% below entry; losses can be larger.',top=439,size=10.1,leading=13.5)
source('My operating, tax, investment and treasury scenarios; 11.555% operating rate retained. Scenarios are not independent effects and are not added together.\nAnnual returns run from November 5, 2026. Planning values are December 31, 2026. No dividends, costs or taxes; the market need not reach any modeled endpoint.')
c.showPage()

# 9
page(9,'Decision','The next results must validate both delivery and durability.','These checkpoints change the forecast. They are not scheduled stock-price catalysts.')
for xx,yr,head,body in [
 (40,'2027','Turn the ramp into deliveries','My test: CPU sales $31.48B. Each quarter, recalculate sales still needed, then test units and ASP against Ireland output and packaging supply.'),
 (342,'2028','Approach Foundry breakeven','My test: Foundry loss narrows to $0.75B; owner cash turns positive at $2.3B. Separate cost/yield gains from inventory and period-charge effects.'),
 (644,'2029-2030','Retain economics at renewal','My test: repeat deployments and pricing as early agreements may approach renewal. Keep owner cash on course for $21.9B in 2030 after investment.')]:
    rect(xx,140,276,135,PALE);label(yr,152,x=xx+13,color=ACCENT,size=12);para(head,x=xx+13,top=179,width=250,font='SansB',size=12,leading=15);para(body,x=xx+13,top=211,width=250,size=10.1,leading=13.5)
label('EVIDENCE',297);label('HOW I WOULD CHANGE THE FORECAST',297,x=316)
items=[
 ('A delivery miss with customers still waiting','Required quarterly average: ($31.48B - actual YTD CPU sales) / quarters left. Preserve next-year volumes only with backlog and catch-up capacity.'),
 ('Repeat losses to AMD or Arm, or weaker pricing','Reduce the sales level or retained profit. Recent 40% margins cannot answer this; certification, software economics and customer behavior matter.'),
 ('More spending or partner claims without output','Raise required investment or cash claims after reconciliation. The model\'s capital ratio and minority reserve are planning assumptions, not contractual guarantees.')]
for i,(head,body) in enumerate(items):
    yy=322+i*50;para(head,top=yy,width=252,font='SansB',size=11.3,leading=14);para(body,x=316,top=yy,width=604,size=10.5,leading=14);line(L,yy+44,R,yy+44,RULE,.4)
source('Sources: Intel [2,10,19-21]; customer evidence [15-17]; Arizona agreement [9]. Use the same CPU allocation scope when updating the quarterly hurdle.\nThe long remains moderate conviction at the reference price. A lower entry improves prospective return; it does not repair a deteriorating business forecast.')
c.showPage()

# 10
page(10,'Sources','Sources and valuation conventions','Evidence reviewed through November 6, 2026 | Public-source analysis and explicit analyst forecasts')
label('HOW TO READ THE VALUATION',140)
para('Operating cash is valued separately from financing tax benefits. Cash, debt, holdings and specified obligations then produce equity value.',top=163,width=270,size=10.7,leading=15)
para('The 2026 planning value covers 2027-40 cash plus the terminal period. The 2030 target covers 2031 onward, plus cash accumulated by then.',top=232,width=270,size=10.3,leading=14)
para('Growth requires continuing investment. The 0.80 capital ratio is a forecast rule, not a factory-level capacity model. Financing tax benefits use zero terminal growth.',top=301,width=270,size=10.3,leading=14)
para('Economic SBC and minority reserves are charged. 5.51B planning shares include specified dilution. Reserves are not exact cash-distribution or future-cap-table forecasts.',top=370,width=270,size=10.3,leading=14)
para('Research uses public filings, industry forecasts and customer engineering accounts. Calculations and forecast assumptions are identified.',top=445,width=270,size=9.6,leading=13,color=MUTED)
refs=[
('1','INTC price history','November 5 close: $52.25.','https://stockanalysis.com/stocks/intc/history/'),
('2','Intel Q3 2026 Form 10-Q','Segments; MD&A; Note 14 commitments.','https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm'),
('3','TrendForce, October 22, 2026','2027 server CPU demand and share forecasts.','https://www.trendforce.com/presscenter/news/20261022-13279.html'),
('4','Intel FY2025 Form 10-K','Recast DCAI margins and cash classifications.','https://www.intc.com/filings-reports/annual-reports/content/0000050863-26-000011/intc-20251227.htm'),
('5','Intel Q2 2026 Form 10-Q','Quarterly DCAI economics and mix.','https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000157/intc-20260627.htm'),
('6','NYU, November 2026 ERP workbook','Treasury and equity-premium inputs.','https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPNov26.xlsx'),
('7','NYU, bottom-up beta method','Cash, leverage and operating business risk.','https://pages.stern.nyu.edu/~adamodar/New_Home_Page/TenQs/TenQsBottomupBetas.htm'),
('8','M37 official competition rules','Initial screen; 3-5-year fundamental horizon.','https://www.m37.com/spc2026'),
('9','Executed Arizona SCIP agreement','Distribution priority and later Intel catch-up.','https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-22-291100/d412415dex101.htm'),
('10','Intel Q3 2026 prepared remarks','pp. 1-3, 5-7: products, capacity and outlook.','https://d1io3yog0oux5.cloudfront.net/_47986fe477a6ac84fe34efbcbf38dd13/intel/db/887/9273/prepared_remarks/Q3%2726_Prepared_Remarks.pdf'),
('11','Ibiden, October 30, 2026 Q&A','Gama ramp timing and substrate constraints.','https://www.ibiden.com/ir/items/en_QA_FY2026Q2.pdf'),
('12','S&P estimates via Stock Analysis','Updated Nov. 5: 2027 total revenue.','https://stockanalysis.com/stocks/intc/forecast/'),
('13','Intel Q1 2026 Form 10-Q','Quarterly DCAI margins, ASPs and units.','https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000079/intc-20260328.htm'),
('14','Ibiden, October 30 presentation','pp. 12-13: production load and project scope.','https://www.ibiden.com/ir/items/en_kessannsetsumei2026Q2.pdf'),
('15','Datadog engineering, Dec. 2, 2024','Production Arm migration and x86 fallback.','https://www.datadoghq.com/blog/arm-migration-aws/'),
('16','Microsoft: SAP on Azure FAQ','SAP HANA certification boundary.','https://learn.microsoft.com/en-us/azure/sap/workloads/get-started'),
('17','SAP, November 7, 2023','HANA Cloud support for AWS Graviton.','https://news.sap.com/2023/11/sap-hana-cloud-now-supports-aws-graviton/'),
('18','Intel Q3 call: published transcript','Q&A 31:56-43:06: growth, supply timing and Fab 28.','https://www.marketbeat.com/earnings/reports/2026-10-29-intel-co-stock/'),
('19','Intel, August 26: Quartr transcript','CFO: Ireland output; ASP per core.','https://stockanalysis.com/stocks/intc/transcripts/736613-deutsche-bank-2026-technology-conference/'),
('20','Intel Q1 call: published transcript','First CFO Q&A: LTA terms, 3-5 years.','https://storage.googleapis.com/magi-store/earnings/INTC/2026-04-23_Q1_FY2026/03_outputs/transcript.html'),
('21','Intel Q1 original prepared remarks','p. 4: signed DCAI LTAs incl. Google.','https://download.intel.com/newsroom/2026/earnings/1Q2026-Earnings-Call.pdf'),
]
label('CLAIM-LEVEL SOURCES | LIVE LINKS',140,x=335,size=8.3)
for i,(num,name,desc,url) in enumerate(refs):
    col=i//11;row=i%11;xx=335+col*298;yy=160+row*29
    text(xx,yy,num,'SansB',8.5,ACCENT)
    para(f'<link href="{escape(url,quote=True)}" color="#16283E"><b>{escape(name)}</b></link><br/>{escape(desc)}',x=xx+20,top=yy-1,width=265,size=8.2,leading=10)
source('M37 Initial Screen | Thomas Ou, Class of 2027 | Individual entry | Figures rounded for display; calculation precision does not imply forecast precision.')
c.showPage();c.save()

from pypdf import PdfReader
reader=PdfReader(OUT);texts=[p.extract_text() for p in reader.pages]
assert len(texts)==10
for key in ['$52.25','$77.46','$51.07','$45.47','$30.23','$58.83','$48.38','9.9%','92.3%','68.14','LONG']:
    assert key in '\n'.join(texts),key
assert all(len(t)>600 for t in texts)
assert hashlib.sha256(model_path.read_bytes()).hexdigest()=='f040f1f39a5daee1bbc9143129622440460e09bdcd2f9b83c4a374e13771e052'
folder=ROOT/'tmp/pdfs/intel_long'
(folder/'extracted.txt').write_text('\n\n'.join(f'PAGE {i+1}\n{t}' for i,t in enumerate(texts)))
links=sum(1 for p in reader.pages for a in p.get('/Annots',[]) if a.get_object().get('/A',{}).get('/URI'))
manifest={'path':str(OUT),'pages':10,'page_size':[W,H],'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'links':links,'source_model_unchanged':True,'submitted':False,'recommendation':'LONG, moderate conviction','base_target_2030':target,'entry':entry_price,'price_CAGR':cagr,'visual_qa':'pending','claims_overlay':str(claims_overlay_path),'additional_claims_reserve_B':1.215,'body_boxes':logs}
(folder/'build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='body_boxes'},indent=2))

from reportlab.platypus import SimpleDocTemplate, Spacer, PageBreak, KeepTogether
notes_path=ROOT/'output/pdf/m37_intel_defense_notes.pdf'
styles={
 'title':ParagraphStyle('nt',fontName='SansB',fontSize=20,leading=25,textColor=INK,spaceAfter=7),
 'subtitle':ParagraphStyle('ns',fontName='Sans',fontSize=9.2,leading=12.5,textColor=MUTED,spaceAfter=15),
 'question':ParagraphStyle('nq',fontName='SansB',fontSize=11,leading=14.5,textColor=INK,spaceAfter=5),
 'body':ParagraphStyle('nb',fontName='Sans',fontSize=10.2,leading=14.3,textColor=INK,spaceAfter=12),
 'small':ParagraphStyle('nm',fontName='Sans',fontSize=8.5,leading=11.5,textColor=MUTED,spaceAfter=7),
}
def np(s,sty='body'):
    s = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;)', '&amp;', s)
    return Paragraph(s,styles[sty])
from reportlab.platypus import Table, TableStyle

def notes_table(headers, rows, widths):
    data=[[np(escape(str(v)),'small') for v in headers]]+[[np(escape(str(v)),'small') for v in row] for row in rows]
    t=Table(data,colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PALE),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.35,RULE),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),2)]))
    return t

def qa(q,a):
    return KeepTogether([np(q,'question'),np(a)])

intelq3='https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm'
remarks='https://d1io3yog0oux5.cloudfront.net/_47986fe477a6ac84fe34efbcbf38dd13/intel/db/887/9273/prepared_remarks/Q3%2726_Prepared_Remarks.pdf'
aug_transcript='https://stockanalysis.com/stocks/intc/transcripts/736613-deutsche-bank-2026-technology-conference/'
q1_transcript='https://storage.googleapis.com/magi-store/earnings/INTC/2026-04-23_Q1_FY2026/03_outputs/transcript.html'
q1_remarks='https://download.intel.com/newsroom/2026/earnings/1Q2026-Earnings-Call.pdf'
consensus_url='https://stockanalysis.com/stocks/intc/forecast/'
opening='My recommendation is a moderate-conviction long in Intel, with a $77.46 target for December 2030. Server growth and richer products can outweigh a weak PC market; better factory output can turn investment into cash. I forecast 20% more server CPUs at a 20% higher average selling price in 2027. The difficult assumption is that Intel retains strong product economics after shortages ease. At $52.25, the base gives about 10% annual price appreciation and little initial discount. I would prefer an entry near $48.38 for a 12% base-case return. Neither return is guaranteed.'
story=[np('Intel | Pitch defense notes','title'),np('LONG | Moderate conviction | November 6, 2026 | Private preparation; separate from the Initial Screen','subtitle'),np('Opening statement','question'),np(opening),
qa('Why own it at $52.25 if planning value is $51.07?',
'The affirmative case is that a bigger server market and richer mix can increase profit even while Intel loses share. My 2027 DCAI margin of 38.8% is below Q3\'s 41.5%, and forecast CPU sales are about 21% above the modeled Q4 annualized run-rate. That supports a recovery without a new wafer-customer jackpot. But the entry is approximately fair value. The 9.9% figure is a conditional base-case return, not a probability-weighted expectation; a strong risk-adjusted price advantage remains unestablished.'),
qa('Does a $77.46 target mean about 48% immediate undervaluation?',
'No. It is a December 2030 value. The $51.07 estimate is at December 31, 2026, 56 days after the reference quote. The later target includes accumulated cash, fewer years of discounting and the value of cash earned after 2030. Comparing today\'s price directly with an undiscounted future target confuses investment return with current mispricing.'),
qa('What is the actual disagreement with other forecasts?',
'The S&P Global proxy, updated November 5, puts 2027 total revenue at $69.27B. My $68.33B Products forecast leaves only $0.94B for external Foundry and net All Other. My All Other segment proxy alone is $2.80B, before its revenue eliminations. This exposes optimism but is not a matched consolidated beat or segment consensus: my capital denominator omits legacy external Foundry sales. Server recovery is already widely discussed; accepted deliveries and retained profit must justify my stronger path. '+link('Current forecast source',consensus_url)),
qa('What would change the recommendation?',
'Persistent customer loss, weaker realized economics or more investment for the same output would reduce my forecast. A short delivery delay with customers still waiting mainly changes timing. A customer-specific, economically distinct external program could add upside only after paying for capacity and removing overlap with existing forecasts.'),
np('Do not claim a winning probability, a proprietary information advantage, or a market belief that has not been measured. Public-source synthesis can be useful without any of those claims.','small')]

story += [PageBreak(),np('Delivery and the earnings bridge','title'),np('Keep industry demand, Intel shipments and customer acceptance separate. All forward figures below are forecasts.','subtitle'),
qa('What do the 20% unit and 20% ASP assumptions mean?',
'From my $21.86B estimated 2026 CPU base, units add $4.37B and ASP on the larger volume adds $5.25B: $31.48B total. My Q4 CPU estimate of $6.53B annualizes to $26.10B; 2027 needs another 20.6%. If H1 holds that pace, H2 needs $9.21B per quarter (+41.2% revenue). Required H2/H1 units are +41.2% at flat ASP, +28.3% at ASP +10%, or +17.6% at ASP +20%. Annual ASP +20% is not sequential H2 ASP +20%; these combinations are requirements, not production estimates.'),
qa('Is the forecast secretly relying on a PC recovery?',
'No near-term volume boom is assumed. In 2027, client units fall 12% and CCPG profit falls $1.38B; DCAI profit rises $5.09B. By 2030, client units are approximately back to 2026 levels. DCAI and lower Foundry losses drive 89% of the 2027-28 EBIT increase. Q3 Foundry improved $0.47B, but lower period charges contributed $0.79B while product profit fell $0.11B. Further factory profit recovery needs more than repeating that charge benefit.'),
qa('Where is the capacity proof?',
'In August, the CFO targeted more than double Ireland output in 2027 while discussing Intel 3 / Granite Rapids. October remarks report progressing tools and rising output. Oregon output and much of a 40% substrate-capacity increase are planned for H2 2027. These are real production plans, but output units, mix, yields and customer acceptance remain undefined. Fab 28\'s ~$300M Q4 sales hit is already in my anchor; a similar early Q1 estimate is not quarterly-reconciled. My Q4 DCAI margin remains judgment. No public Intel-specific accepted-package schedule validates my forecast.'),
qa('How much does a delay hurt?',
'If 2027 unit growth is 10% and Intel restores the base absolute volume in 2028, the target is $77.26. That recovery needs 36.4% unit growth in 2028; it is not automatic and missed 2027 sales are not recaptured. Persistent lower demand instead gives $58.83. A separate one-year Foundry profit delay through 2030, rejoining the base in 2031 with investment retained, gives $75.76.'),
qa('Is all Other DCAI growth supported by the custom-silicon outlook?',
'No. Management expects purpose-built silicon to triple over the next few years. My broader Other DCAI bucket grows $5.19B to $17.44B, or 3.36x, from 2026E to 2030. The scopes differ and standalone margins are undisclosed. This is an assumption following an identified opportunity, not a contracted revenue schedule or proof of the segment\'s 40% mature margin.'),
np('Sources: '+link('Intel Q3 filing',intelq3)+'; '+link('prepared remarks',remarks)+'; '+link('August CFO transcript',aug_transcript)+'; '+link('Q3 call Q&A','https://www.marketbeat.com/earnings/reports/2026-10-29-intel-co-stock/')+'; '+link('Ibiden presentation','https://www.ibiden.com/ir/items/en_kessannsetsumei2026Q2.pdf')+' and '+link('Q&A','https://www.ibiden.com/ir/items/en_QA_FY2026Q2.pdf')+'. Published August transcripts match; original audio was not independently checked. Calculations are mine.','small')]

story += [PageBreak(),np('Can Intel keep the profit?','title'),np('Demand, customer usefulness and supplier profit are related; none substitutes for the others.','subtitle'),
qa('Why use a 40% mature DCAI operating margin?',
'Q2/Q3 margins were 39.5%/41.5%; Intel attributes $4.5B of the $4.88B YTD improvement to product profit. But 2023/2024/2025 margins were 5.9%/8.8%/20.2%. Strong CPU economics must persist as lower-margin Other revenue grows. This is an assumption, not a demonstrated across-cycle floor.'),
qa('Do the contracts protect that margin?',
'Original Q1 remarks confirm signed DCAI agreements including Google. In Q&A, the CFO described most agreements as covering volume and pricing for 3-5 years; August comments support stable or rising like-for-like ASP/core. This strengthens near-term visibility. Coverage, minimum purchases, cancellation rights and cost protection are undisclosed. A 2026 start implies roughly 2029-31 expiry, leaving mature margins dependent on renewals. Oracle\'s October roadmap is prospective, not proof of another signed price contract.'),
np('A conditional way to inspect that assumption','question'),
np('CPU margin = (DCAI margin - Other revenue share x assumed Other margin) / CPU revenue share. Neither standalone margin is disclosed. Using Q3 economics and a hypothetical 20% Other margin implies a 46.6% CPU margin. Holding that CPU margin while Other rises to 24.7% of mature revenue yields a roughly 40.0% blended margin.','small'),
notes_table(['Conditional change from this mature illustration','DCAI margin'],[['No CPU ASP/cost change','40.0%'],['CPU ASP -10%; quantities and dollar costs unchanged','35.2%'],['CPU ASP -10%; enough future cost reduction to retain margin','40.0%']],[390,126]),Spacer(1,6),
np('The last row requires about 11.2% lower CPU expenses within DCAI at fixed quantities and Other revenue/profit. Assuming Other margins of 10% or 30% changes that requirement to 13.5% or 9.0%. These are illustrations, not empirical bounds or wafer-cost targets; revenue weights change when CPU prices change.','small'),
qa('Why should customers stay?',
'Azure does not support AMD VMs for SAP HANA, protecting some deployments. Managed HANA Cloud supports Graviton. Datadog migrated roughly 2,000 services, 70% of AWS workloads, to Arm by end-2023, reporting a 10% AWS-bill saving with x86 fallback. Its prior x86 vendor mix is unknown; this does not test current Xeon 6. Retention is workload-specific.'),
qa('Can lower manufacturing costs protect both segments?',
'Potentially, but Intel 3\'s reported 15% cost reduction since Q1 is already in the Q3 anchor. Future wafer savings must reach all-in package and operating costs. Lower internal wafer charges transfer profit between Products and Foundry without creating a group gain. No separate node-saving windfall is added; future inventory-profit eliminations are normalized to zero. Consolidated cash must validate both recoveries.'),
np('Sources: '+link('Q3 filing',intelq3)+'; '+link('Q3 remarks',remarks)+'; '+link('Q1 original remarks p. 4',q1_remarks)+'; '+link('Q1 published Q&A',q1_transcript)+'; '+link('August CFO transcript',aug_transcript)+'; '+link('Oracle roadmap','https://www.intel.com/content/www/us/en/newsroom/news/corporate/intel-oracle-collaborate-on-enterprise-and-agentic-ai.html')+'; '+link('Microsoft','https://learn.microsoft.com/en-us/azure/sap/workloads/get-started')+'; '+link('SAP','https://news.sap.com/2023/11/sap-hana-cloud-now-supports-aws-graviton/')+'; '+link('Datadog','https://www.datadoghq.com/blog/arm-migration-aws/')+'. LTA terms are transcript descriptions, not reviewed executed contracts or independently verified audio.','small')]

story += [PageBreak(),np('Cash, valuation and model limits','title'),np('A reconciled model makes assumptions inspectable. It does not independently validate them.','subtitle'),
qa('Where does the cash go?',
'Cumulative 2027-30 EBIT of $111.3B plus $72.2B D&A is reduced by $124.5B physical capex, $18.0B working capital, $8.7B leases/minority reserves and $5.9B net financing; net taxes/incentives add $1.2B. Owner cash is $27.6B. It is before debt principal, acquisitions and payments against separately reserved Altera/VLSI claims; it is not GAAP free cash flow or a dividend.'),
qa('How much value depends on the distant future?',
'At December 2026, 92.3% of operating value comes from cash after 2030; 46.3% comes after 2040. The first figure includes explicit 2031-40 forecasts, not only the perpetuity. A good 2027 therefore cannot establish the full value. The model\'s 2030-40 CPU revenue CAGR is 6.0%; changing it to 3% from 2031 with investment responding reduces the target to $69.63.'),
notes_table(['Conditional case','Dec. 2026','Dec. 2030','Annual return'],[['Base','$51.07','$77.46','9.9%'],['35% DCAI margin by 2030, held thereafter','$45.00','$68.14','6.6%'],['CPU units +10% annually in 2028-30','$43.65','$66.13','5.8%'],['Persistent lower CPU demand','$38.85','$58.83','2.9%'],['Joint demand / 30% margin / 0.60 productivity','$30.23','$45.47','-3.3%']],[249,89,89,89]),Spacer(1,7),
np('These states are not probabilities or loss limits. Early margin erosion starts in 2028; mature-only 35% gives $70.76. The illustrative 10% unit-growth case leaves 2027 unchanged, preserves its lower later sales level, holds capex/Foundry profit through 2030 and applies 50% lost-sales EBIT impact. That cost response may understate factory losses. It is not a market forecast.','small'),
qa('What remains approximate in capital and minority claims?',
'The 0.80 ratio is incremental modeled sales divided by net operating investment; it is not a physical factory-capacity estimate. Its revenue denominator omits legacy external Foundry sales. Funding the known embedded-packaging revenue growth alone lowers the target about $0.16, but does not complete that reconciliation. The terminal incremental NOPAT/net-investment ratio is about 23.5%, with R&D expensed; it is not a fully capitalized economic ROIC. Arizona distributions remain an economic reserve because the special-distribution amount is undisclosed.'),
qa('How are the newly mapped claims treated?',
'All values deduct $215M owed to SLP for Altera costs and the $1B VLSI litigation accrual: $0.22 per share. Cash budgets exclude these named payments; a later payment reduces cash and releases its reserve once. VLSI is a book reserve, not a loss ceiling. EC guarantee collateral is already excluded as restricted cash; no duplicate fine deduction or presumed surplus is added.'),
np('Valuation uses 11.555% flat operating risk, separately valued financing tax benefits, 3% funded terminal growth and 5.51B planning shares. The asset discount rate is not identical to the stock\'s price CAGR because cash balances and financing differ. '+link('Arizona agreement','https://www.intc.com/filings-reports/all-sec-filings/content/0001193125-22-291100/d412415dex101.htm')+'; claims: '+link('Q3 Notes 9 and 14',intelq3)+'; EC collateral: '+link('2025 Form 10-K','https://www.intc.com/filings-reports/annual-reports/content/0000050863-26-000011/intc-20251227.htm')+'.','small')]

story += [PageBreak(),np('Original work and its boundaries','title'),np('Independent calculations on public data; no interviews or new workload experiments were performed.','subtitle'),
np('Oracle billing audit: include memory in the comparison','question'),
notes_table(['Per hour, USD','Intel X9 Standard','Intel X12 Ax'],[['OCPUs / memory GB','64 / 1,024','120 / 1,152'],['CPU charge','2.5600','1.4280'],['Memory charge','1.5360','13.1328'],['Combined charge','4.0960','14.5608']],[200,158,158]),Spacer(1,6),
np('CPU plus memory costs 3.55x as much. At the separate vendor throughput claims of 5x/6x, work per dollar improves 1.41x/1.69x, conditional on matched accepted quality and latency. Resources and test conditions differ. A contemporary 4-OCPU/32-GB comparison costs $0.4124/hour for Intel X12 Ax versus $0.4008 for AMD E6 Ax: Intel needs 2.9% more successful throughput for parity. No matched workload was run.','small'),
np('Sources: '+link('Oracle inference article','https://blogs.oracle.com/cloud-infrastructure/run-ai-inference-without-gpus')+'; '+link('launch prices','https://blogs.oracle.com/cloud-infrastructure/announcing-oci-x12-standard-acceleron-compute')+'; '+link('price feed','https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/?currencyCode=USD')+' (November 2 snapshot); '+link('shapes','https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm')+'. Excludes storage, egress, licenses, discounts, tax and support.','small'),
qa('Does expensive software give Intel pricing power?',
'Only if Intel has an advantage over the next-best qualified system. Two audited 32-core HPE SQL configurations list the same $241,968 license bill: two Xeon 6724P sockets versus one EPYC 9375F. AMD\'s complete system scored 29.3% higher with 26.9% lower reported price/performance, but RAM, storage, OS, tuning and dates differ. These 2025 quotations isolate neither CPU performance nor current buyer cost. Faster CPUs save licenses only when the workload fits fewer payable cores. Neither these results nor our SpareCores/SPEC review proves Intel net ASP or margin.'),
np('TPC-H 1TB disclosures, configuration / quotation / results on pp. 4-6: '+link('HPE / Intel','https://www.tpc.org/results/fdr/tpch/hpe~tpch~1000~hpe_proliant_dl380_gen12~fdr~2025-04-23~v03.pdf')+'; '+link('HPE / AMD','https://www.tpc.org/results/fdr/tpch/hpe~tpch~1000~hpe_proliant_dl345_gen11_(with_amd_epyc_9375f)~fdr~2025-09-30~v01.pdf')+'. Same license count does not mean matched hardware.','small'),
qa('What counts as the research contribution?',
'The useful contribution is the audit trail: separate units from ASP, constrain accepted output, distinguish a delay from permanent loss, translate margin assumptions into price/cost requirements, and reconcile profit to funded cash and dated value. These checks can uncover a weak assumption. They do not become a durable information edge merely because the calculations are original.'),
qa('What is submitted for Round 1?',
'The separate 10-page Initial Screen PDF, with name, class year and a current resume. These defense notes and the comparison brief are preparation, not extra screen pages. The official deadline is November 9, 2026; the page states no time of day or time zone. It requires a clear long or short recommendation over 3-5 years. No entry has been sent.'),
np(link('Official M37 competition rules','https://www.m37.com/spc2026')+'. Round 2 is due November 30; final discussion is December 5. M37 evaluates investment theses and judgment rather than model complexity.','small')]

def frame(cv,doc):
    cv.setStrokeColor(ACCENT);cv.setLineWidth(.7);cv.line(48,752,564,752)
    cv.setFillColor(MUTED);cv.setFont('Sans',8);cv.drawString(48,763,'THOMAS OU | INTEL | PITCH DEFENSE')
    cv.line(48,39,564,39);cv.drawString(48,25,'Private preparation - separate from the Initial Screen');cv.drawRightString(564,25,f'{doc.page} / 5')
doc=SimpleDocTemplate(str(notes_path),pagesize=(612,792),leftMargin=48,rightMargin=48,topMargin=59,bottomMargin=51,title='Intel | Pitch defense notes',author='Thomas Ou')
doc.build(story,onFirstPage=frame,onLaterPages=frame)
nr=PdfReader(notes_path);assert len(nr.pages)==5,len(nr.pages)
nt='\n\n'.join(p.extract_text() for p in nr.pages)
for key in ['$77.46','$51.07','$45.47','$30.23','$48.38','$58.83','November 9, 2026','92.3%','No matched workload was run']:
    assert key in ' '.join(nt.split()),key
(folder/'defense_extracted.txt').write_text(nt)
notes_manifest={'path':str(notes_path),'sha256':hashlib.sha256(notes_path.read_bytes()).hexdigest(),'pages':5,'submitted':False,'visual_qa':'pending','purpose':'Private pitch preparation and supporting calculations; excluded from the ten-page screen.'}
(folder/'defense_manifest.json').write_text(json.dumps(notes_manifest,indent=2)+'\n')
print(json.dumps(notes_manifest,indent=2))

comparison_path=ROOT/'output/pdf/m37_intel_pitch_comparison.pdf'
wms_url='https://www.kenan-flagler.unc.edu/wp-content/uploads/2024/12/First-Place-Equity_Team1_Universe_WMS.pdf'
jbi_url='https://www.kenan-flagler.unc.edu/wp-content/uploads/2023/12/Equity-1st-place_Columbia-_JBI.pdf'
cargo_url='https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-2024-winning-presentation-university-of-waterloo.pdf'
midd_url='https://www.kenan-flagler.unc.edu/wp-content/uploads/2025/12/Equity_Team10_Universe_MIDD.pdf'
light_url='https://www.cfainstitute.org/sites/default/files/docs/insights/events/research-challenge/rc-2026-winning-presentation-university-of-waterloo_0.pdf'
gtx_url='https://investmentclub.nd.edu/files/competitions/2023-cornell-gtx-deck.pdf'
comparison=[np('Your Intel pitch versus the public winners','title'),np('Comparative review | November 6, 2026 | Assessment of the revised 10-page screen','subtitle'),
np('<b>The research is defensible and the presentation gap is much smaller. The investment edge at $52.25 is still not established.</b> The strongest examples connect a specific disagreement to earnings, cash and a price advantage. Your revised pitch now explains the first two clearly. Its own valuation still describes a roughly fair entry with a conditional 10% annual return.'),
notes_table(['Area','What the strong examples do','Your revised pitch'],[
['Business mechanism','WMS links material conversion to sales and mix; Cargojet links aircraft capacity to utilization and cash.','Clearer: CPU units x ASP, PC profit drag, factory recovery, then funded owner cash.'],
['Forecast disagreement','WMS shows dated team versus consensus forecasts and the specific drivers behind the difference.','Improved: current $69.27B total-sales proxy versus $68.33B own Products. Only $0.94B remains for other external sales; full consolidation is still approximate.'],
['Operating evidence','Customer economics, production constraints and adoption timing feed the forecast.','Improved: quantified Ireland ramp, signed agreements and 3-5-year pricing terms. Accepted units and renewal margins remain unobserved.'],
['Valuation and entry','A good business still needs a return that compensates for its risks at the purchase price.','Largest gap: $51.07 December 2026 planning value versus $52.25 entry. $77.46 in 2030 includes time and cash accumulation.'],
['Risks and failure tests','The better examples state what would invalidate the view; some winners are much less rigorous here.','Strong: timing versus lasting damage, funded lower-demand cases, margin and growth tests, no invented probabilities.'],
['Communication','WMS completes its main argument in nine pages; large appendices are optional support.','Comparable structure: ten readable pages, claim-led headings, few core exhibits and separate defense notes.']
],[95,207,214]),Spacer(1,11),
np('What the comparison does not show','question'),
np('It does not establish a winning probability or a 9/10 investment thesis. Published winners are a selected sample, from different competitions and horizons. Attractive formatting, interview counts and many valuation methods are not independent evidence that the stock is mispriced. M37 publishes no minimum upside requirement or numeric judging rubric.','small'),
np('Standards checked against '+link('M37 rules','https://www.m37.com/spc2026')+'. Award status checked through '+link('UNC official archives','https://www.kenan-flagler.unc.edu/alpha-challenge-2/archives/')+' and '+link('CFA past champions','https://www.cfainstitute.org/insights/events/research-challenge/past-champions')+'. These are quality comparisons, not a model of competition outcomes.','small')]
comparison += [PageBreak(),np('What to borrow from each example','title'),np('PDF page references below are one-based. Main narratives and relevant valuation/method appendices were reviewed.','subtitle'),
qa('WMS | UNC 2024 first place | closest format match',
'The main argument fits nine pages. Forecast FY26 EPS is $7.33 versus $6.73 consensus, an 8.9% difference tied to conversion and margin mix. Its $172 forward target also assumes favorable multiples; the appendix DCF gives $153.30 current value. The values have different dates. Borrow the evidence-to-forecast bridge; higher-multiple peers do not guarantee rerating. '+link('Deck: pp. 3-8, 41-49',wms_url)+'.'),
qa('JBI | Columbia 2023 first place | explain why the stock is overlooked',
'It distinguishes renovation exposure from new construction and connects ownership overhang to a possible valuation discount. The narrative shows how an investor could misclassify the business. Intel\'s pitch explains recovery better than it explains a current investor mistake. The JBI forecasts later missed materially; winning and subsequent investment accuracy are different outcomes. '+link('Deck: pp. 2-10',jbi_url)+'; '+link('later actual results','https://ir.janusintl.com/financial-information/sec-filings/content/0001839839-25-000032/jbi-20241228.htm')+'.'),
qa('Cargojet | Waterloo 2024 global winner | physical capacity to cash',
'Fleet, utilization, route economics and capital spending connect the operating thesis to free cash. Its valuation distinguishes current DCF estimates from one-year target values. The useful Intel analogue is qualified capacity and accepted deliveries, not copying airline margins or the number of appendix slides. '+link('Presentation: main narrative and valuation appendix',cargo_url)+'.'),
qa('MIDD and Lightspeed | verified winners | research must change a driver',
'Middleby makes market belief, variant belief and financial consequence explicit. Lightspeed tests location growth using sales productivity and payment economics. Neither large research counts nor an expert quotation alone establishes a forecast. For Intel, a workload benchmark must connect to customer allocation and retained supplier profit before it deserves valuation credit. '+link('MIDD',midd_url)+'; '+link('Lightspeed',light_url)+'.'),
qa('Garrett Motion | Notre Dame 2023 Cornell winner | customer persistence',
'Long development cycles and awarded programs help explain a durable franchise, though OEM orders are not guaranteed minimum purchases. The award-linked deck uses $7.61 and $12.18, not the later club version\'s $7.59 and $12.09. Its current-DCF versus 4-5-year-target framing is ambiguous. Intel should preserve its explicit valuation dates. '+link('Exact competition archive deck: pp. 2, 4-5, 25, 31',gtx_url)+'.'),
np('Large upside is not a prerequisite. CFA\'s archived 2015 '+link('Canisius winning presentation','https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-2015-winning-presentation-canisius-college.pdf')+' ends with HOLD and 2.2% price upside; its 2016 '+link('Waterloo winner','https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-2016-winning-presentation-university-of-waterloo.pdf')+' recommends BUY with 14.8% one-year total return. Different eras and risks prevent a direct return comparison. M37 still requires LONG or SHORT.','small'),
np('Same-event control: another 2024 WMS team also had interviews, site research, scenarios and polished slides but is not listed among the top three. Its exact rank is unknown. These features alone are not a recipe for winning.','small')]
comparison += [PageBreak(),np('What changed, and what is still unresolved','title'),np('November 6 evidence update | Operating forecast and $77.46 target unchanged; reference close corrected to $52.25.','subtitle'),
qa('1. The profit story is now explicit.',
'The screen shows why servers can outweigh PC weakness: +$5.09B DCAI profit versus -$1.38B CCPG in 2027. CPU sales must rise 20.6% above modeled Q4 annualized. If H1 holds that pace, H2 must average $9.21B per quarter, 41% higher; this is a revenue hurdle, not a unit forecast. DCAI and Foundry drive 89% of the 2027-28 EBIT increase.'),
qa('2. Supply announcements no longer stand in for deliveries.',
'The CFO\'s August target to more than double Ireland output in 2027 gives the ramp a physical basis. It is not a qualified-package count. Oregon output and much substrate capacity arrive in H2. With flat H1, the revenue target needs H2 units +41% at flat sequential ASP, or +28% at ASP +10%. Each result now triggers a remaining-sales calculation; preserving the next year\'s volume requires catch-up evidence.'),
qa('3. The contract evidence supports a limited period.',
'Original Q1 remarks confirm signed DCAI agreements. Published CFO transcripts describe 3-5-year volume/pricing terms and later like-for-like ASP/core stabilization. A 2026 start implies roughly 2029-31 expiry. Coverage, cancellations, input costs and renewals remain unknown. This supports the ramp without establishing 40% mature margin. Customer switching evidence remains in the defense notes.'),
qa('4. The valuation reveals its duration.',
'92.3% of December 2026 operating value comes from cash after 2030. The screen now shows early margin erosion ($68.14), 10% unit growth in 2028-30 ($66.13), slower post-2030 CPU growth ($69.63), a Foundry delay ($75.76), persistent demand weakness and joint downside. These are conditional states, not probabilities or loss bounds.'),
qa('5. The forecast disagreement is now current and measurable.',
'The November 5 S&P total-revenue proxy leaves only $0.94B beyond our Products estimate. That is a concrete optimism check, not a claimed consensus DCAI estimate: All Other eliminations and legacy external Foundry still need reconciliation. Oracle billing and TPC-H comparisons remain public-data calculations, not interviews or proof of Intel net pricing.'),
np('The unresolved decision','question'),
np('At the reference price, a 10% base-case return is possible. It is not a probability-weighted expectation, and the model shows little initial margin of safety. A 12% base-case return needs about $48.38; 15% needs $43.35. Those entry thresholds depend on the same uncertain target. Better evidence of sustained economics or an incremental, funded program could improve the case; more confident wording cannot.'),
np('<b>Assessment:</b> a credible, transparent moderate-conviction LONG screen, materially stronger as a research argument. It is not yet a demonstrated superior risk-adjusted opportunity at $52.25. The strongest remaining weakness is stock selection at the entry price, not document polish.','small')]

def comparison_frame(cv,doc):
    cv.setStrokeColor(ACCENT);cv.setLineWidth(.7);cv.line(48,752,564,752)
    cv.setFillColor(MUTED);cv.setFont('Sans',8);cv.drawString(48,763,'THOMAS OU | INTEL | COMPARATIVE REVIEW')
    cv.line(48,39,564,39);cv.drawString(48,25,'Research assessment - not part of the competition submission');cv.drawRightString(564,25,f'{doc.page} / 3')
comparison_doc=SimpleDocTemplate(str(comparison_path),pagesize=(612,792),leftMargin=48,rightMargin=48,topMargin=59,bottomMargin=51,title='Intel | Comparison with public investment pitches',author='Thomas Ou')
comparison_doc.build(comparison,onFirstPage=comparison_frame,onLaterPages=comparison_frame)
cr=PdfReader(comparison_path);assert len(cr.pages)==3,len(cr.pages)
ct='\n\n'.join(p.extract_text() for p in cr.pages)
(folder/'comparison_extracted.txt').write_text(ct)
comparison_manifest={'path':str(comparison_path),'sha256':hashlib.sha256(comparison_path.read_bytes()).hexdigest(),'pages':3,'visual_qa':'pending','submitted':False,'scope':'Comparison and research assessment, separate from the ten-page screen.'}
(folder/'comparison_manifest.json').write_text(json.dumps(comparison_manifest,indent=2)+'\n')
print(json.dumps(comparison_manifest,indent=2))
