# Intel valuation and conditional-decision adversarial review

The arithmetic survives independent reconstruction. The strongest attack is whether the chosen $40 rule compensates for the business evidence accompanying a 28.9% price decline. It is not a calculation error or a claim that conditional recommendations are prohibited.

I compared the current ten-page PDF and eight-page defense PDF directly with the supplied extracted texts using PyMuPDF; both match after whitespace normalization. I rebuilt APV from the active annual cash rows, reconstructed cash identities, and reproduced $56.1393/$82.4702 at 10.625% and $48.5577/$73.5608 at 11.555%. Current-quote returns are 9.6429% and 6.6641% over 4.15058 years. Reproduction errors were zero to displayed numerical precision. The independent calculation is in `recheck_decision.py`; all new results are in `decision_recheck_results.json` in this directory.

## 1. The $40 entry has little tolerance for price-relevant business news

**Judge's attack:** “A 29% decline might bring the entry, but why would your favorable CPU forecast survive the news producing it? Your chosen stress does not reduce CPU delivery. How much of a CPU miss breaks the entry rule?”

**Discriminating test:** The selected funded joint stress produces $64.73785 in 2030. A $40 entry needs $64.02409 for 12% annually. Its cushion is $0.71376 per share, or 1.10% of the selected target. Jointly recomputing the same Foundry/terminal-return/higher-rate case with a persistent CPU revenue level loss of only **1.108%** exhausts the 12% hurdle, even before additional funding costs. This lowers 2027 CPU revenue from $31.739B to $31.387B and 2030 CPU revenue from $60.071B to $59.405B. The existing near-term $124.5B capex and model profit/capital response are retained.

Applying the deck's already-modeled one-quarter delay with no catch-up—an 8.045% persistent CPU level loss—to the selected joint stress gives **$59.52 target, 10.05% annual return at $40, and a $37.19 entry ceiling for 12%**, before incremental financing costs. These losses were jointly recalculated, not added across scenarios. This is a test of the decision rule, not an assertion that the price decline or combined stress is likely.

**Strongest defense:** The defense already says price alone is insufficient, the thesis must remain intact, and earnings or material news requires revaluation. The $40 case is not presented as an all-scenario floor. A market-driven decline without adverse Intel news could create the stated opportunity.

**Verdict:** A genuine robustness gap, already partly disclosed. The recommendation is defensible as a monitored conditional entry, but a 1.1% durable CPU miss is small enough that “thesis intact” cannot merely mean the broad growth-through-share-loss narrative still sounds plausible. The narrow selected stress is insufficient evidence of a robust $40 buying opportunity. The new test resolves the size of that gap; it does not supply scenario probabilities.

References: main PDF pp. 7–8; defense p. 6; `price_and_decision_policy.json`, selected entry rule; `calculate_delivery_joint.py`, `delivery_rows` and `combined_rows`.

## 2. The reinvestment stress starts after the decade carrying most of the growth

**Judge's attack:** “Why does a 15% investment-return stress begin only in 2041? Your long CPU forecast and profit expansion rely on capital productivity throughout 2031–40. Have you stressed that decade?”

The operating value is 92.87% post-2030 and 49.80% post-2040. CPU revenue rises from $60.07B in 2030 to $108.03B in 2040 while its modeled margin rises from 44.14% to 44.91%. The terminal model then has $57.65B NOPAT and $7.49B net investment, implying a 23.08% return on modeled net investment under its convention. R&D remains expensed, so this is not a fully capitalized economic ROIC.

The selected stress changes only the 2041 terminal investment row. It leaves the host incremental sales/net-investment rule at 0.8 through 2040. Lowering that existing rule to 0.6 for **2031–40 only**, while preserving the selected 15% terminal return, all sales/profits, and all 2027–30 capex, requires $32.62B additional cumulative investment. The selected joint target falls to **$61.14**, giving **10.76% at $40** and a **$38.20** ceiling for 12%, before funding costs. The terminal cash is unchanged in this comparison. This is a targeted period-mismatch sensitivity, not evidence that 0.6 is the correct forecast.

**Strongest defense:** The forecast explicitly funds growth and includes replacement capex. It does not assume free growth. The terminal-only timing is disclosed on main pp. 7–8. A sustained profitable CPU franchise can reasonably have most value after a four-year investment period, and 0.6 is not established as superior to 0.8.

**Verdict:** A real underwriting burden, not a defective DCF identity. The terminal stress demonstrates robustness to one late-period capital change; it does not validate the profitable 2031–40 expansion. Reproducing a detailed cash bridge cannot independently establish capital productivity or durable margins.

References: main pp. 4, 7–8; defense p. 4; `integrated_model.py`, post-2030 investment calculation; `calculate_delivery_joint.py:60`, terminal-only change.

## 3. The central forecast, risk method, and entry hurdles were selected after their values were visible

**Judge's attack:** “You promoted a previously favorable operating case, selected the lower ERP method, and then chose hurdles producing a round $40 entry. What establishes this as the expected investment case instead of an attractive combination from your scenario set?”

The decision files explicitly acknowledge both selection steps. The earlier lower operating case at 11.555% has a $53.43 target. At $40 it produces only about **7.22% annually**, compared with **15.81%** for the adopted operating case at the same rate. Selection of the operating path, not merely the ERP debate, drives whether the 15% hurdle is passed. Neither the models nor the PDFs establish probabilities or an unbiased expected cash path.

**Strongest defense:** Forecast selection after analysis is normal investment judgment, not automatically overfitting. The promoted case has stated commercial reasons, both ERP methods predated selection, the higher-rate outcome remains prominent, and the recommendation was downgraded when the quote rose instead of increasing the target. The files explicitly disclose chronology and judgmental hurdles. A long thesis need not be a statistical forecast.

**Verdict:** Known disclosed judgment risk; not proof of manipulation or arithmetic failure. The accurate defense is that this is an owned conditional thesis with transparent competing cases. Calling the selected target an expected outcome, or the chosen stress a calibrated downside bound, would go beyond the evidence. The current deck mostly avoids those claims.

References: `intel_market_share_thesis_2026_11_06/root/decision_policy.json:10`; `intel_valuation_resolution_2026_11_06/root/price_and_decision_policy.json:40`; defense pp. 1, 4, 6.

## Attacks I would not elevate

- **A 55-day valuation-date mismatch:** disclosed; current price CAGR uses the correct November 6–December 2030 horizon. A later entry with unchanged target shortens the horizon and improves CAGR. The 12% ceiling would rise to $43.52 on June 30, 2027 or $46.08 on December 31, 2027, before business/news changes. Do not silently keep a rolling four-year horizon or discount all equity at the operating asset rate.
- **The asset discount rate versus equity return hurdle:** these are different quantities, deliberately separated. 10.625% and 11.555% both reproduce. Their difference is material, but the deck shows it. The APV rate does not itself establish a 12% or 15% equity-return requirement.
- **Counting retained cash twice:** not found. Pre-2030 operating cash enters the 2030 treasury bridge; 2030 operating value begins with 2031 cash. The target's increase over planning value is not a contemporaneous margin of safety, which the defense acknowledges.
- **Revolver fees as the decisive omitted cost:** no material omission established. Modeled stressed interest is cents or fractions of a cent per share; contractual access is conditional and fees remain unmodeled. This is not a fresh legal review of every claim, but the reviewed asset/cash bridge does not support inventing a material deduction or a positive asset correction.

Overall assessment: sound arithmetic, candid current-price restraint, and a conditional entry whose robustness is weaker than the round $40 headline may suggest. The most useful new evidence is the 1.108% CPU miss threshold and the combined existing-delay result. Neither requires inventing additional broad scenarios or treating a previous “closed” label as substantive proof.
