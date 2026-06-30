"""Deterministic portfolio diagnostics used before AI interpretation."""

from __future__ import annotations

from typing import Any


TYPE_TO_ASSET_CLASS = {
    "货币型": "现金类",
    "债券型": "固收类",
    "混合型": "权益类",
    "股票型": "权益类",
    "指数型": "权益类",
    "股票型QDII": "权益类QDII",
    "QDII": "权益类QDII",
}

DEFAULT_TARGETS = {
    "现金类": 35.0,
    "固收类": 35.0,
    "权益类": 25.0,
    "权益类QDII": 5.0,
}


def asset_class_for(fund_type: str) -> str:
    return TYPE_TO_ASSET_CLASS.get(fund_type, fund_type or "未分类")


def _round_money(value: float) -> float:
    return round(float(value), 2)


def _round_pct(value: float) -> float:
    return round(float(value), 2)


def _extract_targets(config: dict[str, Any]) -> dict[str, float]:
    raw_targets = config.get("target_allocation_conservative") or {}
    targets = DEFAULT_TARGETS.copy()
    for asset_class, data in raw_targets.items():
        if isinstance(data, dict) and "target" in data:
            targets[asset_class] = float(data["target"])
        elif isinstance(data, (int, float)):
            targets[asset_class] = float(data)
    return targets


def _market_signal(data: dict[str, Any]) -> str:
    rsi = float(data.get("rsi", 50) or 50)
    chg_20d = float(data.get("chg_20d", 0) or 0)
    if rsi >= 70 and chg_20d > 5:
        return "overheated"
    if rsi <= 40 or chg_20d < -2:
        return "weak"
    if chg_20d > 2:
        return "positive"
    return "neutral"


def build_portfolio_analysis(
    config: dict[str, Any],
    holdings: list[dict[str, Any]],
    index_data: dict[str, dict[str, Any]],
    *,
    success_count: int,
    fail_count: int,
) -> dict[str, Any]:
    """Build deterministic diagnostics and a structured AI context."""
    total_value = sum(float(h.get("value") or 0) for h in holdings)
    targets = _extract_targets(config)
    threshold = float(config.get("rebalance_threshold") or 5)

    class_values: dict[str, float] = {asset_class: 0.0 for asset_class in targets}
    enriched_holdings = []
    for holding in holdings:
        value = float(holding.get("value") or 0)
        asset_class = asset_class_for(str(holding.get("type", "")))
        class_values[asset_class] = class_values.get(asset_class, 0.0) + value
        enriched = dict(holding)
        enriched["asset_class"] = asset_class
        enriched["weight"] = _round_pct(value / total_value * 100) if total_value else 0
        enriched_holdings.append(enriched)

    allocation = {}
    rebalance_plan = []
    for asset_class, target_pct in targets.items():
        current_value = class_values.get(asset_class, 0.0)
        current_pct = current_value / total_value * 100 if total_value else 0
        drift_pct = current_pct - target_pct
        target_value = total_value * target_pct / 100 if total_value else 0
        drift_value = current_value - target_value
        if drift_pct >= threshold:
            status = "overweight"
            rebalance_plan.append({
                "asset_class": asset_class,
                "action": "reduce",
                "amount": _round_money(abs(drift_value)),
                "reason": f"当前占比高于目标 {abs(drift_pct):.1f} 个百分点，超过 {threshold:.1f}% 阈值",
            })
        elif drift_pct <= -threshold:
            status = "underweight"
            rebalance_plan.append({
                "asset_class": asset_class,
                "action": "add",
                "amount": _round_money(abs(drift_value)),
                "reason": f"当前占比低于目标 {abs(drift_pct):.1f} 个百分点，超过 {threshold:.1f}% 阈值",
            })
        else:
            status = "within_band"

        allocation[asset_class] = {
            "current_value": _round_money(current_value),
            "current_pct": _round_pct(current_pct),
            "target_pct": _round_pct(target_pct),
            "drift_pct": _round_pct(drift_pct),
            "drift_value": _round_money(drift_value),
            "status": status,
        }

    sorted_holdings = sorted(enriched_holdings, key=lambda h: float(h.get("value") or 0), reverse=True)
    top3_weight = sum(float(h.get("weight") or 0) for h in sorted_holdings[:3])
    max_position = sorted_holdings[0] if sorted_holdings else {}

    market = {}
    for name, data in index_data.items():
        if "error" in data:
            market[name] = {"signal": "unavailable", "error": data.get("error")}
            continue
        market[name] = {
            "price": data.get("price"),
            "chg_5d": _round_pct(data.get("chg_5d", 0)),
            "chg_20d": _round_pct(data.get("chg_20d", 0)),
            "rsi": _round_pct(data.get("rsi", 0)),
            "signal": _market_signal(data),
        }

    data_total = success_count + fail_count
    success_rate = success_count / data_total * 100 if data_total else 0
    focus_questions = _build_focus_questions(allocation, rebalance_plan, market)

    return {
        "summary": {
            "style": config.get("style", "保守"),
            "risk_tolerance": config.get("risk_tolerance", "最大回撤<10%"),
            "total_value": _round_money(total_value),
            "holding_count": len(holdings),
            "investable_cash_pct": allocation.get("现金类", {}).get("current_pct", 0),
            "rebalance_required": bool(rebalance_plan),
        },
        "holdings": sorted_holdings,
        "allocation": allocation,
        "rebalance_plan": rebalance_plan,
        "risk": {
            "top3_weight_pct": _round_pct(top3_weight),
            "max_position": {
                "code": max_position.get("code"),
                "name": max_position.get("name"),
                "weight_pct": max_position.get("weight", 0),
                "value": _round_money(max_position.get("value", 0)),
            },
            "concentration_level": "high" if top3_weight >= 70 else ("medium" if top3_weight >= 50 else "low"),
        },
        "market": market,
        "data_quality": {
            "fund_nav_success_count": success_count,
            "fund_nav_fail_count": fail_count,
            "fund_nav_success_rate": _round_pct(success_rate),
        },
        "ai_context": {
            "decision_rules": {
                "risk_style": config.get("style", "保守"),
                "rebalance_threshold_pct": threshold,
                "avoid_chasing_hot_themes": True,
                "prefer_capital_preservation": True,
            },
            "focus_questions": focus_questions,
        },
    }


def _build_focus_questions(
    allocation: dict[str, dict[str, Any]],
    rebalance_plan: list[dict[str, Any]],
    market: dict[str, dict[str, Any]],
) -> list[str]:
    questions = []
    for item in rebalance_plan:
        action = "减配" if item["action"] == "reduce" else "增配"
        questions.append(
            f"{item['asset_class']}需要{action}约{item['amount']:,.0f}元，是否可通过存量基金内部调整完成？"
        )
    overheated = [name for name, data in market.items() if data.get("signal") == "overheated"]
    weak = [name for name, data in market.items() if data.get("signal") == "weak"]
    if overheated:
        questions.append(f"{'、'.join(overheated)}偏热，权益加仓是否应延后或分批？")
    if weak:
        questions.append(f"{'、'.join(weak)}偏弱，是否需要降低波动资产的新增金额？")
    if not questions:
        questions.append("本周组合是否仍在目标配置带内，是否应维持不操作？")
    return questions
