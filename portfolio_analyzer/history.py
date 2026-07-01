"""CSV history persistence for portfolio snapshots and fund NAVs."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


NAV_FIELDS = ["date", "fund_code", "fund_name", "fund_type", "unit_nav", "daily_return_pct", "value", "weight_pct"]
SNAPSHOT_FIELDS = [
    "date",
    "total_value",
    "holding_count",
    "cash_pct",
    "bond_pct",
    "equity_pct",
    "qdii_pct",
    "top3_weight_pct",
    "max_position_code",
    "max_position_name",
    "max_position_weight_pct",
    "rebalance_required",
    "fund_nav_success_rate",
]


def build_history_records(
    report_date: str,
    holdings: list[dict[str, Any]],
    portfolio_analysis: dict[str, Any],
) -> dict[str, list[dict[str, Any]] | dict[str, Any]]:
    nav_rows = []
    for holding in holdings:
        nav_rows.append({
            "date": report_date,
            "fund_code": holding.get("code", ""),
            "fund_name": holding.get("name", ""),
            "fund_type": holding.get("type", ""),
            "unit_nav": holding.get("current_nav", holding.get("nav", "")),
            "daily_return_pct": (holding.get("nav_data") or {}).get("daily_chg", ""),
            "value": round(float(holding.get("value") or 0), 2),
            "weight_pct": round(float(holding.get("weight") or 0), 2),
        })

    allocation = portfolio_analysis.get("allocation", {})
    max_position = portfolio_analysis.get("risk", {}).get("max_position", {})
    snapshot = {
        "date": report_date,
        "total_value": portfolio_analysis.get("summary", {}).get("total_value", 0),
        "holding_count": portfolio_analysis.get("summary", {}).get("holding_count", 0),
        "cash_pct": _allocation_pct(allocation, "现金类"),
        "bond_pct": _allocation_pct(allocation, "固收类"),
        "equity_pct": _allocation_pct(allocation, "权益类"),
        "qdii_pct": _allocation_pct(allocation, "权益类QDII"),
        "top3_weight_pct": portfolio_analysis.get("risk", {}).get("top3_weight_pct", 0),
        "max_position_code": max_position.get("code", ""),
        "max_position_name": max_position.get("name", ""),
        "max_position_weight_pct": max_position.get("weight_pct", 0),
        "rebalance_required": "true" if portfolio_analysis.get("summary", {}).get("rebalance_required") else "false",
        "fund_nav_success_rate": portfolio_analysis.get("data_quality", {}).get("fund_nav_success_rate", 0),
    }
    return {"nav_rows": nav_rows, "snapshot": snapshot}


def append_history_records(
    nav_path: str | Path,
    snapshot_path: str | Path,
    records: dict[str, list[dict[str, Any]] | dict[str, Any]],
) -> None:
    nav_rows = list(records.get("nav_rows", []))
    snapshot = dict(records.get("snapshot", {}))
    _upsert_rows(Path(nav_path), NAV_FIELDS, nav_rows, key_fields=["date", "fund_code"])
    _upsert_rows(Path(snapshot_path), SNAPSHOT_FIELDS, [snapshot], key_fields=["date"])


def read_snapshots(snapshot_path: str | Path) -> list[dict[str, str]]:
    path = Path(snapshot_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _allocation_pct(allocation: dict[str, dict[str, Any]], asset_class: str) -> float:
    return round(float((allocation.get(asset_class) or {}).get("current_pct") or 0), 2)


def _upsert_rows(
    path: Path,
    fieldnames: list[str],
    new_rows: list[dict[str, Any]],
    *,
    key_fields: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as f:
            existing_rows = list(csv.DictReader(f))

    by_key = {_row_key(row, key_fields): row for row in existing_rows}
    for row in new_rows:
        normalized = {field: _stringify(row.get(field, "")) for field in fieldnames}
        by_key[_row_key(normalized, key_fields)] = normalized

    rows = sorted(by_key.values(), key=lambda row: tuple(row.get(field, "") for field in key_fields))
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row_key(row: dict[str, Any], key_fields: list[str]) -> tuple[str, ...]:
    return tuple(str(row.get(field, "")) for field in key_fields)


def _stringify(value: Any) -> str:
    if isinstance(value, float):
        return str(round(value, 4)).rstrip("0").rstrip(".") if value % 1 else str(value)
    return str(value)
