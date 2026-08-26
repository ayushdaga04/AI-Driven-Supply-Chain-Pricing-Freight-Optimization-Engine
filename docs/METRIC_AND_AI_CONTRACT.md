# Metric and AI contract

## Analytical grain

One row represents one shipment line item. The dashboard does not infer shipment-level totals across repeated ASN/DN identifiers.

## Eligibility

- Freight metrics require captured positive freight cost.
- Freight-per-kilogram additionally requires captured positive weight.
- Freight-to-value additionally requires positive line-item value.
- Model training excludes rows missing any required target or core numeric feature.

## Quote Lab

The quote is not a market prediction. It multiplies the proposed weight by the historical median, 25th percentile, and 75th percentile freight-per-kilogram for the selected country-mode cohort. Cohorts with fewer than five records are not exposed.

## Peer price index

`freight_per_kg / median_freight_per_kg_for_same_mode_and_weight_band`

This is an investigation signal, not proof of overcharging. Urgency, service level, route constraints, consolidation, incoterm, and contract terms require validation.

## AI guardrails

- Only the supplied CSV snapshot and derived aggregates may support numerical statements.
- Every numerical response includes a bracketed evidence record.
- Historical benchmarks are never called current prices.
- Suggested explanations are labeled hypotheses.
- The offline deterministic mode requires no API key, network, or paid service.
