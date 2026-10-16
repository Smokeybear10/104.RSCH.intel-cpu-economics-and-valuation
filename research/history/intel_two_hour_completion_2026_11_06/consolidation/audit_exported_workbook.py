from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import hashlib
import json
import math
import re

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
ROOT = RUN.parents[3]
BOOK = ROOT / 'outputs/01a19d70-cbad-7e23-b996-11dc618014aa/intel_revenue_to_cash_model.xlsx'
FILES = {
    'workbook': BOOK,
    'annual_results': RUN / 'root/integrated_results.json',
    'quarterly_results': RUN / 'root/quarterly_cash_results.json',
    'selected_quarters': RUN / 'quarterly/selected_quarterly_forecast.json',
    'builder': ROOT / 'tmp/spreadsheets/intel_completion/build_model.mjs',
    'builder_receipt': ROOT / 'tmp/spreadsheets/intel_completion/build_receipt.json',
    'anchor_forecasts': RUN / 'quarterly/favorable_anchor_case_results.json',
    'anchor_valuations': RUN / 'quarterly/anchor_valuation_overlay_results.json',
}
HASHES = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in FILES.items()}
NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
TOKEN = re.compile(r"\s*(?:(?P<ref>(?:'(?:[^']|'')+'!)?\$?[A-Z]{1,3}\$?[0-9]+)|(?P<num>(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)|(?P<name>[A-Z]+)|(?P<op><>|<=|>=|[+\-*/^%=<>(),:]))")


def column(n: int) -> str:
    text = ''
    while n:
        n, rem = divmod(n - 1, 26)
        text = chr(65 + rem) + text
    return text


def reference(text: str, sheet: str) -> tuple[str, str]:
    if '!' in text:
        name, address = text.split('!')
        return name[1:-1].replace("''", "'"), address.replace('$', '')
    return sheet, text.replace('$', '')


def coordinates(address: str) -> tuple[int, int]:
    letters, row = re.fullmatch(r'([A-Z]+)([0-9]+)', address).groups()
    col = 0
    for letter in letters:
        col = col * 26 + ord(letter) - 64
    return col, int(row)


def parse(text: str, sheet: str) -> tuple:
    tokens, pos = [], 0
    while pos < len(text):
        match = TOKEN.match(text, pos)
        assert match, (sheet, text, pos)
        tokens.append((match.lastgroup, match.group(match.lastgroup)))
        pos = match.end()
    i = 0

    def expr(minimum: int = 0) -> tuple:
        nonlocal i
        kind, value = tokens[i]
        i += 1
        if value in ('+', '-'):
            node = ('unary', value, expr(35))
        elif value == '(':
            node = expr()
            assert tokens[i][1] == ')'
            i += 1
        elif kind == 'num':
            node = ('number', float(value))
        elif kind == 'ref':
            first = reference(value, sheet)
            node = ('reference', first)
            if i < len(tokens) and tokens[i][1] == ':':
                i += 1
                last = reference(tokens[i][1], first[0])
                i += 1
                node = ('range', first, last)
        elif kind == 'name':
            assert tokens[i][1] == '('
            i += 1
            args = [expr()]
            while tokens[i][1] == ',':
                i += 1
                args.append(expr())
            assert tokens[i][1] == ')'
            i += 1
            node = ('function', value, args)
        else:
            raise ValueError((kind, value))
        while i < len(tokens):
            op = tokens[i][1]
            if op == '%':
                i += 1
                node = ('binary', '/', node, ('number', 100.))
                continue
            precedence = {'=': 5, '<>': 5, '<': 5, '>': 5, '<=': 5, '>=': 5, '+': 10, '-': 10, '*': 20, '/': 20, '^': 40}.get(op)
            if precedence is None or precedence < minimum:
                break
            i += 1
            node = ('binary', op, node, expr(precedence + 1))
        return node

    result = expr()
    assert i == len(tokens), (text, tokens[i:])
    return result


with ZipFile(BOOK) as archive:
    relation_root = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    relationships = {e.attrib['Id']: e.attrib['Target'].lstrip('/') for e in relation_root}
    workbook_root = ET.fromstring(archive.read('xl/workbook.xml'))
    shared_root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
    shared = [''.join(e.itertext()) for e in shared_root]
    cells, sheets, error_cells = {}, [], []
    for sheet in workbook_root.findall('x:sheets/x:sheet', NS):
        name = sheet.attrib['name']
        sheet_root = ET.fromstring(archive.read(relationships[sheet.attrib[RID]]))
        formula_count = 0
        for cell in sheet_root.findall('.//x:c', NS):
            address = cell.attrib['r']
            formula = cell.find('x:f', NS)
            cached = cell.find('x:v', NS)
            kind = cell.attrib.get('t', 'n')
            value = None if cached is None else cached.text
            if kind == 's':
                value = shared[int(value)]
            elif kind == 'inlineStr':
                value = ''.join(cell.find('x:is', NS).itertext())
            elif kind == 'e':
                error_cells.append({'sheet': name, 'cell': address, 'value': value})
            elif kind == 'd':
                value = (datetime.fromisoformat(value.replace('Z', '+00:00')) - datetime(1899, 12, 30, tzinfo=timezone.utc)).total_seconds() / 86400
            elif value is not None and kind not in ('str', 'inlineStr'):
                value = float(value)
            if formula is not None:
                assert not formula.attrib, (name, address, formula.attrib)
                formula_count += 1
            cells[name, address] = {'value': value, 'formula': formula.text if formula is not None else None}
        sheets.append({'name': name, 'formula_count': formula_count})
    external_links = [p for p in archive.namelist() if p.startswith('xl/externalLinks/')]
    calc_properties = workbook_root.find('x:calcPr', NS)
    calc_properties = None if calc_properties is None else calc_properties.attrib

trees = {key: parse(cell['formula'], key[0]) for key, cell in cells.items() if cell['formula']}


class Evaluation:
    def __init__(self, overrides: dict | None = None):
        self.overrides = overrides or {}
        self.cache = {}
        self.pending = set()

    def cell(self, key: tuple[str, str]) -> float:
        if key in self.overrides:
            return self.overrides[key]
        if key in self.cache:
            return self.cache[key]
        assert key not in self.pending, ('circular reference', key)
        self.pending.add(key)
        if key in trees:
            value = self.node(trees[key])
        else:
            value = cells.get(key, {}).get('value')
            value = 0. if value is None else value
        self.pending.remove(key)
        self.cache[key] = value
        return value

    def node(self, node: tuple):
        kind, *args = node
        if kind == 'number':
            return args[0]
        if kind == 'reference':
            return self.cell(args[0])
        if kind == 'range':
            (sheet, start), (end_sheet, end) = args
            assert sheet == end_sheet
            c1, r1 = coordinates(start)
            c2, r2 = coordinates(end)
            return [self.cell((sheet, f'{column(c)}{r}')) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
        if kind == 'unary':
            value = self.node(args[1])
            return value if args[0] == '+' else -value
        if kind == 'binary':
            operator, left, right = args
            a, b = self.node(left), self.node(right)
            return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b,
                    '/': lambda: a / b, '^': lambda: a ** b, '=': lambda: a == b,
                    '<>': lambda: a != b, '<': lambda: a < b, '>': lambda: a > b,
                    '<=': lambda: a <= b, '>=': lambda: a >= b}[operator]()
        if kind == 'function':
            name, expressions = args
            if name == 'IF':
                return self.node(expressions[1 if self.node(expressions[0]) else 2])
            values = []
            for expression in expressions:
                value = self.node(expression)
                values.extend(value if isinstance(value, list) else [value])
            return {'SUM': sum, 'MIN': min, 'MAX': max}[name](values)
        raise ValueError(node)


engine = Evaluation()
formula_errors = []
for key in trees:
    expected = cells[key]['value']
    actual = engine.cell(key)
    error = abs(actual - expected) if isinstance(expected, (int, float)) else math.inf
    formula_errors.append({'cell': '!'.join(key), 'error': error})

annual = json.loads(FILES['annual_results'].read_text())
quarterly = json.loads(FILES['quarterly_results'].read_text())
selected = json.loads(FILES['selected_quarters'].read_text())
preferred = annual['cases']['preferred']
comparisons = []


def compare(sheet: str, address: str, expected: float, meaning: str) -> None:
    actual = engine.cell((sheet, address))
    comparisons.append({'cell': f'{sheet}!{address}', 'meaning': meaning, 'actual': actual,
                        'expected': expected, 'error': abs(actual - expected)})


annual_fields = {7: 'CPU_revenue_B', 8: 'Other_DCAI_B', 9: 'DCAI_revenue_B', 10: 'client_revenue_B',
                 11: 'Other_CCPG_B', 12: 'CCPG_revenue_B', 13: 'Products_revenue_B',
                 14: 'All_Other_gross_B', 16: 'net_All_Other_B', 17: 'legacy_external_Foundry_B',
                 18: 'gross_new_packaging_B', 19: 'consolidated_revenue_B', 21: 'host_capital_revenue_B',
                 32: 'DCAI_profit_B', 34: 'CCPG_profit_B', 36: 'Foundry_profit_B',
                 37: 'net_packaging_profit_B', 38: 'Other_profit_less_corporate_B', 39: 'EBIT_B',
                 42: 'ordinary_operating_tax_B', 45: 'physical_capex_B', 46: 'DA_B', 47: 'WC_cash_use_B',
                 50: 'lease_cash_B', 51: 'minority_cash_B', 52: 'old_credit_collection_B',
                 53: 'new_credit_collection_B', 54: 'credit_basis_loss_tax_B', 55: 'parent_unlevered_cash_B',
                 57: 'financing_shield_B'}
quarter_fields = {10: 'CPU_revenue_B', 14: 'client_revenue_B', 24: 'consolidated_revenue_B',
                  28: 'DCAI_profit_B', 29: 'CCPG_profit_B', 33: 'EBIT_B', 34: 'ordinary_operating_tax_B',
                  37: 'physical_capex_B', 38: 'DA_B', 39: 'WC_cash_use_B', 47: 'parent_unlevered_cash_B',
                  49: 'ordinary_interest_B', 50: 'capitalized_interest_B', 51: 'cash_income_B',
                  54: 'owner_cash_B', 57: 'escrow_cash_B', 58: 'Classiq_cash_B', 59: 'principal_B',
                  60: 'ending_cash_B', 62: 'ending_debt_B'}
for year, row in preferred['annual_rows'].items():
    col = column(int(year) - 2021)
    for line, key in annual_fields.items():
        compare('Annual model', f'{col}{line}', row[key], f'{year} {key}')
    compare('Annual model', f'{col}15', -row['All_Other_internal_B'], 'internal-sales elimination')
    compare('Annual model', f'{col}48', row['physical_capex_B'] - row['DA_B'] + row['WC_cash_use_B'], 'net reinvestment')
for i, row in enumerate(quarterly['base']['quarterly_rows']):
    col = column(i + 6)
    for line, key in quarter_fields.items():
        compare('Quarterly model', f'{col}{line}', row[key], f"{row['year']}Q{row['quarter']} {key}")
    for source, line, field in [('CPU_quarterly', 7, 'unit_index_Q4_2026_100'), ('CPU_quarterly', 8, 'ASP_index_Q4_2026_100'),
                                ('client_quarterly', 12, 'unit_index_Q4_2026_100'), ('client_quarterly', 13, 'ASP_index_Q4_2026_100')]:
        compare('Quarterly model', f'{col}{line}', selected[source][i][field], f'{source} {field}')
for address, expected in [('D9', preferred['values']['2026']['price_USD']), ('D10', preferred['values']['2030']['price_USD']),
                          ('D14', quarterly['base']['minimum_quarter_end_cash_B'])]:
    compare('Valuation', address, expected, 'root model output')

mutations = []
receipt = json.loads(FILES['builder_receipt'].read_text())
for mutation in receipt['mutations']:
    key = ('Assumptions', mutation['input'])
    changed = Evaluation({key: mutation['changed']})
    actual = changed.cell(('Valuation', 'D10'))
    source_actuals_stable = all(changed.cell(('Sources', f'{column(c)}{r}')) == engine.cell(('Sources', f'{column(c)}{r}'))
                                for c in range(6, 10) for r in range(6, 9))
    mutations.append({'input': '!'.join(key), 'independent_target': actual, 'builder_target': mutation['target_after'],
                      'difference': abs(actual - mutation['target_after']), 'source_actuals_unchanged': source_actuals_stable})

anchor_checks = []
anchor_forecasts = json.loads(FILES['anchor_forecasts'].read_text())['cases']
anchor_valuations = json.loads(FILES['anchor_valuations'].read_text())['cases']
for name, forecast in anchor_forecasts.items():
    q4 = forecast['Q4_2026']
    overrides = {('Assumptions', 'D24'): q4['CPU_B'], ('Assumptions', 'D25'): q4['client_B'],
                 ('Assumptions', 'D26'): forecast['FY2026_revised_product_bases']['Other_DCAI_B']}
    modified = Evaluation(overrides)
    expected = anchor_valuations[f'{name}__YTD_normalized_growth']
    errors = []
    for year, row in expected['annual_rows'].items():
        for line, key in annual_fields.items():
            errors.append(abs(modified.cell(('Annual model', f'{column(int(year) - 2021)}{line}')) - row[key]))
    expected_opening = engine.cell(('Sources', 'F60')) + q4['opening2027_economic_cash_delta_B']
    opening = modified.cell(('Assumptions', 'D13'))
    target = modified.cell(('Valuation', 'D10'))
    anchor_checks.append({'case': name, 'annual_comparisons': len(errors), 'annual_max_error': max(errors),
                          'opening_cash_B': opening, 'opening_cash_error_B': abs(opening - expected_opening),
                          'target_USD': target, 'target_error_USD': abs(target - expected['values']['2030']['price_USD']),
                          '2027_WC_B': modified.cell(('Annual model', 'F47'))})


def terminal_control(evaluation: Evaluation, growth: float) -> dict:
    get = evaluation.cell
    EBIT = get(('Annual model', 'T39'))
    tax_rate = get(('Assumptions', 'T59'))
    host = get(('Annual model', 'T21'))
    pack = get(('Annual model', 'T20'))
    claims = get(('Annual model', 'T50')) + get(('Annual model', 'T51'))
    next_cash = EBIT * (1 + growth) * (1 - tax_rate) - growth * host / get(('Assumptions', 'D21')) - growth * pack / get(('Assumptions', 'T119')) - claims * (1 + growth)
    claimed_next_cash = get(('Annual model', 'T55')) * (1 + growth)
    return {'growth': growth, '2041_FCFF_B': get(('Annual model', 'T55')), 'implied_2042_FCFF_B': next_cash,
            '2042_FCFF_assumed_by_Gordon_B': claimed_next_cash, 'cash_scaling_mismatch_B': next_cash - claimed_next_cash,
            'planning2026_USD': get(('Valuation', 'D9')), 'target2030_USD': get(('Valuation', 'D10'))}


terminal_edits = []
for growth in [.02, .03, .04]:
    unchanged_trajectory = Evaluation({('Assumptions', 'D10'): growth})
    linked = {('Assumptions', 'D10'): growth}
    for row in [37, 38, 120, 121]:
        linked['Assumptions', f'T{row}'] = growth
    linked['Assumptions', 'T40'] = (1 + growth) / (1 + engine.cell(('Assumptions', 'T39'))) - 1
    linked['Assumptions', 'T42'] = (1 + growth) / (1 + engine.cell(('Assumptions', 'T41'))) - 1
    for row in [43, 44, 45, 58, 63, 64]:
        linked['Assumptions', f'T{row}'] = engine.cell(('Assumptions', f'S{row}')) * (1 + growth)
    corrected = Evaluation(linked)
    terminal_edits.append({'growth': growth, 'exported_behavior': terminal_control(unchanged_trajectory, growth),
                           'proposed_all_terminal_growth_links_in_memory': terminal_control(corrected, growth)})
other_margin_controls = []
for margin in [.1, .2, .3]:
    controlled = Evaluation({('Assumptions', 'D16'): margin})
    other_margin_controls.append({'mature_Other_DCAI_margin': margin, **terminal_control(controlled, .03)})

check_values = [{'cell': '!'.join(key), 'value': engine.cell(key)} for key in trees if key[0] == 'Checks']
all_unchanged = all(hashlib.sha256(path.read_bytes()).hexdigest() == HASHES[name] for name, path in FILES.items())
report = {
    'audited_utc': datetime.now(timezone.utc).isoformat(), 'file_hashes_before': HASHES,
    'method': 'Read-only Python standard-library ZIP/XML. Independently parse and recursively evaluate every stored formula from exported numeric inputs, ignoring cached formula values during calculation. No artifact-tool or root model function calls, no openpyxl, no workbook writes.',
    'sheets': sheets, 'external_link_parts': external_links, 'calculation_properties': calc_properties,
    'formula_count': len(trees), 'formula_cache_max_error': max(r['error'] for r in formula_errors),
    'formula_cache_mismatches': [r for r in formula_errors if r['error'] > 1e-8], 'excel_error_cells': error_cells,
    'source_model_comparisons': len(comparisons), 'source_model_max_error': max(r['error'] for r in comparisons),
    'source_model_mismatches': [r for r in comparisons if r['error'] > 1e-8],
    'independent_mutation_controls': mutations, 'terminal_checks': check_values,
    'Q4_anchor_propagation_controls': anchor_checks,
    'terminal_growth_input_controls': terminal_edits,
    'mature_Other_margin_controls': other_margin_controls,
    'all_input_and_workbook_hashes_unchanged': all_unchanged,
    'verified_outputs': {cell: engine.cell(('Valuation', cell)) for cell in ['D8', 'D9', 'D10', 'D11', 'D12', 'D13', 'D14', 'D15', 'D43']},
    'limits': ['Native Microsoft Excel UI was not run. XML formulas and caches were independently evaluated.',
               'Agreement validates implementation of dated assumptions, not future revenue, cash access, probabilities or competition-winning odds.',
               'This workbook forecasts aggregate operating cash and financial claims, not a fully linked GAAP three-statement model.',
               'The workbook has one editable base cash-timing schedule; the concentrated timing controls remain in the accompanying research calculations.'],
}
(OUT / 'independent_exported_workbook_audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key: report[key] for key in ['formula_count', 'formula_cache_max_error', 'formula_cache_mismatches', 'source_model_comparisons', 'source_model_max_error', 'source_model_mismatches', 'independent_mutation_controls', 'all_input_and_workbook_hashes_unchanged', 'verified_outputs']}, indent=2))
