import fs from 'node:fs/promises';
import path from 'node:path';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const root = '/Users/thomasou/Documents/Codex/2026-11-02/lo';
const research = path.join(root, 'work/three_hour/active_research');
const run = path.join(research, 'intel_two_hour_completion_2026_11_06');
const revision = path.join(research, 'intel_market_share_thesis_2026_11_06');
const out = path.join(root, 'outputs/01a19d70-cbad-7e23-b996-11dc618014aa');
const rebuild = path.join(research, 'intel_fundamental_rebuild_2026_11_06');
const temp = path.join(rebuild, 'factory/workbook');
const resolution = temp;
await fs.mkdir(temp, {recursive:true});
const read = async p => JSON.parse(await fs.readFile(p, 'utf8'));
const cash = await read(path.join(run, 'root/quarterly_cash_results.json'));
const selected = await read(path.join(run, 'quarterly/selected_quarterly_forecast.json'));
const host = (await read(path.join(research, 'pricing_and_competition_review_2026_11_04/intel_server_ASP_mix_operating_policy.json'))).annual_rows;
const raw = (await read(path.join(research, 'pricing_and_competition_review_2026_11_04/intel_ASP20_mature_margin35_valuation.json'))).annual_operating_rows;
const pack = (await read(path.join(research, 'intel_competition_screen_2026_11_04/external_packaging_operating_policy_2026_11_04.json'))).annual_rows;
const preferred = await read(path.join(revision, 'root/active_case.json'));
const reverse = await read(path.join(rebuild, 'valuation/valuation_rebuild_results.json'));
const packagingControls = await read(path.join(rebuild, 'factory/packaging_margin_controls.json'));
const years = Array.from({length:15}, (_,i)=>2027+i);
const qrows = cash.base.quarterly_rows;
const wb = Workbook.create();
const names = ['Valuation','Assumptions','Annual model','Quarterly model','Sources','Checks','Research checks'];
const sheets = Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
const ink='#16283E', teal='#146F67', pale='#EFF3F7', blue='#245FC0', green='#228047', gray='#5E6C7B';
const num='#,##0.00;(#,##0.00);"-"', money='$0.00;($0.00);"-"', pct='0.0%;(0.0%);"-"';
const col = n => {let s='';for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const cell=(s,a,v)=>{s.getRange(a).values=[[v]];};
const formula=(s,a,f,output=false)=>{s.getRange(a).formulas=[[f]];s.getRange(a).format.font.color=output?ink:(f.includes('!')?green:'#111111');};
const values=(s,r,arr,start=6)=>{const g=s.getRange(`${col(start)}${r}:${col(start+arr.length-1)}${r}`);g.values=[arr];g.format.font.color=blue;};
const formulas=(s,r,arr,start=6)=>{const g=s.getRange(`${col(start)}${r}:${col(start+arr.length-1)}${r}`);g.formulas=[arr];for(let j=0;j<arr.length;j++)s.getRange(`${col(start+j)}${r}`).format.font.color=arr[j].includes('!')?green:'#111111';};
const label=(s,r,t)=>cell(s,`C${r}`,t);
const band=(s,r,t,last='T')=>{label(s,r,t);s.getRange(`C${r}:${last}${r}`).format={fill:ink,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'}};};
const total=(s,r,last='T')=>{s.getRange(`C${r}:${last}${r}`).format.fill=pale;s.getRange(`C${r}:${last}${r}`).format.font.bold=true;s.getRange(`F${r}:${last}${r}`).format.borders={top:{style:'thin',color:'#CFD7E0'}};};
const percent=(s,r,last='T')=>{s.getRange(`F${r}:${last}${r}`).setNumberFormat(pct);s.getRange(`C${r}:${last}${r}`).format.font.italic=true;};
for(const [name,s] of Object.entries(sheets)){
  s.showGridLines=false;s.tabColor=name==='Valuation'?teal:name==='Assumptions'?'#3C7BAA':name==='Checks'?'#7B8794':ink;
  s.getRange('A1:W135').format={font:{name:'Arial',size:10,color:ink},rowHeight:20};
  s.getRange('A:B').format.columnWidth=2;s.getRange('C:C').format.columnWidth=46;
  s.getRange('D:E').format.columnWidth=2;s.getRange('F:U').format.columnWidth=13;
  s.getRange('F5:U110').setNumberFormat(num);
  s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(5);
  cell(s,'C2',`INTEL | ${name}`);s.getRange('C2').format.font={name:'Arial',size:16,bold:true,color:ink};
  cell(s,'C3','06 Nov 2026 | $ billions unless stated | core forecast; conditional LONG at $40 or below');
  s.getRange('C3').format.font.color=gray;
}

const A=sheets.Assumptions, S=sheets.Sources, Y=sheets['Annual model'], Q=sheets['Quarterly model'], V=sheets.Valuation, K=sheets.Checks;
A.getRange('D:D').format.columnWidth=17;
const globals=[
 ['Reference price ($)',56.28],['Reference date',new Date('2026-11-06T12:00:00Z')],['Target date',new Date('2030-12-31T12:00:00Z')],
 ['Holding period (years)',null],['Operating discount rate',.10625],['Terminal growth',.03],['Planning share claims (billions)',5.51],
 ['Net other assets after claims',4.502],['Opening 2027 economic cash',null],['Opening 2027 ordinary debt',50.134],['Mature CPU operating margin',null],
 ['Mature Other DCAI operating margin',.20],['Mature CCPG operating margin',.28],['CPU / client sales to group profit',.50],['Near-term Other DCAI margin',.20],
 ['Working capital / sales change',.10],['Sales / net operating investment',.80],['Financing-shield tail growth',0],['Owned minimum cash buffer',20],
 ['Q4:26 CPU sales estimate',6.81206],['Q4:26 client sales estimate',5.19963],['2026 Other DCAI sales estimate',5.05],['2026 Other CCPG sales estimate',4.598],['2026 Products sales estimate',null],
];
globals.forEach(([l,v],i)=>{label(A,5+i,l);if(v!==null){cell(A,`D${5+i}`,v);A.getRange(`D${5+i}`).format.font.color=blue;}});
formula(A,'D8','=(D7-D6)/365.25');
formula(A,'D15',"=(SUM('Sources'!G8:H8)-D19*SUM('Sources'!G7:H7))/(SUM('Sources'!G6:H6)-SUM('Sources'!G7:H7))");
formula(A,'D28',"='Sources'!F59+D24-'Sources'!F55+D25-'Sources'!F56+D26-'Sources'!F57+D27-'Sources'!F58");
formula(A,'D13',"='Sources'!F60+(D28-'Sources'!F59)*(D18*(1-'Sources'!F61)-D20)");
A.getRange('D6:D7').setNumberFormat('dd-mmm-yy');A.getRange('D5:D28').setNumberFormat(num);A.getRange('D6:D7').setNumberFormat('dd-mmm-yy');
for(const r of [9,10,15,16,17,18,19,20,22])A.getRange(`D${r}`).setNumberFormat(pct);
cell(A,'F6','Blue: editable input   Black: calculation   Green: linked input');
cell(A,'F8','Mature CPU margin uses pooled Q2/Q3 profit and an assumed 20% Other margin.');
cell(A,'F10','No physical shipment counts or contract-level margins are disclosed.');
cell(A,'F12','The 20B cash floor is an analyst buffer, not a covenant.');
cell(A,'F14','Changing the dated forecasts changes value; it does not prove those forecasts.');
cell(A,'F16','Annual CPU unit/ASP inputs start in 2028. Post-2030 growth fades gradually.');
cell(A,'F18','Economic cash includes selected short-term investments; access is not verified daily.');
cell(A,'F20','Finite credits, acquisition payments, leases, NCI and central SBC are included once.');
cell(A,'F22','Model scope: operating cash and equity valuation, not full GAAP statements.');
cell(A,'F24','Owned case was previously favorable. Selection followed research with all values known.');
cell(A,'F26','2028-30 quarterly CPU timing allocates annual totals; it is not sourced cadence.');
cell(A,'F28','10.625% uses trailing-cash ERP. The 11.555% method remains a valid sensitivity.');
A.getRange('D9').setNumberFormat('0.000%');
label(A,30,'Investment judgment');cell(A,'D30','Conditional LONG at $40 or below');A.getRange('D30').format.font.color=blue;
band(A,34,'Annual operating and financing inputs');values(A,36,years);A.getRange('F36:T36').format={fill:ink,font:{color:'#FFFFFF',bold:true}};A.getRange('F36:T36').setNumberFormat('0');
const annualLabels={37:'Other DCAI revenue growth',38:'Other CCPG revenue growth',39:'CPU unit growth after 2030',40:'CPU ASP growth after 2030',41:'Client unit growth after 2030',42:'Client ASP growth after 2030',43:'All Other gross external + internal sales',44:'All Other internal-sales elimination',45:'Legacy external Foundry sales',46:'Gross new packaging sales',47:'Packaging already in Foundry economics',48:'Net new packaging operating profit',49:'Net new packaging D&A',50:'Net new packaging physical capex',51:'Net new packaging working capital use',52:'Net new packaging net investment',53:'Physical capex budget, 2027-30',54:'D&A budget, 2027-30',55:'Working capital reference budget',56:'D&A / Products sales after 2030',57:'Foundry operating profit, 2027-30',58:'All Other profit less corporate costs',59:'Operating cash tax rate',60:'Old capital-credit collections',61:'New capital-credit collections',62:'Credit tax-basis loss cost',63:'Lease cash allowance',64:'Minority-owner cash allowance',65:'Financing tax benefit',66:'Ordinary cash interest, 2027-30',67:'Capitalized cash interest, 2027-30',68:'Cash interest income, 2027-30',69:'Government escrow receipts',70:'Classiq acquisition payments',71:'Scheduled debt principal',72:'Prior CPU sales reference',73:'Prior Other DCAI sales reference',74:'Prior client sales reference',75:'Prior CCPG sales reference',76:'Prior DCAI profit reference',77:'Prior CCPG profit reference',78:'Prior Products sales reference'};
Object.entries(annualLabels).forEach(([r,l])=>label(A,+r,l));
label(A,39,'CPU annual unit growth, 2028 onward');label(A,40,'CPU annual ASP growth, 2028 onward');
const mapInputs={};for(let r=37;r<=78;r++)mapInputs[r]=[];
for(let i=0;i<15;i++){
 const y=years[i],h=host[i],p=pack[i],r=raw[i],m=preferred.annual_rows[y],f=preferred.treasury[y];
 const fields={37:y<=2030?[.6,.3,.2,.15][i]:h.Other_DCAI_growth,38:h.Other_CCPG_growth,39:y<=2030?null:y===2041?.01:.02,40:y<=2030?null:y===2041?1.03/1.01-1:.02,41:y<=2030?null:h.client_unit_growth,42:y<=2030?null:h.client_ASP_growth,43:m.All_Other_gross_B,44:m.All_Other_internal_B,45:m.legacy_external_Foundry_B,46:p.gross_external_packaging_revenue_B,47:p.existing_embedded_packaging_revenue_allowance_B,48:p.net_incremental_operating_profit_B,49:p.incremental_DA_B,50:p.incremental_physical_cash_capex_B,51:p.incremental_WC_cash_use_B,52:p.incremental_net_operating_investment_B,53:y<=2030?r.physical_cash_capex_B:null,54:y<=2030?r.DA_B:null,55:y<=2030?r.WC_cash_use_B:null,56:h.DA_fraction_of_Products_revenue,57:y<=2030?h.Foundry_operating_profit_B:null,58:m.Other_profit_less_corporate_B,59:r.tax_rate,60:r.old_credit_collection_B,61:r.new_credit_collection_B,62:r.credit_basis_loss_tax_B,63:r.lease_cash_B,64:r.minority_cash_B,65:m.financing_shield_B,66:f?.ordinary_interest_B??null,67:f?.capitalized_interest_B??null,68:f?.cash_income_B??null,69:f?.escrow_cash_B??null,70:f?.Classiq_cash_B??null,71:f?.principal_B??null,72:h.server_CPU_revenue_proxy_B,73:h.Other_DCAI_revenue_B,74:h.client_revenue_B,75:h.CCPG_revenue_B,76:h.DCAI_operating_profit_B,77:h.CCPG_operating_profit_B,78:h.Products_revenue_B};
 for(const [r,v] of Object.entries(fields))mapInputs[r].push(v);
}
for(const [r,vals] of Object.entries(mapInputs))values(A,+r,vals);
values(A,39,years.map((y,i)=>y===2027?null:y<=2030?[.25,.18,.12][i-1]:host[i].server_unit_growth));
values(A,40,years.map((y,i)=>y===2027?null:y<=2030?[.08,.04,.02][i-1]:host[i].server_ASP_growth));
for(let i=0;i<4;i++){
 const c=col(i+6);
 cell(A,`${c}53`,raw[i].physical_cash_capex_B-pack[i].incremental_physical_cash_capex_B);
 cell(A,`${c}54`,raw[i].DA_B-pack[i].incremental_DA_B);
 cell(A,`${c}55`,raw[i].WC_cash_use_B-pack[i].incremental_WC_cash_use_B);
}
label(A,53,'Host physical capex budget, 2027-30');label(A,54,'Host D&A budget, 2027-30');label(A,55,'Host working capital reference budget');
for(const r of [37,38,39,40,41,42,56,59])percent(A,r);
cell(A,'C80','2027-30 budgets are finite. Forecast misses do not refund capex or depreciation.');
cell(A,'C81','Reference forecasts calibrate retained costs; they are analyst inputs, not reported actuals.');
band(A,84,'Quarterly drivers and cash timing', 'U');
values(A,86,qrows.map(r=>`Q${r.quarter}:${String(r.year).slice(-2)}`));A.getRange('F86:U86').format={fill:ink,font:{color:'#FFFFFF',bold:true}};
const qLabels={87:'CPU units: change from prior quarter',88:'CPU ASP: change from prior quarter',89:'Client units: change from prior quarter',90:'Client ASP: change from prior quarter',91:'Other DCAI share of annual sales',92:'Packaging share of annual sales / profit',93:'Physical capex share of annual budget',94:'Working capital share of annual use',95:'Credit cash share of annual receipts',97:'Ordinary cash interest',98:'Capitalized cash interest',99:'Cash interest income',100:'Government escrow receipts',101:'Classiq acquisition payments',102:'Scheduled principal repayment'};
Object.entries(qLabels).forEach(([r,l])=>label(A,+r,l));
for(const r of [87,88,89,90,91,92,93,94,95,97,98,99,100,101,102]){
 const vals=qrows.map((q,i)=>{const k=i%4;return ({87:selected.CPU_quarterly[i].unit_growth_QoQ,88:selected.CPU_quarterly[i].ASP_growth_QoQ,89:selected.client_quarterly[i].unit_growth_QoQ,90:selected.client_quarterly[i].ASP_growth_QoQ,91:[.23,.24,.26,.27][k],92:[.1,.2,.3,.4][k],93:[.3,.25,.25,.2][k],94:[.35,.3,.2,.15][k],95:.25,97:q.ordinary_interest_B,98:q.capitalized_interest_B,99:q.cash_income_B,100:q.escrow_cash_B,101:q.Classiq_cash_B,102:q.principal_B})[r];});values(A,r,vals);
 if(r<=95)percent(A,r,'U');
}
cell(A,'C105','Principal dates are sourced. Other intra-year timing is a disclosed analyst allocation.');
cell(A,'C106','Uniform credit receipts are not promised dates; the PDF includes a late-receipt stress.');
label(A,96,'CPU share of annual units, 2028-30');
values(A,96,qrows.map((q,i)=>i<4?null:[.23,.24,.26,.27][i%4]));percent(A,96,'U');
for(let i=4;i<16;i++){
 const c=col(i+6),p=col(i+5);
 formula(A,`${c}87`,`='Quarterly model'!${c}7/'Quarterly model'!${p}7-1`);
 formula(A,`${c}88`,`='Quarterly model'!${c}8/'Quarterly model'!${p}8-1`);
}
cell(A,'C104','2028-30 CPU units: 23/24/26/27% allocation. ASP is flat within each year.');
band(A,108,'Packaging economics and replacement investment');
values(A,110,years);A.getRange('F110:T110').setNumberFormat('0');
for(const [r,l] of [[111,'Program margin after direct D&A'],[112,'Central cost / incremental revenue'],[113,'Initial capex: equipment fraction'],[114,'Equipment life (years)'],[115,'Initial capex: facility fraction'],[116,'Facility life (years)'],[117,'Normalized D&A / incremental sales'],[118,'Working capital / incremental sales'],[119,'Sales / net operating investment'],[120,'Gross packaging sales growth after 2030'],[121,'Shadow packaging growth after 2030']])label(A,r,l);
for(const r of [111,112,113,114,115,116,117,118,119,120,121]){
 values(A,r,years.map((y,i)=>({111:pack[i].gross_program_operating_margin_after_direct_DA,112:.015,113:.8,114:7,115:.2,116:20,117:y<=2030?null:pack[i].incremental_DA_B/pack[i].incremental_external_packaging_revenue_B,118:.15,119:1,120:y<=2030?null:pack[i].gross_external_packaging_revenue_B/pack[i-1].gross_external_packaging_revenue_B-1,121:y<=2030?null:.03})[r]));
 if([111,112,113,115,117,118,120,121].includes(r))percent(A,r);
}
for(let i=0;i<15;i++){
 const c=col(i+6),p=col(i+5),net=`(${c}46-${c}47)`,prior=i===0?'0':`(${p}46-${p}47)`;
 if(i>3){formula(A,`${c}46`,`=${p}46*(1+${c}120)`);formula(A,`${c}47`,`=${p}47*(1+${c}121)`);}
 formula(A,`${c}48`,`=${c}46*${c}111-MAX(0,${c}47*${c}111)-${net}*${c}112`);
 formula(A,`${c}49`,i<=3?`=(${i===0?'0':`SUM($F50:${p}50)`}+${c}50/2)*(${c}113/${c}114+${c}115/${c}116)`:`=${net}*${c}117`);
 formula(A,`${c}51`,`=(${net}-${prior})*${c}118`);
 formula(A,`${c}52`,i<=3?`=${c}50-${c}49+${c}51`:`=(${net}-${prior})/${c}119`);
 if(i>3)formula(A,`${c}50`,`=${c}49+${c}52-${c}51`);
}
cell(A,'C124','Initial packaging D&A uses a half-year convention. Later D&A replaces that cohort schedule.');
for(const r of [37,38,120,121])formula(A,`T${r}`,'=$D$10');
formula(A,'T40','=(1+$D$10)/(1+T39)-1');
formula(A,'T42','=(1+$D$10)/(1+T41)-1');
for(const r of [43,44,45,58,63,64])formula(A,`T${r}`,`=S${r}*(1+$D$10)`);
cell(A,'C125','Terminal growth updates 2041 revenue, recurring costs and required investment together.');

values(Y,5,years);Y.getRange('F5:T5').format={fill:ink,font:{color:'#FFFFFF',bold:true}};Y.getRange('F5:T5').setNumberFormat('0');
const yLabels={7:'Server CPU sales',8:'Other DCAI sales',9:'DCAI sales',10:'Client CPU sales',11:'Other CCPG sales',12:'CCPG sales',13:'Products sales',14:'All Other gross segment sales',15:'Internal-sales elimination',16:'All Other external sales',17:'Legacy external Foundry sales',18:'Gross new packaging sales',19:'Consolidated external sales',20:'Net incremental packaging sales',21:'Host sales for capital calculation',23:'CPU sales change vs prior forecast',24:'Client sales change vs prior forecast',25:'Other DCAI change vs prior forecast',26:'Total Products sales change',28:'CPU operating profit allocation',29:'CPU operating margin',30:'Other DCAI operating margin',31:'Other DCAI operating profit',32:'DCAI operating profit',33:'DCAI blended margin',34:'CCPG operating profit',35:'CCPG operating margin',36:'Foundry operating profit',37:'Net new packaging operating profit',38:'All Other profit less corporate costs',39:'Group EBIT after economic SBC',40:'Group operating margin',42:'Ordinary operating cash tax',43:'After-tax operating profit',45:'Physical cash capex',46:'Depreciation and amortization',47:'Working capital cash use',48:'Net operating investment',50:'Lease cash allowance',51:'Minority-owner cash allowance',52:'Old capital-credit cash',53:'New capital-credit cash',54:'Credit tax-basis loss cost',55:'Parent unlevered cash flow',57:'Financing tax benefit',59:'Ordinary cash interest',60:'Capitalized cash interest',61:'Cash interest income',62:'After-tax cash interest income',63:'Owner cash after financing',65:'Opening economic cash',66:'Government escrow receipts',67:'Classiq acquisition payments',68:'Debt principal repayments',69:'Closing economic cash',70:'Opening ordinary debt',71:'Closing ordinary debt',73:'Host external sales growth ($B)',74:'Margin transition to 2040'};
Object.entries(yLabels).forEach(([r,l])=>label(Y,+r,l));
for(const [r,t] of [[6,'External revenue'],[27,'Operating profit'],[41,'Tax and reinvestment'],[49,'Other cash claims and credits'],[58,'Treasury, 2027-30']])band(Y,r,t);
for(const r of Object.keys(yLabels).map(Number)){
 const f=years.map((y,i)=>{const c=col(6+i),pr=col(5+i),ac=`'Assumptions'!${c}`,j=col(6+i*4),l=col(9+i*4),near=y<=2030;const a=n=>`${ac}${n}`;
 const z={
 7:near?`SUM('Quarterly model'!${j}10:${l}10)`:`${pr}7*(1+${a(39)})*(1+${a(40)})`,
 8:`${i===0?"'Assumptions'!$D$26":pr+'8'}*(1+${a(37)})`,9:`SUM(${c}7:${c}8)`,
 10:near?`SUM('Quarterly model'!${j}14:${l}14)`:`${pr}10*(1+${a(41)})*(1+${a(42)})`,
 11:`${i===0?"'Assumptions'!$D$27":pr+'11'}*(1+${a(38)})`,12:`SUM(${c}10:${c}11)`,13:`${c}9+${c}12`,
 14:a(43),15:`-${a(44)}`,16:`SUM(${c}14:${c}15)`,17:a(45),18:a(46),19:`${c}13+${c}16+${c}17+${c}18`,20:`${c}18-${a(47)}`,21:`${c}19-${c}20`,
 23:near?`${c}7-${a(72)}`:'0',24:near?`${c}10-${a(74)}`:'0',25:near?`${c}8-${a(73)}`:'0',26:`SUM(${c}23:${c}25)`,
 28:near?`${a(76)}-'Assumptions'!$D$19*${a(73)}+'Assumptions'!$D$18*${c}23`:`${c}29*${c}7`,
 29:near?`${c}28/${c}7`:`$I$29+${c}74*('Assumptions'!$D$15-$I$29)`,
 30:near?"'Assumptions'!$D$19":`'Assumptions'!$D$19+${c}74*('Assumptions'!$D$16-'Assumptions'!$D$19)`,
 31:`${c}8*${c}30`,32:`${c}28+${c}31`,33:`${c}32/${c}9`,
 34:near?`${a(77)}+'Assumptions'!$D$18*${c}24`:`${c}35*${c}12`,
 35:near?`${c}34/${c}12`:`$I$35+${c}74*('Assumptions'!$D$17-$I$35)`,
 36:near?a(57):`$I$36/$I$13*${c}13`,37:a(48),38:a(58),39:`${c}32+SUM(${c}34,${c}36:${c}38)`,40:`${c}39/${c}19`,
 42:`MAX(${c}39,0)*${a(59)}`,43:`${c}39-${c}42`,45:near?`${a(53)}+${a(50)}`:`${c}46+${c}48-${c}47`,46:near?`${a(54)}+${a(49)}`:`${a(56)}*${c}13+${a(49)}`,
 47:near?`${a(55)}+${a(51)}+'Assumptions'!$D$20*(${c}26-${i===0?"('Assumptions'!$D$28-'Sources'!$F$59)":pr+'26'})`:`'Assumptions'!$D$20*${c}73+${a(51)}`,
 48:near?`${c}45-${c}46+${c}47`:`${c}73/'Assumptions'!$D$21+${a(52)}`,
 50:a(63),51:a(64),52:a(60),53:a(61),54:a(62),55:`${c}43-${c}48-${c}50-${c}51+${c}52+${c}53-${c}54`,57:a(65),
 59:near?a(66):'0',60:near?a(67):'0',61:near?a(68):'0',62:near?`${c}61*(1-${a(59)})`:'0',63:near?`${c}55-${c}59-${c}60+${c}62+${c}57`:'0',
 65:near?(i===0?"'Assumptions'!$D$13":`${pr}69`):'0',66:near?a(69):'0',67:near?a(70):'0',68:near?a(71):'0',69:near?`${c}65+${c}63+${c}66-${c}67-${c}68`:'0',70:near?(i===0?"'Assumptions'!$D$14":`${pr}71`):'0',71:near?`${c}70-${c}68`:'0',
 73:y>2030?`${c}21-${pr}21`:'0',74:`MIN(MAX((${c}$5-2030)/10,0),1)`};return '='+z[r];});formulas(Y,r,f);
}
for(const r of [9,12,13,19,32,39,43,48,55,63,69,71])total(Y,r);
for(const r of [29,30,33,35,40,74])percent(Y,r);
cell(Y,'C77','Quarterly receipts and costs reconcile to these annual amounts; timing remains assumed.');
cell(Y,'C78','Foundry dollars after 2030 scale with Products sales at the 2030 ratio; not a Foundry margin.');
cell(Y,'C79','Blank / dash treasury periods after 2030 are outside the cash-balance forecast.');

values(Q,5,qrows.map(r=>`Q${r.quarter}:${String(r.year).slice(-2)}`));Q.getRange('F5:U5').format={fill:ink,font:{color:'#FFFFFF',bold:true}};
const qNames={7:'CPU unit index (Q4:26 = 100)',8:'CPU ASP index (Q4:26 = 100)',10:'CPU sales',12:'Client unit index (Q4:26 = 100)',13:'Client ASP index (Q4:26 = 100)',14:'Client sales',16:'Other DCAI sales',17:'DCAI sales',18:'Other CCPG sales',19:'CCPG sales',20:'Products sales',21:'All Other external sales',22:'Legacy external Foundry sales',23:'Gross new packaging sales',24:'Consolidated external sales',26:'CPU operating profit allocation',27:'Other DCAI operating profit',28:'DCAI operating profit',29:'CCPG operating profit',30:'Foundry operating profit',31:'Net new packaging operating profit',32:'All Other profit less corporate costs',33:'Group EBIT after economic SBC',34:'Ordinary operating tax allocation',35:'Positive EBIT for tax allocation',37:'Physical cash capex',38:'Depreciation and amortization',39:'Working capital cash use',40:'Net operating investment',42:'Lease cash allowance',43:'Minority-owner cash allowance',44:'Old capital-credit receipts',45:'New capital-credit receipts',46:'Credit tax-basis loss cost',47:'Parent unlevered cash flow',49:'Ordinary cash interest',50:'Capitalized cash interest',51:'Cash interest income',52:'After-tax cash interest income',53:'Financing tax benefit',54:'Owner cash after financing',56:'Opening economic cash',57:'Government escrow receipts',58:'Classiq acquisition payments',59:'Debt principal repayments',60:'Closing economic cash',61:'Opening ordinary debt',62:'Closing ordinary debt'};
Object.entries(qNames).forEach(([r,l])=>label(Q,+r,l));
for(const [r,t] of [[6,'Units, ASP and external revenue'],[25,'Profit timing'],[36,'Cash investment'],[41,'Other cash claims and credits'],[48,'Financing cash'],[55,'Cash and debt balances']])band(Q,r,t,'U');
for(const r of Object.keys(qNames).map(Number)){
 const f=qrows.map((q,i)=>{const c=col(i+6),pr=col(i+5),yc=col(6+Math.floor(i/4)),first=col(6+4*Math.floor(i/4)),last=col(9+4*Math.floor(i/4));const a=n=>`'Assumptions'!${c}${n}`,y=n=>`'Annual model'!${yc}${n}`;
 const z={7:`${i===0?'100':pr+'7'}*(1+${a(87)})`,8:`${i===0?'100':pr+'8'}*(1+${a(88)})`,10:`'Assumptions'!$D$24*${c}7/100*${c}8/100`,12:`${i===0?'100':pr+'12'}*(1+${a(89)})`,13:`${i===0?'100':pr+'13'}*(1+${a(90)})`,14:`'Assumptions'!$D$25*${c}12/100*${c}13/100`,16:`${y(8)}*${a(91)}`,17:`${c}10+${c}16`,18:`${y(11)}/4`,19:`${c}14+${c}18`,20:`${c}17+${c}19`,21:`${y(16)}/4`,22:`${y(17)}/4`,23:`${y(18)}*${a(92)}`,24:`SUM(${c}20:${c}23)`,
 26:`'Assumptions'!$D$18*${c}10-('Assumptions'!$D$18*${y(7)}-${y(28)})/4`,27:`'Assumptions'!$D$19*${c}16`,28:`SUM(${c}26:${c}27)`,29:`'Assumptions'!$D$18*${c}19-('Assumptions'!$D$18*${y(12)}-${y(34)})/4`,30:`${y(36)}/4`,31:`${y(37)}*${a(92)}`,32:`${y(38)}/4`,33:`SUM(${c}28:${c}32)`,34:`IF(SUM(${first}35:${last}35)=0,0,${y(42)}*${c}35/SUM(${first}35:${last}35))`,35:`MAX(${c}33,0)`,
 37:`${y(45)}*${a(93)}`,38:`${y(46)}/4`,39:`${y(47)}*${a(94)}`,40:`${c}37-${c}38+${c}39`,42:`${y(50)}/4`,43:`${y(51)}/4`,44:`${y(52)}*${a(95)}`,45:`${y(53)}*${a(95)}`,46:`${y(54)}/4`,47:`${c}33-${c}34-${c}40-${c}42-${c}43+${c}44+${c}45-${c}46`,49:a(97),50:a(98),51:a(99),52:`${c}51*(1-'Assumptions'!${yc}59)`,53:`${y(57)}/4`,54:`${c}47-${c}49-${c}50+${c}52+${c}53`,56:i===0?"'Assumptions'!$D$13":`${pr}60`,57:a(100),58:a(101),59:a(102),60:`${c}56+${c}54+${c}57-${c}58-${c}59`,61:i===0?"'Assumptions'!$D$14":`${pr}62`,62:`${c}61-${c}59`};return '='+z[r];});formulas(Q,r,f);
}
for(const r of [10,14,17,19,24,28,33,40,47,54,60,62])total(Q,r,'U');
for(let i=4;i<16;i++){
 const c=col(i+6),yc=col(6+Math.floor(i/4)),pfirst=col(2+4*Math.floor(i/4)),plast=col(5+4*Math.floor(i/4));
 formula(Q,`${c}7`,`=SUM(${pfirst}7:${plast}7)*(1+'Assumptions'!${yc}39)*'Assumptions'!${c}96`);
 formula(Q,`${c}8`,`=SUMPRODUCT(${pfirst}7:${plast}7,${pfirst}8:${plast}8)/SUM(${pfirst}7:${plast}7)*(1+'Assumptions'!${yc}40)`);
}
cell(Q,'C65','Indices describe the chosen mix and quantity path; they are not observed chip counts.');
cell(Q,'C66','Quarterly profit uses contribution less allocated annual retained costs.');
cell(Q,'C67','Debt principal dates are sourced; capex, tax, grant and escrow timing are assumptions.');
cell(Q,'C68','2028-30 CPU quarterly units allocate annual totals; annual weighted ASP grows once.');

S.getRange('F5:I5').values=[['Q1:26','Q2:26','Q3:26','9M:26']];S.getRange('F5:I5').format={fill:ink,font:{color:'#FFFFFF',bold:true}};
label(S,6,'Reported DCAI sales');values(S,6,[5.052,6.262,7.318,18.632]);label(S,7,'Other DCAI sales (rounded scope)');values(S,7,[.935,.951,1.4,3.3]);label(S,8,'Reported DCAI operating profit');values(S,8,[1.542,2.474,3.039,7.055]);
label(S,10,'2027 S&P revenue forecast proxy');cell(S,'F10',69.27);S.getRange('F10').format.font.color=blue;
cell(S,'K6','Source: Intel Q1 / Q2 / Q3 filings; segment disclosures');
cell(S,'K7','Rounded Other categories do not add exactly. No exact units are inferred.');
cell(S,'K10','StockAnalysis, S&P Global feed, refreshed 05 Nov 2026');
cell(S,'C13','PUBLIC SOURCES AND INPUT CLASSIFICATION');S.getRange('C13').format.font.bold=true;
const sourceRows=[
 ['Reported actuals','Intel Q3 2026 Form 10-Q','https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000191/intc-20260926.htm'],
 ['Reported actuals','Intel Q2 2026 Form 10-Q','https://www.intc.com/filings-reports/all-sec-filings/content/0000050863-26-000157/intc-20260627.htm'],
 ['Guidance / commentary','Intel Q3 prepared remarks','https://d1io3yog0oux5.cloudfront.net/_47986fe477a6ac84fe34efbcbf38dd13/intel/db/887/9273/prepared_remarks/Q3%2726_Prepared_Remarks.pdf'],
 ['Forecast proxy','S&P company revenue; not CPU consensus','https://stockanalysis.com/stocks/intc/forecast/'],
 ['Market reference','Nov 6 regular close; $56.28','https://www.marketscreener.com/quote/stock/INTEL-CORPORATION-4829/quotes/'],
 ['Grant timing','Mobileye Q3: 2026 grant cash begins in 2028','https://ir.mobileye.com/news-releases/news-release-details/mobileye-releases-third-quarter-2026-results-updates-guidance'],
 ['Competition rules','M37: <=10-page PDF; Nov 9 deadline','https://www.m37.com/spc2026'],
 ['Planned customer offering','Oracle / Intel collaboration; no unit schedule','https://www.intel.com/content/www/us/en/newsroom/news/corporate/intel-oracle-collaborate-on-enterprise-and-agentic-ai.html'],
 ];
sourceRows.forEach((r,i)=>{cell(S,`C${15+i*3}`,r[0]);cell(S,`F${15+i*3}`,r[1]);cell(S,`F${16+i*3}`,r[2]);});
cell(S,'C41','Forecast inputs in Assumptions are owned estimates. They are not historical disclosures.');
cell(S,'C43','Legacy external Foundry: H1 2026 annualized, excluding the Q3 nonrecurring spike.');
cell(S,'C44','All Other gross sales 2.8B less 0.02B internal sales; flat through 2030, then 3%.');
cell(S,'C45','Packaging gross revenue is included once; only its net incremental profit/capital is added.');
cell(S,'C46','WC already contains receivables, including Mobileye R&D grants. No additional base charge.');
cell(S,'C48','Reference annual cost budgets come from the archived analyst model, dated 04 Nov 2026.');
cell(S,'C49','The model uses economic SBC, not a GAAP EPS forecast. Do not compare it with adjusted EPS.');
cell(S,'C51','Independent Python rebuilds matched annual and quarterly calculations before export.');
cell(S,'C52','This workbook does not provide source-verified 2030s contracts or future investment returns.');
const anchors=[['Q4:26 baseline CPU sales',6.5257],['Q4:26 baseline client sales',4.87575],['2026 baseline Other DCAI sales',5.19],['2026 baseline Other CCPG sales',4.598],['2026 baseline Products sales',57.82145],['2027 opening cash at baseline anchors',50.839],['Q4 cash tax convention',.15]];
anchors.forEach(([l,v],i)=>{label(S,55+i,l);cell(S,`F${55+i}`,v);S.getRange(`F${55+i}`).format.font.color=blue;});
cell(S,'H55','Dated analyst Q4 estimates, not reported actuals.');
cell(S,'H57','Changing Q4 anchors updates opening cash and the next year WC starting balance once.');
cell(S,'H60','Opening cash = Sep liquidity54.005 + Q4CFO4.5 - PPE8.166 - lease.25 - NCI.25 + receipts1.');
S.getRange('F61').setNumberFormat(pct);

V.getRange('D:E').format.columnWidth=17;V.freezePanes.unfreeze();
cell(V,'C5','Investment judgment');formula(V,'F5',"='Assumptions'!D30");
cell(V,'F6','No new position at the Nov 6 close. The core operating assumptions remain forecasts.');
const outputRows={8:['Reference price ($)',"='Assumptions'!D5"],9:['December 2026 planning value ($)','=D40'],10:['December 2030 target ($)','=E40'],11:['Annual price return','=((D10/D8)^(1/\'Assumptions\'!D8))-1'],12:['2027 consolidated sales',"='Annual model'!F19"],13:['2027 difference vs revenue consensus',"=D12/'Sources'!F10-1"],14:['Minimum quarterly economic cash',"=MIN('Quarterly model'!F60:U60)"],15:['Cash headroom over owned buffer',"=D14-'Assumptions'!D23"]};
for(const [r,[l,f]] of Object.entries(outputRows)){label(V,+r,l);formula(V,`D${r}`,f,true);V.getRange(`D${r}`).setNumberFormat([11,13].includes(+r)?pct:(+r<=10?money:num));}
V.getRange('C8:D15').format.rowHeight=25;V.getRange('D9:D11').format.font={name:'Arial',size:14,bold:true,color:teal};
cell(V,'F8','Entry rule: higher-rate core return at least 15%; selected joint stress at least 12%.');cell(V,'F10','No dividend or multiple rerating is credited.');cell(V,'F12','Q4 anchors and the joint growth path are owned estimates.');cell(V,'F14','31.19B is base-timing cash. Joint and funded stresses are in the PDF and research.');cell(V,'F16','Dec 2026 planning value is not Nov 6 fair value. The dates differ by 55 days.');
band(V,18,'Discounted cash flow and financial claims');values(V,20,years);V.getRange('F20:T20').setNumberFormat('0');
for(const [r,l] of [[21,'Parent unlevered cash flow'],[22,'Financing tax benefit'],[23,'Operating PV to December 2026'],[24,'Operating PV to December 2030'],[25,'Shield PV to December 2026'],[26,'Shield PV to December 2030']])label(V,r,l);
for(const r of [21,22,23,24,25,26])formulas(V,r,years.map((y,i)=>{const c=col(6+i);return '='+({21:`'Annual model'!${c}55`,22:`'Annual model'!${c}57`,23:y<=2040?`${c}21/(1+'Assumptions'!$D$9)^(${c}$20-2026)`:'0',24:y>2030&&y<=2040?`${c}21/(1+'Assumptions'!$D$9)^(${c}$20-2030)`:'0',25:y<=2040?`${c}22/(1+'Assumptions'!$D$9)^(${c}$20-2026)`:'0',26:y>2030&&y<=2040?`${c}22/(1+'Assumptions'!$D$9)^(${c}$20-2030)`:'0'})[r];}));
cell(V,'D29','Dec 2026');cell(V,'E29','Dec 2030');V.getRange('C29:E29').format={fill:ink,font:{color:'#FFFFFF',bold:true}};
const vLabels={30:'Explicit operating value',31:'Terminal operating value',32:'Financing tax-benefit value',33:'Economic cash',34:'Ordinary debt',35:'Net other assets after claims',36:'Remaining escrow receipts (PV)',37:'Remaining Classiq payments (PV)',38:'Equity value',39:'Planning share claims (billions)',40:'Value per share ($)'};
Object.entries(vLabels).forEach(([r,l])=>label(V,+r,l));
for(const [c,endpoint,pr,sh] of [['D',2026,23,25],['E',2030,24,26]]){
 const d=2040-endpoint;
 const fl={30:`SUM(F${pr}:T${pr})`,31:`T21/('Assumptions'!$D$9-'Assumptions'!$D$10)/(1+'Assumptions'!$D$9)^${d}`,32:`SUM(F${sh}:T${sh})+T22/('Assumptions'!$D$9-'Assumptions'!$D$22)/(1+'Assumptions'!$D$9)^${d}`,33:endpoint===2026?"'Assumptions'!D13":"'Annual model'!I69",34:endpoint===2026?"-'Assumptions'!D14":"-'Annual model'!I71",35:"'Assumptions'!D12",36:endpoint===2026?"'Assumptions'!F69/(1+'Assumptions'!$D$9)+'Assumptions'!G69/(1+'Assumptions'!$D$9)^2":'0',37:endpoint===2026?"-'Assumptions'!F70/(1+'Assumptions'!$D$9)-'Assumptions'!G70/(1+'Assumptions'!$D$9)^2":'0',38:`SUM(${c}30:${c}37)`,39:"'Assumptions'!D11",40:`${c}38/${c}39`};
 for(const [r,f] of Object.entries(fl)){formula(V,`${c}${r}`,'='+f,true);V.getRange(`${c}${r}`).setNumberFormat(+r===40?money:num);}
}
V.getRange('C38:E40').format.fill=pale;V.getRange('C40:E40').format.font.bold=true;
label(V,43,'Core case: 12% return ceiling ($)');formula(V,'D43',"=E40/(1+12%)^'Assumptions'!D8",true);V.getRange('D43').setNumberFormat(money);
label(V,44,'Selected joint: 12% ceiling ($)');formula(V,'D44',"=I44/(1+12%)^'Assumptions'!D8",true);V.getRange('D44').setNumberFormat(money);
cell(V,'F44','Fixed joint target ($)');cell(V,'I44',64.7378499644682);V.getRange('I44').setNumberFormat(money);V.getRange('I44').format.font.color=blue;
cell(V,'F45','Fixed joint: 11.555% rate, Foundry breakeven, 15% modeled terminal return, 8% funding.');
cell(V,'F30','Annual-end discount convention; reference quote precedes planning value by 55 days.');
cell(V,'F32','Tail begins with 2041 cash. Operating growth 3%; financing-shield growth 0%.');
cell(V,'F34','2030 cash already includes 2027-30 owner cash; those flows are not added twice.');
cell(V,'F36','1.215B added claim reserve is already deducted in net other assets.');
cell(V,'F38','5.51B claims include the stated escrow and award allowances; no second derivative charge.');
cell(V,'F43','As of Nov 6: min($41.18 higher-rate core 15%, $40.45 joint 12%) rounded down to $40.');
cell(V,'C46','The owned forecast was selected after all case values were known.');
cell(V,'C47','Case probabilities and competition-winning odds are not estimated.');
band(V,50,'Market-share diagnostics: conditional scenarios', 'M');
const diagnostics=[
 [52,'2027 industry unit growth scenario',.40],
 [53,'Intel 2026 shipment-share estimate',.50],
 [54,'Intel 2027 shipment-share forecast',.42],
 [55,'Implied Intel unit growth',null],
 [56,'2026 CPU revenue estimate ($B)',null],
 [57,'Required 2027 Intel ASP growth',null],
 [59,'2030 CPU market scenario ($B)',150],
 [60,'Required Intel revenue share',null],
 [62,'2031-40 CPU revenue CAGR',null],
 [63,'Dec 2026 value / Nov 6 quote - 1',null],
 ];
for(const [r,l,v] of diagnostics){label(V,r,l);if(v!==null){cell(V,`D${r}`,v);V.getRange(`D${r}`).format.font.color=blue;}}
formula(V,'D55','=(1+D52)*D54/D53-1',true);
formula(V,'D56',"='Sources'!I6-'Sources'!I7+'Assumptions'!D24",true);
formula(V,'D57',"='Annual model'!F7/D56/(1+D55)-1",true);
formula(V,'D60',"='Annual model'!I7/D59",true);
formula(V,'D62',"=('Annual model'!S7/'Annual model'!I7)^(1/10)-1",true);
formula(V,'D63','=D9/D8-1',true);
for(const r of [52,53,54,55,57,60,62,63])V.getRange(`D${r}`).setNumberFormat(pct);
for(const r of [56,59])V.getRange(`D${r}`).setNumberFormat(num);
cell(V,'F52','TrendForce projects >40% industry shipments; 40% is an illustrative boundary.');
cell(V,'F54','Rounded E/F shares interpreted as shipment shares from the article context.');
cell(V,'F57','Uses this case\'s FY2026 estimated CPU baseline, not reported full-year sales.');
cell(V,'F59','150B is a scenario. Intel: >200B in five years (~2031). AMD: ~220B in 2030.');
cell(V,'F60','Revenue share differs from shipment share; captive-CPU TAM treatment is not disclosed.');
cell(V,'F62','The post-2030 growth fade is an owned forecast, not management guidance.');
cell(V,'F63','Dates differ by 55 days. This comparison is not a same-date safety margin.');
cell(V,'C65','Market diagnostics test the forecast. They do not set the operating revenue inputs.');
band(S,64,'Market evidence and scenario definitions', 'M');
cell(S,'C66','Industry shipment forecast');cell(S,'F66','TrendForce, 22 Oct 2026: >40% growth in 2027; rounded E/F shares.');
cell(S,'F67','https://www.trendforce.com/presscenter/news/20261022-13279.html');
cell(S,'C69','AMD CPU-specific evidence');cell(S,'F69','Q2 2026: CPU sales >70% YoY; CPU TAM ~220B in 2030; separate from accelerators.');
cell(S,'F70','https://d1io3yog0oux5.cloudfront.net/_76e60a688092d06ccab8a780191eae46/amd/db/841/9237/webcast_transcript/AMD2Q26EarningsCallTranscript.pdf');
cell(S,'C72','Intel TAM timing');cell(S,'F72','Q3 remarks: ~40B today to >200B over five years. Not a precise 2030 forecast.');
cell(S,'C74','Share denominators');cell(S,'F74','Shipment shares include captive Arm CPUs; vendor revenue-TAM accounting is not harmonized.');
cell(S,'C76','Risk method');cell(S,'F76','10.625% = 4.94% Treasury + 1.5 asset beta x 3.79% trailing-cash implied ERP.');
cell(S,'C78','Selection chronology');cell(S,'F78','Previously favorable operations adopted on 06 Nov 2026 after all scenario values were known.');
cell(S,'C80','Conditional entry rule');cell(S,'F80','Analyst judgment after reviewing cases. Not a 20% margin, probability or all-stress floor.');
cell(S,'C82','Selected joint snapshot');cell(S,'F82','Model appendix, 06 Nov 2026: fixed operating/terminal stress plus 8% funding, zero immediate tax benefit.');

band(S,85,'Research controls captured on 06 Nov 2026', 'M');
label(S,87,'Higher operating discount rate');cell(S,'F87',.11555);S.getRange('F87').setNumberFormat('0.000%');
label(S,88,'Higher-rate core 2030 target ($)');cell(S,'F88',73.56082736404235);S.getRange('F88').setNumberFormat(money);
cell(S,'H88','Dated calculation with unchanged operations. Rebuild after forecast edits.');
cell(S,'C90','Packaging margin control');cell(S,'F90','Core target ($)');cell(S,'G90','Higher rate ($)');
S.getRange('C90:G90').format={fill:ink,font:{name:'Arial',size:10,color:'#FFFFFF',bold:true}};
const controlNames=[
 ['20% from 2030','rounded_ASE_ATM_Q3_margin20pct_control'],
 ['25% in 2030; 27% from 2032','unchanged_owned_case'],
 ['30% from 2030','Intel_attributed_aspiration30pct_control'],
];
controlNames.forEach(([name,key],i)=>{
 const row=91+i;label(S,row,name);
 cell(S,`F${row}`,packagingControls.results['0.10625'][key].Dec2030_target_USD);
 cell(S,`G${row}`,packagingControls.results['0.11555'][key].Dec2030_target_USD);
});
S.getRange('F87:F88').format.font.color=blue;S.getRange('F91:G93').format.font.color=blue;S.getRange('F91:G93').setNumberFormat(money);
cell(S,'C95','Packaging control method');cell(S,'F95','From 2030, change all program margins. Revenue, capital and 2027-29 remain fixed.');
cell(S,'F96','Embedded profit change goes to Foundry; net program change is added once. Recompute tax and cash.');
cell(S,'C98','Actual external benchmark');cell(S,'F98','ASE Q3 2026: ATM operating margin 20.0%; materials 27% of sales');
cell(S,'F99','https://www.sec.gov/Archives/edgar/data/1122411/000095010326016324/dp255760_6k.htm');
cell(S,'C100','Material-scope comparison');cell(S,'F100','Amkor Q3 2026: operating margin 11.3%; materials 50.7% of sales');
cell(S,'F101','https://www.sec.gov/Archives/edgar/data/1047127/000104712726000052/amkr-20260930.htm');
cell(S,'C102','Upper margin reference');cell(S,'F102','Intel Aug 26 conference: attributed 30% aspiration; audio not independently verified');
cell(S,'F103','https://www.intc.com/news-events/ir-calendar/detail/20260826-deutsche-banks-2026-technology-conference');
cell(S,'F104','The 30% statement is from a third-party transcript of this issuer-confirmed event.');
cell(S,'C105','Valuation method');cell(S,'F105','Damodaran: Adjusted Present Value');
cell(S,'F106','https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/apv.htm');
cell(S,'C107','Growth and capital method');cell(S,'F107','Damodaran: growth, reinvestment and consistent R&D treatment');
cell(S,'F108','https://pages.stern.nyu.edu/~adamodar/New_Home_Page/invfables/growthdeterminants.htm');
cell(S,'C109','Peer comparison limit');cell(S,'F109','Different materials, test, process IP and geography. Controls are not calibrated Intel forecasts.');

const R=sheets['Research checks'];
R.freezePanes.unfreeze();R.tabColor='#7B8794';
R.getRange('C:C').format.columnWidth=49;R.getRange('D:G').format.columnWidth=18;R.getRange('H:H').format.columnWidth=3;
R.getRange('C5:G44').format.rowHeight=22;R.getRange('D5:G44').setNumberFormat(num);
cell(R,'C2','INTEL | Research checks');cell(R,'C3','06 Nov 2026 | Dated controls; operating forecast unchanged');
band(R,5,'Cash required for the selected annual price return', 'G');
cell(R,'C7','Input / result');cell(R,'D7','Core rate');cell(R,'E7','Higher rate');
R.getRange('C7:E7').format={fill:ink,font:{name:'Arial',size:10,color:'#FFFFFF',bold:true}};
const hurdleLabels={8:'Reference price ($)',9:'Holding period (years)',10:'Annual price-return hurdle',11:'Required December 2030 price ($)',12:'Model December 2030 target ($)',13:'Operating discount rate',14:'Added cash stream annual growth',15:'Planning share claims (billions)',17:'Required price uplift ($)',18:'Extra normalized 2031 cash ($B)',19:'Core normalized 2031 cash ($B)',20:'Required 2031 cash equivalent ($B)',21:'Increase vs core normalized cash'};
Object.entries(hurdleLabels).forEach(([row,name])=>label(R,+row,name));
for(const [address,f] of Object.entries({
 D8:"='Assumptions'!D5",E8:'=D8',D9:"='Assumptions'!D8",E9:'=D9',E10:'=D10',
 D11:'=D8*(1+D10)^D9',E11:'=D11',D12:"='Valuation'!D10",E12:"='Sources'!F88",
 D13:"='Assumptions'!D9",E13:"='Sources'!F87",D14:"='Assumptions'!D10",E14:'=D14',
 D15:"='Assumptions'!D11",E15:'=D15',D17:'=D11-D12',E17:'=E11-E12',
 D18:'=D17*D15*(D13-D14)',E18:'=E17*E15*(E13-E14)',
 D19:"='Annual model'!J55-'Annual model'!J52-'Annual model'!J53+'Annual model'!J54",E19:'=D19',
 D20:'=SUM(D18:D19)',E20:'=SUM(E18:E19)',D21:'=D18/D19',E21:'=E18/E19',
}))formula(R,address,f);
cell(R,'D10',.12);R.getRange('D10').format.font.color=blue;
for(const row of [8,11,12,17])R.getRange(`D${row}:E${row}`).setNumberFormat(money);
for(const row of [10,14,21])R.getRange(`D${row}:E${row}`).setNumberFormat(pct);
R.getRange('D13:E13').setNumberFormat('0.000%');
for(const row of [11,18,20])R.getRange(`C${row}:E${row}`).format.fill=pale;
R.getRange('C18:E18').format.font.bold=true;
cell(R,'C23','The added cash starts in 2031 and grows at 3% in perpetuity. The original cash path is retained.');
cell(R,'C24','This cash equivalent is a decision threshold, not a forecast or a unique market expectation.');
cell(R,'C25','The higher-rate target is a dated control. Rebuild it after operating inputs change.');
band(R,27,'Packaging margins do not close the return gap', 'G');
R.getRange('C29:G29').values=[['Program margin from 2030','Core target ($)','Core annual','Higher target ($)','Higher annual']];
R.getRange('C29:G29').format={fill:ink,font:{name:'Arial',size:10,color:'#FFFFFF',bold:true}};
controlNames.forEach(([name],i)=>{
 const row=30+i,source=91+i;label(R,row,name);
 formula(R,`D${row}`,`='Sources'!F${source}`);formula(R,`F${row}`,`='Sources'!G${source}`);
 formula(R,`E${row}`,`=(D${row}/$D$8)^(1/$D$9)-1`);formula(R,`G${row}`,`=(F${row}/$D$8)^(1/$D$9)-1`);
});
R.getRange('D30:D32').setNumberFormat(money);R.getRange('F30:F32').setNumberFormat(money);
R.getRange('E30:E32').setNumberFormat(pct);R.getRange('G30:G32').setNumberFormat(pct);
cell(R,'C34','Targets are captured scenario results, not live margin sensitivities. Method and links: Sources rows 85-109.');
cell(R,'C35','Both embedded and incremental packaging profit change. Output and investment stay fixed.');
band(R,37,'Terminal return definition', 'G');
label(R,39,'Return on modeled net investment');formula(R,'D39',"='Assumptions'!D10*'Annual model'!T43/'Annual model'!T48");R.getRange('D39').setNumberFormat(pct);
label(R,40,'R&D treatment');cell(R,'D40','Expensed in operating margins');
cell(R,'C42','The ratio uses physical net investment and working capital. It is not R&D-capitalized economic ROC.');
cell(R,'C43','Control label: terminal return assumption equals the discount rate.');
cell(R,'C44','That convention changes modeled reinvestment. It does not establish that all economic rents disappear.');

values(K,5,[2027,2028,2029,2030]);K.getRange('F5:I5').format={fill:ink,font:{color:'#FFFFFF',bold:true}};K.getRange('F5:I5').setNumberFormat('0');
const checks=[['Sales: quarterly minus annual',24,19],['EBIT: quarterly minus annual',33,39],['Tax: quarterly minus annual',34,42],['Physical capex: quarterly minus annual',37,45],['Working capital: quarterly minus annual',39,47],['Unlevered cash: quarterly minus annual',47,55],['Owner cash: quarterly minus annual',54,63]];
checks.forEach(([l,qr,ar],j)=>{label(K,j+7,l);formulas(K,j+7,[0,1,2,3].map(i=>`=SUM('Quarterly model'!${col(6+i*4)}${qr}:${col(9+i*4)}${qr})-'Annual model'!${col(6+i)}${ar}`));});
label(K,14,'Closing cash: quarterly minus annual');label(K,15,'Closing debt: quarterly minus annual');
for(const [r,qr,yr] of [[14,60,69],[15,62,71]])formulas(K,r,[0,1,2,3].map(i=>`='Quarterly model'!${col(9+i*4)}${qr}-'Annual model'!${col(6+i)}${yr}`));
label(K,17,'Quarterly capex weights minus 100%');label(K,18,'Quarterly credit weights minus 100%');label(K,19,'Quarterly Other DCAI weights minus 100%');
for(const [r,ar] of [[17,93],[18,95],[19,91]])formulas(K,r,[0,1,2,3].map(i=>`=SUM('Assumptions'!${col(6+i*4)}${ar}:${col(9+i*4)}${ar})-1`));
label(K,20,'CPU annual allocation weights minus 100%');
formulas(K,20,[1,2,3].map(i=>`=SUM('Assumptions'!${col(6+i*4)}96:${col(9+i*4)}96)-1`),7);
K.getRange('F7:I20').setNumberFormat('0.00;(0.00);0.00');K.getRange('F7:I20').format.font.color=ink;
K.getRange('F7:I20').conditionalFormats.add('Custom',{formula:'ABS(F7)>0.0000001',format:{fill:'#FDE9E7',font:{bold:true,color:'#B42318'}}});
cell(K,'C22','These checks do not feed the valuation. Differences above 0.0000001B are flagged.');
cell(K,'C24','Quarterly sums and unit-times-ASP formulas were independently rebuilt in Python.');
cell(K,'C25','Recalculation tested for quarterly growth, annual units/ASP, margin, packaging and rate.');
cell(K,'C26','Native Microsoft Excel UI execution was not used for validation.');

wb.recalculate();
const comparisons=[];
for(let i=0;i<15;i++){
 const y=years[i],c=col(i+6),r=preferred.annual_rows[y];
 for(const [row,key] of [[7,'CPU_revenue_B'],[10,'client_revenue_B'],[19,'consolidated_revenue_B'],[32,'DCAI_profit_B'],[39,'EBIT_B'],[45,'physical_capex_B'],[46,'DA_B'],[47,'WC_cash_use_B'],[55,'parent_unlevered_cash_B']]){
  const actual=Y.getRange(`${c}${row}`).values[0][0];const err=Math.abs(actual-r[key]);comparisons.push({cell:`Annual model!${c}${row}`,actual,expected:r[key],error:err});
 }
}
for(const [addr,expected] of [['D9',preferred.values['2026'].price_USD],['D10',preferred.values['2030'].price_USD]]){
 const actual=V.getRange(addr).values[0][0];comparisons.push({cell:`Valuation!${addr}`,actual,expected,error:Math.abs(actual-expected)});
}
for(const [column,rate] of [['D',.10625],['E',.11555]]){
 const expected=reverse.reverse_operating_thresholds.find(r=>r.rate===rate&&r.annual_return_hurdle===.12);
 for(const [row,key] of [[11,'required_Dec2030_price_USD'],[18,'equivalent_extra_parent_cash2031_B_growing3pct'],[20,'equivalent_total_normalized_parent_cash2031_B']]){
  const actual=R.getRange(`${column}${row}`).values[0][0];
  comparisons.push({cell:`Research checks!${column}${row}`,actual,expected:expected[key],error:Math.abs(actual-expected[key])});
 }
}
const errors=comparisons.filter(r=>typeof r.actual!=='number'||r.error>1e-7);
await fs.writeFile(path.join(temp,'formula_reconciliation.json'),JSON.stringify({comparisons,errors},null,2));
if(errors.length)throw new Error(`Formula reconciliation failed: ${JSON.stringify(errors.slice(0,8))}`);
const basePrice=V.getRange('D10').values[0][0],sourceBefore=S.getRange('F6:I8').values;
const mutations=[];
for(const addr of ['F87','G39','G40','N39','I111','D9','D19']){
 const before=A.getRange(addr).values[0][0];A.getRange(addr).values=[[before+.01]];wb.recalculate();
 const changed=V.getRange('D10').values[0][0];
 if(Math.abs(changed-basePrice)<1e-8)throw new Error(`Input ${addr} did not affect valuation`);
 if(JSON.stringify(S.getRange('F6:I8').values)!==JSON.stringify(sourceBefore))throw new Error('Actuals changed');
 mutations.push({input:addr,original:before,changed:before+.01,target_before:basePrice,target_after:changed,actuals_unchanged:true});
 A.getRange(addr).values=[[before]];wb.recalculate();
}
if(Math.abs(V.getRange('D10').values[0][0]-basePrice)>1e-8)throw new Error('Restore did not recalculate');
const savedAnchors=['D24','D25','D26'].map(a=>A.getRange(a).values[0][0]);
A.getRange('D24').values=[[savedAnchors[0]+.1]];
wb.recalculate();
const favorableAnchorCheck={target:V.getRange('D10').values[0][0],openingCash:A.getRange('D13').values[0][0],expectedOpeningCash:50.991828+.1*(.5*(1-.15)-.1)};
if(Math.abs(favorableAnchorCheck.target-basePrice)<1e-7||Math.abs(favorableAnchorCheck.openingCash-favorableAnchorCheck.expectedOpeningCash)>1e-7)throw new Error(`Anchor propagation failure ${JSON.stringify(favorableAnchorCheck)}`);
['D24','D25','D26'].forEach((a,i)=>A.getRange(a).values=[[savedAnchors[i]]]);wb.recalculate();
await fs.writeFile(path.join(temp,'anchor_propagation_check.json'),JSON.stringify(favorableAnchorCheck,null,2));
const tailChecks=[];
for(const growth of [.02,.04]){
 A.getRange('D10').values=[[growth]];wb.recalculate();
 const planning=V.getRange('D9').values[0][0],target=V.getRange('D10').values[0][0];
 const investmentIdentity=Y.getRange('T48').values[0][0]-(Y.getRange('T45').values[0][0]-Y.getRange('T46').values[0][0]+Y.getRange('T47').values[0][0]);
 if(Math.abs(investmentIdentity)>1e-7||!Number.isFinite(target)||Math.abs(target-basePrice)<1e-8)throw new Error(`Funded terminal growth failure: ${growth}, ${planning}, ${target}`);
 tailChecks.push({growth,planning,target,investmentIdentity});
}
A.getRange('D10').values=[[.03]];wb.recalculate();
if(Math.abs(V.getRange('D10').values[0][0]-basePrice)>1e-8)throw new Error('Tail-growth restore did not recalculate');
await fs.writeFile(path.join(temp,'terminal_growth_checks.json'),JSON.stringify(tailChecks,null,2));
await fs.writeFile(path.join(temp,'mutation_checks.json'),JSON.stringify(mutations,null,2));
const marketBefore=V.getRange('D57').values[0][0];
V.getRange('D52').values=[[.45]];wb.recalculate();
const marketMutation={industry_growth:.45,implied_Intel_unit_growth:V.getRange('D55').values[0][0],required_ASP_growth:V.getRange('D57').values[0][0],target:V.getRange('D10').values[0][0]};
if(Math.abs(marketMutation.implied_Intel_unit_growth-.218)>1e-8||marketMutation.required_ASP_growth>=marketBefore||Math.abs(marketMutation.target-basePrice)>1e-8)throw new Error('Market diagnostic dependency failed');
V.getRange('D52').values=[[.40]];wb.recalculate();
await fs.writeFile(path.join(temp,'market_diagnostic_check.json'),JSON.stringify(marketMutation,null,2));
const quote=A.getRange('D5').values[0][0],holdingYears=A.getRange('D8').values[0][0];
if(Math.abs(holdingYears-1516/365.25)>1e-10||Math.abs(V.getRange('D11').values[0][0]-.0964291893107092)>1e-10)throw new Error('Current-date return reconciliation failed');
const currentReturn=V.getRange('D11').values[0][0];
A.getRange('D5').values=[[quote+1]];wb.recalculate();
if(V.getRange('D11').values[0][0]>=currentReturn||Math.abs(V.getRange('D10').values[0][0]-basePrice)>1e-8)throw new Error('Quote sensitivity changed forecast or failed return dependency');
A.getRange('D5').values=[[quote]];wb.recalculate();
const hurdlePropagation=[];
for(const hurdle of [.15,0]){
 cell(R,'D10',hurdle);wb.recalculate();
 const required=R.getRange('D11').values[0][0],expected=quote*(1+hurdle)**holdingYears;
 if(Math.abs(required-expected)>1e-10||Math.abs(V.getRange('D10').values[0][0]-basePrice)>1e-8)throw new Error('Research return hurdle changed core forecast or failed dependency');
 hurdlePropagation.push({hurdle,required_price:required,extra_core_cash:R.getRange('D18').values[0][0],extra_higher_rate_cash:R.getRange('E18').values[0][0],core_forecast_unchanged:true});
}
cell(R,'D10',.12);wb.recalculate();
await fs.writeFile(path.join(temp,'research_hurdle_propagation.json'),JSON.stringify(hurdlePropagation,null,2));
const inspection=await wb.inspect({kind:'table',range:'Valuation!C8:M16',include:'values,formulas',tableMaxRows:9,tableMaxCols:11,maxChars:4500});
await fs.writeFile(path.join(temp,'inspection.json'),JSON.stringify(inspection,null,2));
const researchInspection=await wb.inspect({kind:'table',range:'Research checks!C7:G21',include:'values,formulas',tableMaxRows:15,tableMaxCols:5,maxChars:6000});
await fs.writeFile(path.join(temp,'research_inspection.json'),JSON.stringify(researchInspection,null,2));
await fs.mkdir(out,{recursive:true});
for(const [sheetName,range,filename] of [['Valuation','C43:M47','entry-preview.png'],['Research checks','C2:G25','research-cash-preview.png'],['Research checks','C27:G44','research-margin-preview.png'],['Sources','C85:M109','research-source-preview.png']]){
 const image=await wb.render({sheetName,range,scale:1.5,format:'png'});
 await fs.writeFile(path.join(temp,filename),new Uint8Array(await image.arrayBuffer()));
}
const file=path.join(out,'intel_revenue_to_cash_model.xlsx');
const errorCells=[];
for(const [name,s] of Object.entries(sheets))s.getUsedRange().values.forEach((row,i)=>row.forEach((v,j)=>{if(typeof v==='string'&&(/^#(REF!|DIV\/0!|VALUE!|N\/A|NAME\?|NUM!|SPILL!|CALC!|CIRC!)/.test(v)||v.includes(' is not implemented:')))errorCells.push({sheet:name,row:i+1,column:j+1,value:v});}));
if(errorCells.length)throw new Error(`Formula errors ${JSON.stringify(errorCells)}`);
const quarterCashRows=qrows.map((q,i)=>{const c=col(i+6);return {year:q.year,quarter:q.quarter,CPU_revenue_B:Q.getRange(`${c}10`).values[0][0],CPU_unit_index:Q.getRange(`${c}7`).values[0][0],CPU_ASP_index:Q.getRange(`${c}8`).values[0][0],EBIT_B:Q.getRange(`${c}33`).values[0][0],parent_unlevered_cash_B:Q.getRange(`${c}47`).values[0][0],owner_cash_B:Q.getRange(`${c}54`).values[0][0],ending_cash_B:Q.getRange(`${c}60`).values[0][0],ending_debt_B:Q.getRange(`${c}62`).values[0][0]};});
await fs.writeFile(path.join(resolution,'workbook_quarterly_cash_results.json'),JSON.stringify({computed_utc:new Date().toISOString(),scope:'Recalculated core workbook results; new operating/timing and funded stresses are separate research overlays.',quarterly_rows:quarterCashRows,minimum_cash_B:V.getRange('D14').values[0][0],annual_checks:K.getRange('F7:I20').values},null,2));
await (await SpreadsheetFile.exportXlsx(wb)).save(file);
const receipt={created_utc:new Date().toISOString(),output:file,sheets:names,active_case:preferred.metadata.case_name,formula_comparisons:comparisons.length,max_error:Math.max(...comparisons.map(r=>r.error)),formula_error_cells:errorCells,mutations,quarterly_allocation_policy:'2027 sequential units/ASP preserved. 2028-30 annual units allocated23/24/26/27%; annual weighted ASP grows once and is flat within each year.',output_values:{planning:V.getRange('D9').values[0][0],target:V.getRange('D10').values[0][0],annual_return:V.getRange('D11').values[0][0],minimum_quarterly_cash:V.getRange('D14').values[0][0],opening_cash:A.getRange('D13').values[0][0],mature_CPU_margin:A.getRange('D15').values[0][0]},limits:['Tested with bundled formula engine, not native Excel UI.','Forecast policies and future margins remain unproved.']};
await fs.writeFile(path.join(temp,'build_receipt.json'),JSON.stringify(receipt,null,2));
await fs.writeFile(path.join(resolution,'workbook_build_receipt.json'),JSON.stringify({...receipt,quote,holding_years:holdingYears,selected_joint_entry_ceiling:V.getRange('D44').values[0][0],quote_sensitivity_verified:true},null,2));
console.log(JSON.stringify({output:file,comparisons:comparisons.length,planning:V.getRange('D9').values[0][0],target:V.getRange('D10').values[0][0],minimumCash:V.getRange('D14').values[0][0]}));
