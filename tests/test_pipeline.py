import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = json.loads((ROOT / "data/processed/pricing_intelligence.json").read_text())

def test_source_contract():
    assert PAYLOAD["summary"]["rows"] == 10324
    assert PAYLOAD["summary"]["arv_rows"] == 8550
    assert PAYLOAD["source"]["grain"] == "One shipment line item"

def test_eligible_feature_rows():
    rows = PAYLOAD["records"]
    assert len(rows) == 6162
    assert all(r["weight_kg"] > 0 and r["freight_cost"] > 0 and r["item_value"] > 0 for r in rows)

def test_quote_benchmarks_have_coverage_and_ordered_bounds():
    for row in PAYLOAD["benchmarks"]:
        assert row["shipments"] >= 5
        assert row["p25_freight_per_kg"] <= row["median_freight_per_kg"] <= row["p75_freight_per_kg"]

def test_model_evaluation_is_holdout_based():
    model = PAYLOAD["model"]
    assert model["test_rows"] > 0
    assert 0 < model["r2_log"] < 1
    assert "Chronological" in model["method"]

def test_grounding_caveats_are_visible():
    evidence = " ".join(row["evidence"] for row in PAYLOAD["quality"])
    assert "missing freight cost" in evidence
    assert "missing shipment weight" in evidence
