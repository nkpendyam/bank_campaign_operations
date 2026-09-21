"""Build the observed-record analysis for UCI Bank Marketing (additional full)."""

from __future__ import annotations

import hashlib
import io
import json
import math
import sqlite3
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
URL = "https://archive.ics.uci.edu/static/public/222/bank+marketing.zip"
SOURCE_VARIANT = "bank-additional-full.csv"
SOURCE_DOI = "10.24432/C5K306"
SOURCE_LICENSE = "CC BY 4.0"

COLS = [
    "age", "job", "marital", "education", "default", "housing", "loan", "contact", "month", "day_of_week", "duration", "campaign", "pdays", "previous", "poutcome", "emp.var.rate", "cons.price.idx", "cons.conf.idx", "euribor3m", "nr.employed", "y",
]
ENUMS = {
    "job": {"admin.", "blue-collar", "entrepreneur", "housemaid", "management", "retired", "self-employed", "services", "student", "technician", "unemployed", "unknown"},
    "marital": {"divorced", "married", "single", "unknown"},
    "education": {"basic.4y", "basic.6y", "basic.9y", "high.school", "illiterate", "professional.course", "university.degree", "unknown"},
    "default": {"no", "yes", "unknown"},
    "housing": {"no", "yes", "unknown"},
    "loan": {"no", "yes", "unknown"},
    "contact": {"cellular", "telephone"},
    "month": {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"},
    "day_of_week": {"mon", "tue", "wed", "thu", "fri"},
    "poutcome": {"failure", "nonexistent", "success"},
    "y": {"yes", "no"},
}
INTEGER_COLUMNS = ("age", "duration", "campaign", "pdays", "previous")
FLOAT_COLUMNS = ("emp.var.rate", "cons.price.idx", "cons.conf.idx", "euribor3m", "nr.employed")
SQL_OUTPUTS = {
    "contact_pressure": ("contact_pressure.sql", ["contact_band"]),
    "channel": ("channel.sql", ["contact"]),
    "channel_by_month": ("channel_by_month.sql", ["month", "contact"]),
    "prior_outcome": ("prior_outcome.sql", ["poutcome"]),
    "pooled_month": ("pooled_month.sql", ["month"]),
    "pressure_strata": ("pressure_strata.sql", ["contact", "poutcome", "contact_band"]),
}


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Return a standard two-sided 95% Wilson interval for a binomial rate."""
    if not isinstance(successes, int) or isinstance(successes, bool):
        raise ValueError("successes must be a nonnegative integer")
    if not isinstance(total, int) or isinstance(total, bool):
        raise ValueError("total must be a nonnegative integer")
    if successes < 0 or total < 0 or successes > total:
        raise ValueError("successes must be between 0 and total")
    if total == 0:
        return None, None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half_width = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def extract_source(archive_bytes: bytes, destination: Path | str) -> Path:
    """Read only the expected members from UCI's nested archive into destination."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as outer:
        if "bank-additional.zip" not in outer.namelist():
            raise ValueError("source archive is missing bank-additional.zip")
        nested_bytes = outer.read("bank-additional.zip")
    with zipfile.ZipFile(io.BytesIO(nested_bytes)) as nested:
        csv_member = "bank-additional/bank-additional-full.csv"
        names_member = "bank-additional/bank-additional-names.txt"
        missing = [member for member in (csv_member, names_member) if member not in nested.namelist()]
        if missing:
            raise ValueError(f"nested archive is missing expected members: {missing}")
        (destination / SOURCE_VARIANT).write_bytes(nested.read(csv_member))
        (destination / "bank-additional-names.txt").write_bytes(nested.read(names_member))
    return destination / SOURCE_VARIANT


def ensure_source(raw: Path | str = RAW) -> Path:
    raw = Path(raw)
    raw.mkdir(parents=True, exist_ok=True)
    csv_path = raw / SOURCE_VARIANT
    names_path = raw / "bank-additional-names.txt"
    if csv_path.exists() and names_path.exists():
        return csv_path
    archive_path = raw / "bank-marketing.zip"
    if not archive_path.exists():
        with urllib.request.urlopen(URL, timeout=60) as response:
            archive_path.write_bytes(response.read())
    return extract_source(archive_path.read_bytes(), raw)


def prepare(df: pd.DataFrame, expected: int | None = 41188) -> pd.DataFrame:
    """Validate source records before adding analysis-only fields."""
    if list(df.columns) != COLS:
        raise ValueError("unexpected 21-column schema")
    if expected is not None and len(df) != expected:
        raise ValueError(f"unexpected observed record count: {len(df)}")
    prepared = df.copy()
    for column, values in ENUMS.items():
        invalid = set(prepared[column].astype(str)) - values
        if invalid:
            raise ValueError(f"invalid {column} values: {sorted(invalid)}")
    for column in INTEGER_COLUMNS:
        values = pd.to_numeric(prepared[column], errors="coerce")
        if values.isna().any() or not (values % 1 == 0).all():
            raise ValueError(f"invalid integer values in {column}")
        if (values < 0).any() or (column == "age" and (values <= 0).any()) or (column == "campaign" and (values < 1).any()):
            raise ValueError(f"invalid range in {column}")
        prepared[column] = values.astype("int64")
    for column in FLOAT_COLUMNS:
        values = pd.to_numeric(prepared[column], errors="coerce")
        if values.isna().any() or not values.map(math.isfinite).all():
            raise ValueError(f"invalid finite numeric values in {column}")
        prepared[column] = values.astype("float64")
    prepared.insert(0, "row_id", range(1, len(prepared) + 1))
    prepared["subscribed"] = (prepared["y"] == "yes").astype("int64")
    prepared["contact_band"] = pd.cut(prepared["campaign"], [0, 1, 2, 3, 5, float("inf")], labels=["1", "2", "3", "4-5", "6+"], ordered=True).astype("string")
    prepared["prior_contacted"] = (prepared["pdays"] != 999).astype("int64")
    prepared["pdays_clean"] = prepared["pdays"].mask(prepared["pdays"] == 999).astype("Int64")
    return prepared


def load(path: Path | str, expected: int | None = 41188) -> pd.DataFrame:
    return prepare(pd.read_csv(path, sep=";", keep_default_na=False), expected=expected)


def quality_controls(raw: pd.DataFrame, df: pd.DataFrame) -> dict:
    duplicate_rows = int(raw.duplicated().sum())
    duplicate_set = raw.loc[raw.duplicated(keep=False)]
    known_recency = df["pdays_clean"].dropna()
    return {
        "records": int(len(df)), "subscriptions": int(df["subscribed"].sum()), "subscription_rate": float(df["subscribed"].mean()),
        "exact_duplicate_rows": duplicate_rows, "duplicate_groups": int(len(duplicate_set.drop_duplicates())), "duplicate_affected_rows": int(len(duplicate_set)),
        "median_campaign": float(df["campaign"].median()),
        "unknown_counts": {column: int((df[column] == "unknown").sum()) for column in ENUMS},
        "history_conflicts": {"pdays_never_but_previous_positive": int(((df["pdays"] == 999) & (df["previous"] > 0)).sum())},
        "missing_cells": int(raw.isna().sum().sum()), "known_recency_records": int(known_recency.shape[0]),
        "mean_known_recency_days": float(known_recency.mean()) if not known_recency.empty else None,
    }


def _pandas_aggregate(df: pd.DataFrame, group_keys: list[str]) -> pd.DataFrame:
    grouped = df.groupby(group_keys, dropna=False, observed=True)
    result = grouped.agg(records=("row_id", "size"), subscriptions=("subscribed", "sum"), reported_contacts=("campaign", "sum")).reset_index()
    result["subscription_rate"] = result["subscriptions"] / result["records"]
    return result


def _assert_aggregate(name: str, result: pd.DataFrame, expected: pd.DataFrame, group_keys: list[str], total_records: int, total_subscriptions: int) -> None:
    required = group_keys + ["records", "subscriptions", "subscription_rate", "reported_contacts"]
    if list(result.columns) != required:
        raise AssertionError(f"{name}: unexpected SQL output columns")
    if int(result["records"].sum()) != total_records or int(result["subscriptions"].sum()) != total_subscriptions:
        raise AssertionError(f"{name}: SQL partition totals do not match observed records")
    actual = result.sort_values(group_keys, kind="stable").reset_index(drop=True)
    independent = expected[required].sort_values(group_keys, kind="stable").reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(actual, independent, check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-12)
    except AssertionError as error:
        raise AssertionError(f"{name}: SQL does not match independent pandas aggregation") from error


def run_aggregates(df: pd.DataFrame, cx: sqlite3.Connection, sql_dir: Path | str = ROOT / "sql") -> list[str]:
    """Execute external SQL artifacts, validate each, and write its report."""
    sql_dir = Path(sql_dir)
    REPORTS.mkdir(parents=True, exist_ok=True)
    checks: list[str] = []
    for output_name, (sql_file, group_keys) in SQL_OUTPUTS.items():
        result = pd.read_sql_query((sql_dir / sql_file).read_text(encoding="utf-8"), cx)
        _assert_aggregate(output_name, result, _pandas_aggregate(df, group_keys), group_keys, len(df), int(df["subscribed"].sum()))
        intervals = [wilson(int(row.subscriptions), int(row.records)) for row in result.itertuples()]
        result["ci_low"] = [item[0] for item in intervals]
        result["ci_high"] = [item[1] for item in intervals]
        result["small_samples"] = result["records"] < 30
        result.to_csv(REPORTS / f"{output_name}.csv", index=False)
        checks.append(f"{output_name}: SQL partition totals and independent pandas aggregation matched observed records and subscriptions")
    return checks


def main() -> None:
    source = ensure_source()
    raw = pd.read_csv(source, sep=";", keep_default_na=False)
    df = prepare(raw)
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUT / "campaign.sqlite") as connection:
        df.to_sql("observations", connection, if_exists="replace", index=False)
        checks = run_aggregates(df, connection)
    unknowns = pd.DataFrame([(column, int((df[column] == "unknown").sum()), float((df[column] == "unknown").mean())) for column in ENUMS], columns=["field", "unknown_records", "unknown_rate"])
    unknowns.to_csv(REPORTS / "unknowns.csv", index=False)
    manifest = {
        "source": {"url": URL, "variant": SOURCE_VARIANT, "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "doi": SOURCE_DOI, "license": SOURCE_LICENSE},
        "controls": quality_controls(raw, df),
        "checks": checks + ["schema: exact ordered 21-column source schema validated", "enums: all dictionary categorical values, including y yes/no before mapping, validated", "numerics: finite values and integer/range constraints validated after coercion", "source rows: observed 41,188 records retained without deduplication"],
        "limitations": ["Rows are campaign contact records; the source has no unique client identifier or contact date, so client-level and chronological claims are not supported.", "The calendar month is a pooled month label across 2008-2010, not a dated monthly time series.", "The pdays value 999 denotes no prior contact in the documented field; pdays=999 with previous>0 is retained and flagged rather than reconciled.", "These descriptive aggregates do not establish prediction quality, causality, or treatment effects."],
    }
    (REPORTS / "validation.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
