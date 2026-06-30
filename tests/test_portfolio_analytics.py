import math

from portfolio_analyzer.analytics import build_portfolio_analysis


def sample_config():
    return {
        "style": "保守",
        "risk_tolerance": "最大回撤<10%",
        "rebalance_threshold": 5,
        "target_allocation_conservative": {
            "现金类": {"target": 35},
            "固收类": {"target": 35},
            "权益类": {"target": 25},
            "权益类QDII": {"target": 5},
        },
    }


def sample_holdings():
    return [
        {"code": "A", "name": "现金基金", "type": "货币型", "value": 450000, "shares": 450000, "current_nav": 1},
        {"code": "B", "name": "债券基金", "type": "债券型", "value": 250000, "shares": 250000, "current_nav": 1},
        {"code": "C", "name": "红利基金", "type": "股票型", "value": 250000, "shares": 250000, "current_nav": 1},
        {"code": "D", "name": "QDII基金", "type": "股票型QDII", "value": 50000, "shares": 50000, "current_nav": 1},
    ]


def test_build_portfolio_analysis_calculates_allocations_and_rebalance_plan():
    analysis = build_portfolio_analysis(sample_config(), sample_holdings(), {}, success_count=3, fail_count=1)

    assert analysis["summary"]["total_value"] == 1000000
    assert analysis["allocation"]["现金类"]["current_pct"] == 45
    assert analysis["allocation"]["固收类"]["current_pct"] == 25
    assert analysis["allocation"]["现金类"]["status"] == "overweight"
    assert analysis["allocation"]["固收类"]["status"] == "underweight"

    actions = {item["asset_class"]: item for item in analysis["rebalance_plan"]}
    assert actions["现金类"]["action"] == "reduce"
    assert actions["现金类"]["amount"] == 100000
    assert actions["固收类"]["action"] == "add"
    assert actions["固收类"]["amount"] == 100000
    assert "权益类" not in actions

    assert analysis["risk"]["top3_weight_pct"] == 95
    assert analysis["risk"]["max_position"]["code"] == "A"
    assert analysis["data_quality"]["fund_nav_success_rate"] == 75


def test_build_portfolio_analysis_adds_market_signals_and_ai_context():
    index_data = {
        "沪深300": {"price": 4100, "chg_5d": 2.1, "chg_20d": 7.5, "rsi": 74},
        "中证500": {"price": 6200, "chg_5d": -1.0, "chg_20d": -3.0, "rsi": 38},
    }

    analysis = build_portfolio_analysis(sample_config(), sample_holdings(), index_data, success_count=4, fail_count=0)

    assert analysis["market"]["沪深300"]["signal"] == "overheated"
    assert analysis["market"]["中证500"]["signal"] == "weak"
    assert analysis["ai_context"]["decision_rules"]["rebalance_threshold_pct"] == 5
    assert "现金类" in analysis["ai_context"]["focus_questions"][0]
    assert math.isclose(analysis["summary"]["investable_cash_pct"], 45)
