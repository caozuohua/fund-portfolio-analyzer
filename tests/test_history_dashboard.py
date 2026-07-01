import csv
from pathlib import Path

from portfolio_analyzer.dashboard import render_dashboard_html
from portfolio_analyzer.history import append_history_records, build_history_records


def sample_holdings():
    return [
        {
            "code": "A",
            "name": "现金基金",
            "type": "货币型",
            "current_nav": 1.01,
            "value": 303000,
            "weight": 30.3,
            "nav_data": {"daily_chg": "0.01"},
        },
        {
            "code": "B",
            "name": "债券基金",
            "type": "债券型",
            "nav": 1.20,
            "value": 350000,
            "weight": 35.0,
        },
    ]


def sample_analysis():
    return {
        "summary": {
            "total_value": 1000000.0,
            "holding_count": 2,
            "rebalance_required": True,
        },
        "allocation": {
            "现金类": {"current_pct": 30.3, "target_pct": 35.0, "drift_pct": -4.7, "status": "within_band"},
            "固收类": {"current_pct": 35.0, "target_pct": 35.0, "drift_pct": 0.0, "status": "within_band"},
            "权益类": {"current_pct": 29.7, "target_pct": 25.0, "drift_pct": 4.7, "status": "within_band"},
            "权益类QDII": {"current_pct": 5.0, "target_pct": 5.0, "drift_pct": 0.0, "status": "within_band"},
        },
        "risk": {
            "top3_weight_pct": 65.3,
            "concentration_level": "medium",
            "max_position": {"code": "B", "name": "债券基金", "weight_pct": 35.0, "value": 350000.0},
        },
        "rebalance_plan": [
            {"asset_class": "现金类", "action": "add", "amount": 47000.0, "reason": "接近目标下沿"}
        ],
        "data_quality": {"fund_nav_success_rate": 100.0},
    }


def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_append_history_records_upserts_nav_and_snapshot_rows(tmp_path):
    nav_path = tmp_path / "fund_nav_history.csv"
    snapshot_path = tmp_path / "portfolio_snapshots.csv"
    records = build_history_records("2026-06-30", sample_holdings(), sample_analysis())

    append_history_records(nav_path, snapshot_path, records)
    append_history_records(nav_path, snapshot_path, records)

    nav_rows = read_csv(nav_path)
    snapshot_rows = read_csv(snapshot_path)

    assert len(nav_rows) == 2
    assert nav_rows[0]["date"] == "2026-06-30"
    assert nav_rows[0]["fund_code"] == "A"
    assert nav_rows[0]["unit_nav"] == "1.01"
    assert nav_rows[1]["unit_nav"] == "1.2"

    assert len(snapshot_rows) == 1
    assert snapshot_rows[0]["total_value"] == "1000000.0"
    assert snapshot_rows[0]["cash_pct"] == "30.3"
    assert snapshot_rows[0]["top3_weight_pct"] == "65.3"
    assert snapshot_rows[0]["rebalance_required"] == "true"


def test_render_dashboard_html_contains_history_charts_and_current_allocation():
    html = render_dashboard_html(
        snapshots=[
            {
                "date": "2026-06-29",
                "total_value": "980000",
                "cash_pct": "40",
                "bond_pct": "30",
                "equity_pct": "25",
                "qdii_pct": "5",
                "top3_weight_pct": "70",
            },
            {
                "date": "2026-06-30",
                "total_value": "1000000",
                "cash_pct": "30.3",
                "bond_pct": "35",
                "equity_pct": "29.7",
                "qdii_pct": "5",
                "top3_weight_pct": "65.3",
            },
        ],
        analysis=sample_analysis(),
    )

    assert "组合总市值趋势" in html
    assert "资产配置趋势" in html
    assert "当前配置 vs 目标配置" in html
    assert "再平衡草案" in html
    assert "2026-06-30" in html
    assert "现金类" in html
