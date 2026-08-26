# Interview walkthrough

## 90-second story

“I revisited an older graduate supply-chain pricing analysis and rebuilt it as a full decision product. The source contains 10,324 historical shipment line items, primarily ARV products across 43 countries. I first created explicit data-quality and metric rules because roughly 40% of freight and 38% of weight values are missing. I then built a governed feature layer, a chronologically evaluated freight-cost model, and peer benchmarks by country, shipment mode, and weight cohort.

The unique feature is the Quote Lab. A user can enter a proposed destination, shipment mode, weight, quantity, and item value. The system returns a historical peer median and interquartile freight range, shows the comparable sample size, and uses a deterministic AI layer to challenge cost-to-serve assumptions and identify lower-cost historical mode alternatives. The AI cannot invent numbers; every conclusion cites the exact evidence cohort.

The project demonstrates data cleaning, pricing analytics, model evaluation, explainability, dashboard engineering, and business decision support—not just visualization.”

## Demo order

1. Network Pulse: explain scope, historical limitation, and the difference between procurement value and freight.
2. Quote Lab: change country, mode, weight, and value; interpret the expected range and confidence.
3. Cost Drivers: explain chronological evaluation and why predictive importance is not causality.
4. Exception Manifest: open a high peer-index line and discuss investigation rather than accusation.
5. Trust Center: show missingness, eligibility rules, and AI grounding.

## Defensible answers

**Why not impute freight and weight?**  
The missingness is material and may not be random. Silent imputation would create false precision in lane pricing. I expose coverage and restrict cost metrics to eligible rows.

**Is the quote a current prediction?**  
No. It is an empirical historical benchmark that demonstrates the decision workflow. A production version would require current carrier rates, service levels, fuel surcharges, and contract terms.

**Why use chronological evaluation?**  
Random splitting can leak historical patterns into both train and test sets. The chronological holdout better approximates how the model would generalize to later shipments.

**Why use log freight cost?**  
Freight cost has a long right tail. Modeling the logarithm reduces dominance by extreme shipments while preserving relative cost structure.
