#!/usr/bin/env python3
"""
基金持仓周报分析脚本
使用 akshare 拉取基金净值 + 市场行情，生成结构化报告
"""
import json
import os
import sys
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def load_config():
    """加载持仓配置"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'holdings.json')
    with open(config_path) as f:
        return json.load(f)

def get_fund_nav(fund_code, days=120):
    """获取基金净值历史"""
    tries = [
        lambda: ak.fund_open_fund_daily_em(symbol=fund_code),
        lambda: ak.fund_etf_fund_daily_em(symbol=fund_code),
    ]
    for fn in tries:
        try:
            df = fn()
            if df is not None and len(df) >= 10:
                # 找净值列
                nav_col = None
                for col in df.columns:
                    if '单位净值' in col or '累计净值' in col:
                        nav_col = col
                        break
                if nav_col is None:
                    nav_col = df.columns[-1]
                
                close = df[nav_col].astype(float)
                close = close[close > 0]
                return close
        except Exception:
            continue
    return None

def calc_metrics(close):
    """计算技术指标"""
    if len(close) < 20:
        return None
    
    price = close.iloc[-1]
    
    # 均线
    ma5 = close.rolling(5).mean().iloc[-1] if len(close) >= 5 else price
    ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else price
    
    # RSI(14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    
    # 涨跌幅
    chg_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0
    chg_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
    
    return {
        'price': price,
        'ma5': ma5,
        'ma20': ma20,
        'rsi': rsi,
        'chg_5d': chg_5d,
        'chg_20d': chg_20d,
        'trend': '多头排列' if ma5 > ma20 else '空头排列',
        'rsi_tag': '超买' if rsi > 70 else ('超卖' if rsi < 30 else '中性'),
    }

def get_index_data():
    """获取A股指数数据"""
    indices = {
        '000300': '沪深300',
        '399006': '创业板指',
        '000905': '中证500',
        '000852': '中证1000',
    }
    results = {}
    for code, name in indices.items():
        try:
            df = ak.index_zh_a_hist(symbol=code, period='daily',
                                    start_date=(datetime.now() - timedelta(days=90)).strftime('%Y%m%d'),
                                    end_date=datetime.now().strftime('%Y%m%d'))
            if df is not None and len(df) >= 20:
                close_col = [c for c in df.columns if '收盘' in c][0]
                close = df[close_col].astype(float)
                chg_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
                chg_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100
                
                # RSI
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]
                
                results[name] = {
                    'price': close.iloc[-1],
                    'chg_5d': chg_5d,
                    'chg_20d': chg_20d,
                    'rsi': rsi,
                }
        except Exception as e:
            results[name] = {'error': str(e)[:50]}
    return results

def generate_report(config, holdings_data, index_data):
    """生成 Markdown 报告"""
    total_value = sum(h['value'] for h in holdings_data)
    report_date = datetime.now().strftime('%Y-%m-%d')
    
    lines = []
    lines.append(f"# 基金持仓周报 - {report_date}")
    lines.append("")
    lines.append("## 一、组合总览")
    lines.append("")
    lines.append(f"- **总市值**: ¥{total_value:,.2f}")
    lines.append(f"- **报告日期**: {report_date}")
    lines.append("")
    
    # 资产配置
    type_map = {'货币型': '现金类', '债券型': '固收类', '混合型': '权益类', '股票型': '权益类', '股票型QDII': '权益类QDII'}
    type_values = {}
    for h in holdings_data:
        cat = type_map.get(h['type'], h['type'])
        type_values[cat] = type_values.get(cat, 0) + h['value']
    
    target = config['target_allocation_conservative']
    lines.append("### 资产配置")
    lines.append("")
    lines.append("| 类别 | 当前占比 | 目标占比 | 状态 |")
    lines.append("|------|---------|---------|------|")
    for cat in ['现金类', '固收类', '权益类', '权益类QDII']:
        current = type_values.get(cat, 0) / total_value * 100
        tgt = target.get(cat, {}).get('target', 0)
        diff = current - tgt
        flag = '✅' if abs(diff) < 3 else ('⬆️' if diff > 0 else '⬇️')
        lines.append(f"| {cat} | {current:.1f}% | {tgt}% | {flag} ({diff:+.1f}%) |")
    lines.append("")
    
    # 各基金表现
    lines.append("## 二、各基金表现")
    lines.append("")
    for h in sorted(holdings_data, key=lambda x: -x['value']):
        lines.append(f"### {h['name']} ({h['code']})")
        lines.append("")
        lines.append(f"- **市值**: ¥{h['value']:,.2f} ({h['value']/total_value*100:.1f}%)")
        lines.append(f"- **类型**: {h['type']}")
        
        if h.get('metrics'):
            m = h['metrics']
            lines.append(f"- **净值**: {m['price']:.4f}")
            lines.append(f"- **周涨跌**: {m['chg_5d']:+.2f}%")
            lines.append(f"- **月涨跌**: {m['chg_20d']:+.2f}%")
            lines.append(f"- **RSI(14)**: {m['rsi']:.0f} ({m['rsi_tag']})")
            lines.append(f"- **趋势**: {m['trend']}")
        else:
            lines.append("- *数据获取失败或货币基金*")
        lines.append("")
    
    # 市场环境
    lines.append("## 三、市场环境")
    lines.append("")
    for name, data in index_data.items():
        if 'error' not in data:
            lines.append(f"- **{name}**: {data['price']:.2f} | 周: {data['chg_5d']:+.1f}% | 月: {data['chg_20d']:+.1f}% | RSI: {data['rsi']:.0f}")
        else:
            lines.append(f"- **{name}**: 数据获取失败")
    lines.append("")
    
    return '\n'.join(lines)

def main():
    print("🔍 开始拉取基金数据...")
    
    # 加载配置
    config = load_config()
    holdings = config['holdings']
    
    # 获取各基金净值
    print(f"📊 共 {len(holdings)} 只基金待分析")
    total_value = 0
    for i, h in enumerate(holdings):
        print(f"  [{i+1}/{len(holdings)}] {h['name']} ({h['code']})...")
        
        # 计算市值
        nav = h.get('nav', 1.0)
        value = h['shares'] * nav
        h['value'] = value
        total_value += value
        
        # 获取历史数据
        close = get_fund_nav(h['code'])
        if close is not None:
            metrics = calc_metrics(close)
            if metrics:
                h['metrics'] = metrics
                # 用最新净值更新市值
                h['value'] = h['shares'] * metrics['price']
                total_value = sum(hh.get('value', hh['shares'] * hh.get('nav', 1.0)) for hh in holdings[:i+1])
        
    # 更新占比
    for h in holdings:
        h['weight'] = h['value'] / total_value * 100
    
    # 获取指数数据
    print("\n📈 获取A股指数数据...")
    index_data = get_index_data()
    
    # 生成报告
    print("\n📝 生成分析报告...")
    report = generate_report(config, holdings, index_data)
    
    # 保存报告
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    report_path = os.path.join(output_dir, f"report_{datetime.now().strftime('%Y%m%d')}.md")
    with open(report_path, 'w') as f:
        f.write(report)
    
    # 同时保存最新数据 JSON
    data_path = os.path.join(output_dir, 'latest_data.json')
    with open(data_path, 'w') as f:
        json.dump({
            'date': datetime.now().isoformat(),
            'total_value': total_value,
            'holdings': [{k: v for k, v in h.items() if k != 'metrics'} for h in holdings],
            'index': index_data,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 报告已生成: {report_path}")
    print(f"✅ 数据已保存: {data_path}")
    
    # 输出报告摘要到 stdout（供 AI 分析使用）
    print("\n" + "="*60)
    print(report)
    
    return report_path

if __name__ == '__main__':
    main()
