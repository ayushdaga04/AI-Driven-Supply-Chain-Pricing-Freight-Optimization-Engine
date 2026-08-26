"""Reproducible data-quality, pricing, benchmarking, and model pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data/raw/Supply_Chain_Shipment_Pricing_Dataset.csv"
OUT = ROOT / "data/processed"
WEB_DATA = ROOT / "web/data.js"

NUMERIC = [
    "line item quantity", "line item value", "pack price", "unit price",
    "weight (kilograms)", "freight cost (usd)", "line item insurance (usd)",
]
DATES = ["scheduled delivery date", "delivered to client date", "delivery recorded date"]


def clean() -> pd.DataFrame:
    df = pd.read_csv(RAW, low_memory=False)
    for col in NUMERIC:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in DATES:
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=False)
    for col in ["country", "shipment mode", "fulfill via", "vendor inco term", "product group", "sub classification"]:
        df[col] = df[col].fillna("Not captured").astype(str).str.strip()

    df["year"] = df["delivered to client date"].dt.year.astype("Int64")
    df["delivery_variance_days"] = (df["delivered to client date"] - df["scheduled delivery date"]).dt.days
    df["on_time"] = df["delivery_variance_days"].le(0)
    df["landed_cost"] = df["line item value"] + df["freight cost (usd)"].fillna(0) + df["line item insurance (usd)"].fillna(0)
    valid_weight = df["weight (kilograms)"].gt(0)
    valid_value = df["line item value"].gt(0)
    df["freight_per_kg"] = np.where(valid_weight, df["freight cost (usd)"] / df["weight (kilograms)"], np.nan)
    df["freight_pct_value"] = np.where(valid_value, 100 * df["freight cost (usd)"] / df["line item value"], np.nan)
    df["value_per_kg"] = np.where(valid_weight, df["line item value"] / df["weight (kilograms)"], np.nan)
    return df


def model_freight(df: pd.DataFrame):
    features = ["weight (kilograms)", "line item value", "line item quantity", "unit price", "shipment mode", "country", "fulfill via", "vendor inco term", "product group", "sub classification"]
    usable = df[df["freight cost (usd)"].gt(0) & df["weight (kilograms)"].gt(0) & df["line item value"].gt(0)].copy()
    usable = usable[usable["year"].notna()].sort_values("delivered to client date")
    numeric = features[:4]
    categorical = features[4:]
    X = usable[features]
    y = np.log1p(usable["freight cost (usd)"])
    split = max(int(len(usable) * .8), 1)
    X_train, X_test, y_train, y_test = X.iloc[:split], X.iloc[split:], y.iloc[:split], y.iloc[split:]
    prep = ColumnTransformer([
        ("num", "passthrough", numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=8), categorical),
    ])
    forest = RandomForestRegressor(n_estimators=140, max_depth=14, min_samples_leaf=4, random_state=42, n_jobs=-1)
    pipe = Pipeline([("prep", prep), ("model", forest)])
    pipe.fit(X_train, y_train)
    pred = np.expm1(pipe.predict(X_test))
    actual = np.expm1(y_test)
    r2_log = r2_score(y_test, np.log1p(pred))
    r2_dollars = r2_score(actual, pred)
    mae = mean_absolute_error(actual, pred)

    names = pipe.named_steps["prep"].get_feature_names_out()
    importances = pipe.named_steps["model"].feature_importances_
    grouped = {}
    for name, value in zip(names, importances):
        clean_name = name.replace("num__", "").replace("cat__", "")
        base = next((c for c in categorical if clean_name.startswith(c + "_")), clean_name)
        grouped[base] = grouped.get(base, 0) + float(value)
    drivers = [{"feature": k, "importance": round(v, 5)} for k, v in sorted(grouped.items(), key=lambda x: x[1], reverse=True)]
    return pipe, usable, {
        "training_rows": int(len(X_train)), "test_rows": int(len(X_test)),
        "r2_log": round(float(r2_log), 3), "r2_dollars": round(float(r2_dollars), 3),
        "mae_usd": round(float(mae), 2), "drivers": drivers,
        "method": "Chronological 80/20 split; Random Forest on log freight cost",
    }


def records(df: pd.DataFrame) -> list[dict]:
    view = df[df["year"].notna()].copy()
    valid = view["freight_per_kg"].replace([np.inf, -np.inf], np.nan).notna()
    view = view[valid & view["freight_pct_value"].notna()].copy()
    view["weight_band"] = pd.qcut(view["weight (kilograms)"], 6, labels=["XS", "S", "M", "L", "XL", "XXL"], duplicates="drop").astype(str)
    med = view.groupby(["shipment mode", "weight_band"], observed=True)["freight_per_kg"].transform("median")
    view["benchmark_freight_per_kg"] = med
    view["price_index"] = view["freight_per_kg"] / med
    view["anomaly_score"] = np.abs(np.log(view["price_index"].clip(lower=.01)))
    view["reason"] = np.select(
        [view["price_index"].gt(2), view["freight_pct_value"].gt(25), view["delivery_variance_days"].gt(14)],
        ["Freight/kg > 2x peer lane", "Freight > 25% of item value", "Delivery > 14 days late"],
        default="Peer deviation",
    )
    cols = {
        "id": "id", "country": "country", "shipment mode": "mode", "fulfill via": "fulfill",
        "vendor inco term": "incoterm", "product group": "product", "sub classification": "classification",
        "vendor": "vendor", "molecule/test type": "molecule", "year": "year",
        "line item quantity": "quantity", "line item value": "item_value", "unit price": "unit_price",
        "weight (kilograms)": "weight_kg", "freight cost (usd)": "freight_cost",
        "freight_per_kg": "freight_per_kg", "freight_pct_value": "freight_pct_value",
        "landed_cost": "landed_cost", "delivery_variance_days": "delivery_variance_days",
        "on_time": "on_time", "weight_band": "weight_band", "benchmark_freight_per_kg": "benchmark_freight_per_kg",
        "price_index": "price_index", "anomaly_score": "anomaly_score", "reason": "reason",
    }
    out = view[list(cols)].rename(columns=cols)
    for col in out.select_dtypes(include="number"):
        out[col] = out[col].round(4)
    return json.loads(out.to_json(orient="records"))


def aggregate(df: pd.DataFrame, model: dict, shipment_records: list[dict]) -> dict:
    valid_freight = df[df["freight cost (usd)"].gt(0)]
    valid_weight = df[df["freight_per_kg"].notna() & np.isfinite(df["freight_per_kg"])]
    annual = (valid_freight.groupby("year", dropna=True).agg(
        shipments=("id", "count"), item_value=("line item value", "sum"), freight_cost=("freight cost (usd)", "sum"),
        median_freight=("freight cost (usd)", "median"), on_time_rate=("on_time", "mean"),
    ).reset_index().dropna()).to_dict("records")
    modes = (valid_weight.groupby("shipment mode").agg(
        shipments=("id", "count"), freight_cost=("freight cost (usd)", "sum"), median_freight_per_kg=("freight_per_kg", "median"),
        median_freight_pct=("freight_pct_value", "median"), on_time_rate=("on_time", "mean"),
    ).reset_index().sort_values("shipments", ascending=False)).to_dict("records")
    countries = (valid_weight.groupby("country").agg(
        shipments=("id", "count"), freight_cost=("freight cost (usd)", "sum"), item_value=("line item value", "sum"),
        median_freight_per_kg=("freight_per_kg", "median"), median_freight_pct=("freight_pct_value", "median"),
        on_time_rate=("on_time", "mean"),
    ).reset_index().query("shipments >= 10").sort_values("freight_cost", ascending=False)).to_dict("records")
    benchmarks = (valid_weight.groupby(["shipment mode", "country"]).agg(
        shipments=("id", "count"), median_freight_per_kg=("freight_per_kg", "median"),
        p25_freight_per_kg=("freight_per_kg", lambda s: s.quantile(.25)), p75_freight_per_kg=("freight_per_kg", lambda s: s.quantile(.75)),
        median_freight_pct=("freight_pct_value", "median"),
    ).reset_index().query("shipments >= 5")).to_dict("records")
    anomalies = sorted(shipment_records, key=lambda r: r["anomaly_score"], reverse=True)[:250]
    summary = {
        "rows": int(len(df)), "columns": int(len(df.columns)), "arv_rows": int(df["product group"].eq("ARV").sum()),
        "countries": int(df["country"].nunique()), "years": [int(df["year"].min()), int(df["year"].max())],
        "item_value": round(float(df["line item value"].sum()), 2), "freight_cost": round(float(valid_freight["freight cost (usd)"].sum()), 2),
        "median_freight_per_kg": round(float(valid_weight["freight_per_kg"].median()), 2),
        "median_freight_pct": round(float(valid_weight["freight_pct_value"].median()), 2),
        "on_time_rate": round(float(df["on_time"].mean()), 4), "cost_complete_rate": round(float(df["freight cost (usd)"].notna().mean()), 4),
    }
    quality = [
        {"check":"Row identity", "status":"pass", "evidence":f"{df['id'].nunique():,} unique IDs across {len(df):,} rows", "severity":"None"},
        {"check":"Freight completeness", "status":"caution", "evidence":f"{df['freight cost (usd)'].isna().mean():.1%} missing freight cost", "severity":"High for cost modeling"},
        {"check":"Weight completeness", "status":"caution", "evidence":f"{df['weight (kilograms)'].isna().mean():.1%} missing shipment weight", "severity":"High for freight/kg"},
        {"check":"Non-positive values", "status":"caution", "evidence":f"{int(df['line item value'].le(0).sum())} non-positive item values; {int(df['unit price'].le(0).sum())} non-positive unit prices", "severity":"Medium"},
        {"check":"Date coverage", "status":"pass", "evidence":f"Delivery coverage {summary['years'][0]}-{summary['years'][1]}", "severity":"Historical snapshot"},
        {"check":"Model eligibility", "status":"pass", "evidence":f"{model['training_rows'] + model['test_rows']:,} complete rows used; missing-cost rows excluded", "severity":"Documented"},
    ]
    return {"source":{"name":RAW.name,"grain":"One shipment line item","snapshot":"Historical public-health supply chain data","generated_at":pd.Timestamp.now().isoformat()},"summary":summary,"annual":annual,"modes":modes,"countries":countries,"benchmarks":benchmarks,"anomalies":anomalies,"records":shipment_records,"model":model,"quality":quality}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = clean()
    _, _, model = model_freight(df)
    shipment_records = records(df)
    payload = aggregate(df, model, shipment_records)
    (OUT / "pricing_intelligence.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame(shipment_records).to_csv(OUT / "shipment_pricing_features.csv", index=False)
    WEB_DATA.write_text("window.PRICING_DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(json.dumps({"summary":payload["summary"],"model":{k:v for k,v in model.items() if k!="drivers"},"top_drivers":model["drivers"][:6]}, indent=2))


if __name__ == "__main__":
    main()
