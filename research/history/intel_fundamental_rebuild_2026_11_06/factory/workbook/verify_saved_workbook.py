from copy import copy
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isclose
from pathlib import Path

import openpyxl
from openpyxl.xml.functions import tostring

root = Path('/Users/thomasou/Documents/Codex/2026-11-02/lo')
research = root / 'work/three_hour/active_research/intel_fundamental_rebuild_2026_11_06'
folder = research / 'factory/workbook'
current_path = root / 'outputs/01a19d70-cbad-7e23-b996-11dc618014aa/intel_revenue_to_cash_model.xlsx'
old_path = folder / 'before_intel_revenue_to_cash_model.xlsx'
builder = root / 'tmp/spreadsheets/intel_completion/build_model.mjs'
old = openpyxl.load_workbook(old_path, data_only=False)
new = openpyxl.load_workbook(current_path, data_only=False)
old_values = openpyxl.load_workbook(old_path, data_only=True)
new_values = openpyxl.load_workbook(current_path, data_only=True)
reverse = json.loads((research / 'valuation/valuation_rebuild_results.json').read_text())
controls = json.loads((research / 'factory/packaging_margin_controls.json').read_text())
failures = []
checks = []
changed_text = []
numeric_comparisons = 0
formula_comparisons = 0
style_comparisons = 0
max_numeric_difference = 0.0


def compare_value(actual, expected, label: str) -> None:
    global numeric_comparisons, max_numeric_difference
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        numeric_comparisons += 1
        max_numeric_difference = max(max_numeric_difference, abs(actual - expected))
        if not isclose(actual, expected, rel_tol=0, abs_tol=1e-10):
            failures.append([label, actual, expected])
    elif actual != expected:
        failures.append([label, str(actual), str(expected)])


if new.sheetnames != [*old.sheetnames, 'Research checks']:
    failures.append(['sheet order', new.sheetnames, old.sheetnames])
for name in old.sheetnames:
    a, b = old[name], new[name]
    for field in ['freeze_panes', 'sheet_state']:
        compare_value(getattr(b, field), getattr(a, field), f'{name}.{field}')
    compare_value(b.sheet_view.showGridLines, a.sheet_view.showGridLines, f'{name}.gridlines')
    compare_value(str(b.merged_cells), str(a.merged_cells), f'{name}.merged_cells')
    old_formats = [(str(item.sqref), [tostring(rule.to_tree()).decode() for rule in a.conditional_formatting[item]]) for item in a.conditional_formatting]
    new_formats = [(str(item.sqref), [tostring(rule.to_tree()).decode() for rule in b.conditional_formatting[item]]) for item in b.conditional_formatting]
    compare_value(new_formats, old_formats, f'{name}.conditional_formatting')
    for key, dimension in a.column_dimensions.items():
        for field in ['width', 'hidden', 'outlineLevel']:
            compare_value(getattr(b.column_dimensions[key], field), getattr(dimension, field), f'{name}.column.{key}.{field}')
    for row in a.iter_rows():
        for before in row:
            address = before.coordinate
            after = b[address]
            if name == 'Sources' and before.row >= 85:
                continue
            if name == 'Valuation' and address == 'F45':
                changed_text.append({'cell': f'{name}!{address}', 'before': before.value, 'after': after.value})
            else:
                compare_value(after.value, before.value, f'{name}!{address}.formula_or_value')
                compare_value(new_values[name][address].value, old_values[name][address].value, f'{name}!{address}.cached_value')
                formula_comparisons += before.data_type == 'f'
            for field in ['font', 'fill', 'border', 'alignment', 'protection', 'number_format']:
                style_comparisons += 1
                if copy(getattr(after, field)) != copy(getattr(before, field)):
                    failures.append([f'{name}!{address}.{field}', 'changed'])

for sheet in new_values:
    for row in sheet.iter_rows():
        for cell in row:
            value = cell.value
            if cell.data_type == 'e' or (isinstance(value, str) and ' is not implemented:' in value):
                failures.append([f'{sheet.title}!{cell.coordinate}', value])

r = new_values['Research checks']
for column, rate in [('D', 0.10625), ('E', 0.11555)]:
    expected = next(row for row in reverse['reverse_operating_thresholds'] if row['rate'] == rate and row['annual_return_hurdle'] == 0.12)
    for row, key in [(11, 'required_Dec2030_price_USD'), (18, 'equivalent_extra_parent_cash2031_B_growing3pct'), (20, 'equivalent_total_normalized_parent_cash2031_B')]:
        value = r[f'{column}{row}'].value
        compare_value(value, expected[key], f'Research checks!{column}{row}.independent_rebuild')
        checks.append({'cell': f'Research checks!{column}{row}', 'value': value, 'expected': expected[key]})
    extra = (r[f'{column}11'].value - r[f'{column}12'].value) * r[f'{column}15'].value * (r[f'{column}13'].value - r[f'{column}14'].value)
    compare_value(r[f'{column}18'].value, extra, f'{column}.cash_identity')

cases = ['rounded_ASE_ATM_Q3_margin20pct_control', 'unchanged_owned_case', 'Intel_attributed_aspiration30pct_control']
for i, key in enumerate(cases, 30):
    for target_col, annual_col, rate in [('D', 'E', '0.10625'), ('F', 'G', '0.11555')]:
        expected = controls['results'][rate][key]
        compare_value(r[f'{target_col}{i}'].value, expected['Dec2030_target_USD'], f'{target_col}{i}.control_target')
        compare_value(r[f'{annual_col}{i}'].value, expected['annual_price_return_from_Nov6_56_28'], f'{annual_col}{i}.control_return')

required_formulas = {'D11': '=D8*(1+D10)^D9', 'E11': '=D11', 'D18': '=D17*D15*(D13-D14)', 'E18': '=E17*E15*(E13-E14)'}
for address, formula in required_formulas.items():
    compare_value(new['Research checks'][address].value, formula, f'{address}.formula')
compare_value(new_values['Assumptions']['D5'].value, 56.28, 'quote')
compare_value(new_values['Valuation']['D10'].value, 82.47015162680005, 'central_target')
compare_value(new_values['Valuation']['D9'].value, 56.139285845568374, 'central_planning')
compare_value(r['D10'].value, 0.12, 'restored_hurdle')
annual = new_values['Annual model']
return_on_investment = new_values['Assumptions']['D10'].value * annual['T43'].value / annual['T48'].value
compare_value(r['D39'].value, return_on_investment, 'modeled_return_label')

receipt = {
    'computed_utc': datetime.now(timezone.utc).isoformat(),
    'method': 'Read saved XLSX formulas, cached values, and styles with openpyxl; no openpyxl authoring. Compare original six sheets with pre-edit snapshot. Independently reconcile research controls to separately rebuilt Python outputs.',
    'output': str(current_path),
    'sha256': {str(path): sha256(path.read_bytes()).hexdigest() for path in [current_path, builder, old_path, folder / 'before_build_model.mjs']},
    'sheets': new.sheetnames,
    'numeric_comparisons': numeric_comparisons,
    'original_formulas_preserved': formula_comparisons,
    'original_style_property_comparisons': style_comparisons,
    'max_numeric_difference': max_numeric_difference,
    'permitted_existing_text_changes': changed_text,
    'permitted_additions': ['Sources rows 85-109', 'Research checks sheet'],
    'reverse_cash_checks': checks,
    'modeled_return_on_net_investment': return_on_investment,
    'visuals_reviewed': ['entry-preview.png', 'research-cash-preview.png', 'research-margin-preview.png', 'research-source-preview.png'],
    'formula_errors': [],
    'failures': failures,
    'limits': ['Native Microsoft Excel UI execution was not performed.', 'Margin results and higher-rate target are clearly labeled dated captures, not automatic forecast sensitivities.', 'Source URLs are ordinary cell text, consistent with the original Sources tab.'],
}
(folder / 'saved_workbook_independent_verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({key: receipt[key] for key in ['sheets', 'numeric_comparisons', 'original_formulas_preserved', 'original_style_property_comparisons', 'max_numeric_difference', 'failures']}))
assert not failures, failures[:10]
