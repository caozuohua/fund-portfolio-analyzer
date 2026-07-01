"""Static HTML dashboard rendering for phase-one portfolio history."""

from __future__ import annotations

import html
from typing import Any


COLORS = {
    "现金类": "#2563eb",
    "固收类": "#059669",
    "权益类": "#dc2626",
    "权益类QDII": "#7c3aed",
    "目标": "#64748b",
}


def render_dashboard_html(snapshots: list[dict[str, Any]], analysis: dict[str, Any]) -> str:
    latest = snapshots[-1] if snapshots else {}
    allocation = analysis.get("allocation", {})
    rebalance_plan = analysis.get("rebalance_plan", [])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>基金组合看板</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #111827; background: #f8fafc; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 28px 18px 44px; }}
    h1 {{ margin: 0 0 4px; font-size: 28px; }}
    h2 {{ margin: 0 0 14px; font-size: 18px; }}
    .muted {{ color: #64748b; }}
    .grid {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); margin: 18px 0; }}
    .panel {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; box-shadow: 0 1px 2px rgba(15,23,42,.05); }}
    .metric {{ font-size: 26px; font-weight: 700; margin-top: 8px; }}
    svg {{ width: 100%; height: auto; display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
    th {{ color: #475569; font-weight: 600; background: #f8fafc; }}
    .tag {{ display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eef2ff; color: #3730a3; font-size: 12px; }}
  </style>
</head>
<body>
<main>
  <h1>基金组合看板</h1>
  <div class="muted">最新数据日期：{html.escape(str(latest.get("date", "暂无历史数据")))}</div>
  <section class="grid">
    <div class="panel"><h2>组合总市值</h2><div class="metric">¥{_money(latest.get("total_value", 0))}</div></div>
    <div class="panel"><h2>前三大持仓占比</h2><div class="metric">{_pct(latest.get("top3_weight_pct", 0))}%</div></div>
    <div class="panel"><h2>是否触发再平衡</h2><div class="metric">{_yes_no(analysis.get("summary", {}).get("rebalance_required"))}</div></div>
  </section>
  <section class="panel">
    <h2>组合总市值趋势</h2>
    {_line_chart(snapshots, "total_value", "#0f766e")}
  </section>
  <section class="panel">
    <h2>资产配置趋势</h2>
    {_allocation_trend(snapshots)}
  </section>
  <section class="panel">
    <h2>当前配置 vs 目标配置</h2>
    {_allocation_bars(allocation)}
  </section>
  <section class="panel">
    <h2>再平衡草案</h2>
    {_rebalance_table(rebalance_plan)}
  </section>
</main>
</body>
</html>"""


def _line_chart(rows: list[dict[str, Any]], field: str, color: str) -> str:
    if not rows:
        return '<p class="muted">暂无历史数据。</p>'
    width, height, pad = 760, 220, 28
    values = [_float(row.get(field)) for row in rows]
    dates = [str(row.get("date", "")) for row in rows]
    min_v, max_v = min(values), max(values)
    span = max(max_v - min_v, 1)
    points = []
    for idx, value in enumerate(values):
        x = pad + idx * ((width - pad * 2) / max(len(values) - 1, 1))
        y = height - pad - ((value - min_v) / span) * (height - pad * 2)
        points.append(f"{x:.1f},{y:.1f}")
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="组合总市值趋势">
      <polyline fill="none" stroke="{color}" stroke-width="3" points="{' '.join(points)}" />
      <text x="{pad}" y="{height - 6}" fill="#64748b" font-size="12">{html.escape(dates[0])}</text>
      <text x="{width - pad - 88}" y="{height - 6}" fill="#64748b" font-size="12">{html.escape(dates[-1])}</text>
      <text x="{pad}" y="16" fill="#64748b" font-size="12">¥{_money(max_v)}</text>
      <text x="{pad}" y="{height - pad - 4}" fill="#64748b" font-size="12">¥{_money(min_v)}</text>
    </svg>"""


def _allocation_trend(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<p class="muted">暂无历史数据。</p>'
    latest = rows[-8:]
    table_rows = []
    for row in latest:
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('date', '')))}</td>"
            f"<td>{_pct(row.get('cash_pct'))}%</td>"
            f"<td>{_pct(row.get('bond_pct'))}%</td>"
            f"<td>{_pct(row.get('equity_pct'))}%</td>"
            f"<td>{_pct(row.get('qdii_pct'))}%</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>日期</th><th>现金</th><th>固收</th><th>权益</th><th>QDII</th></tr></thead><tbody>" + "".join(table_rows) + "</tbody></table>"


def _allocation_bars(allocation: dict[str, dict[str, Any]]) -> str:
    if not allocation:
        return '<p class="muted">暂无配置数据。</p>'
    rows = []
    for asset_class, item in allocation.items():
        current = _float(item.get("current_pct"))
        target = _float(item.get("target_pct"))
        current_width = min(max(current, 0), 100)
        target_width = min(max(target, 0), 100)
        color = COLORS.get(asset_class, "#334155")
        rows.append(f"""
        <tr>
          <td>{html.escape(asset_class)}</td>
          <td>{current:.1f}%</td>
          <td>{target:.1f}%</td>
          <td>
            <div style="height:10px;background:#e5e7eb;border-radius:5px;position:relative">
              <div style="height:10px;width:{current_width:.1f}%;background:{color};border-radius:5px"></div>
              <div style="position:absolute;left:{target_width:.1f}%;top:-3px;width:2px;height:16px;background:{COLORS['目标']}"></div>
            </div>
          </td>
        </tr>""")
    return "<table><thead><tr><th>类别</th><th>当前</th><th>目标</th><th>偏离图</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _rebalance_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="muted">当前主要资产类别均在阈值内。</p>'
    rows = []
    for item in items:
        action = "减配" if item.get("action") == "reduce" else "增配"
        rows.append(
            f"<tr><td>{html.escape(str(item.get('asset_class', '')))}</td>"
            f"<td><span class=\"tag\">{action}</span></td>"
            f"<td>¥{_money(item.get('amount', 0))}</td>"
            f"<td>{html.escape(str(item.get('reason', '')))}</td></tr>"
        )
    return "<table><thead><tr><th>类别</th><th>动作</th><th>金额</th><th>原因</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _money(value: Any) -> str:
    return f"{_float(value):,.0f}"


def _pct(value: Any) -> str:
    return f"{_float(value):.1f}"


def _yes_no(value: Any) -> str:
    return "是" if bool(value) else "否"
