#!/usr/bin/env python3
"""
基金持仓周报分析脚本 - 适配 akshare 新版 API
"""
import json
import os
import sys
import time
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from portfolio_analyzer.analytics import build_portfolio_analysis

def load_config():
    """加载持仓配置"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'holdings.json')
    with open(config_path) as f:
        return json.load(f)

def get_all_fund_nav():
    """获取全部开放式基金最新净值（日频）"""
    print("  拉取开放式基金净值...")
    t0 = time.time()
    df = ak.fund_open_fund_daily_em()
    print(f"  完成，{len(df)} 条，耗时 {time.time()-t0:.1f}s")
    return df

def get_money_fund_nav():
    """获取货币基金净值"""
    print("  拉取货币基金净值...")
    t0 = time.time()
    try:
        df = ak.fund_money_fund_daily_em()
        print(f"  完成，{len(df)} 条，耗时 {time.time()-t0:.1f}s")
        return df
    except Exception as e:
        print(f"  货币基金接口失败: {e}")
        return pd.DataFrame()

def get_etf_fund_nav():
    """获取ETF基金净值"""
    print("  拉取ETF基金净值...")
    t0 = time.time()
    try:
        df = ak.fund_etf_fund_daily_em()
        print(f"  完成，{len(df)} 条，耗时 {time.time()-t0:.1f}s")
        return df
    except Exception as e:
        print(f"  ETF接口失败: {e}")
        return pd.DataFrame()

def match_fund(code, open_fund_df, money_fund_df, etf_df):
    """在数据集中查找基金"""
    # 先查开放式基金
    match = open_fund_df[open_fund_df['基金代码'] == code]
    if len(match) > 0:
        return match.iloc[0].to_dict(), 'open'
    
    # 查货币基金
    if len(money_fund_df) > 0:
        match = money_fund_df[money_fund_df.iloc[:, 0].astype(str).str.contains(code)]
        if len(match) > 0:
            return match.iloc[0].to_dict(), 'money'
    
    # 查ETF
    if len(etf_df) > 0:
        match = etf_df[etf_df['基金代码'] == code]
        if len(match) > 0:
            return match.iloc[0].to_dict(), 'etf'
    
    return None, None

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

def generate_report(config, holdings_data, index_data, portfolio_analysis):
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
    lines.append(f"- **持仓数量**: {portfolio_analysis['summary']['holding_count']} 只")
    lines.append(f"- **是否触发再平衡**: {'是' if portfolio_analysis['summary']['rebalance_required'] else '否'}")
    lines.append(f"- **数据成功率**: {portfolio_analysis['data_quality']['fund_nav_success_rate']:.1f}%")
    lines.append("")
    
    lines.append("### 资产配置")
    lines.append("")
    lines.append("| 类别 | 当前占比 | 目标占比 | 偏离 | 状态 |")
    lines.append("|------|---------|---------|------|------|")
    status_map = {'within_band': '带内', 'overweight': '偏高', 'underweight': '偏低'}
    for cat, item in portfolio_analysis['allocation'].items():
        lines.append(
            f"| {cat} | {item['current_pct']:.1f}% | {item['target_pct']:.1f}% | "
            f"{item['drift_pct']:+.1f}% | {status_map.get(item['status'], item['status'])} |"
        )
    lines.append("")

    lines.append("### 再平衡草案")
    lines.append("")
    if portfolio_analysis['rebalance_plan']:
        for item in portfolio_analysis['rebalance_plan']:
            action = '减配' if item['action'] == 'reduce' else '增配'
            lines.append(f"- **{item['asset_class']}**: 建议{action}约 ¥{item['amount']:,.0f}。{item['reason']}")
    else:
        lines.append("- 当前主要资产类别均在再平衡阈值内，本周可优先观察。")
    lines.append("")

    lines.append("### 组合风险")
    lines.append("")
    risk = portfolio_analysis['risk']
    lines.append(f"- **前三大持仓占比**: {risk['top3_weight_pct']:.1f}%（集中度: {risk['concentration_level']}）")
    if risk['max_position'].get('code'):
        lines.append(
            f"- **最大单只持仓**: {risk['max_position']['name']} ({risk['max_position']['code']}) "
            f"{risk['max_position']['weight_pct']:.1f}%"
        )
    lines.append("")
    
    # 各基金表现
    lines.append("## 二、各基金表现")
    lines.append("")
    for h in sorted(holdings_data, key=lambda x: -x['value']):
        lines.append(f"### {h['name']} ({h['code']})")
        lines.append("")
        lines.append(f"- **市值**: ¥{h['value']:,.2f} ({h['value']/total_value*100:.1f}%)")
        lines.append(f"- **类型**: {h['type']}")
        
        if h.get('nav_data'):
            nd = h['nav_data']
            nav = nd.get('nav', 'N/A')
            chg = nd.get('daily_chg', 'N/A')
            buy = nd.get('buy_status', 'N/A')
            sell = nd.get('sell_status', 'N/A')
            lines.append(f"- **最新净值**: {nav}")
            lines.append(f"- **日涨跌**: {chg}")
            lines.append(f"- **申购**: {buy} | **赎回**: {sell}")
        else:
            lines.append("- *数据获取失败*")
        lines.append("")
    
    # 市场环境
    lines.append("## 三、市场环境")
    lines.append("")
    for name, data in index_data.items():
        if 'error' not in data:
            signal = portfolio_analysis.get('market', {}).get(name, {}).get('signal', 'neutral')
            lines.append(f"- **{name}**: {data['price']:.2f} | 周: {data['chg_5d']:+.1f}% | 月: {data['chg_20d']:+.1f}% | RSI: {data['rsi']:.0f} | 信号: {signal}")
        else:
            lines.append(f"- **{name}**: 数据获取失败")
    lines.append("")
    
    return '\n'.join(lines)

def main():
    print("🔍 开始拉取基金数据...")
    
    # 加载配置
    config = load_config()
    holdings = config['holdings']
    
    # 获取全量数据
    open_fund_df = get_all_fund_nav()
    money_fund_df = get_money_fund_nav()
    etf_df = get_etf_fund_nav()
    
    # 匹配各基金
    print(f"\n📊 匹配 {len(holdings)} 只基金...")
    total_value = 0
    success = 0
    fail = 0
    
    for h in holdings:
        code = h['code']
        nav = h.get('nav', 1.0)
        
        # 尝试匹配
        match, source = match_fund(code, open_fund_df, money_fund_df, etf_df)
        
        if match is not None:
            # 提取净值
            nav_val = None
            for key in match:
                if '单位净值' in str(key) and '累计' not in str(key):
                    nav_val = str(match[key])
                    break
            
            if nav_val and nav_val != '---':
                try:
                    nav = float(nav_val)
                except ValueError:
                    nav = h.get('nav', 1.0)
                h['current_nav'] = nav
                h['value'] = h['shares'] * nav
                
                # 日涨跌
                daily_chg = 'N/A'
                for key in match:
                    if '增长率' in str(key):
                        daily_chg = match[key]
                        break
                
                h['nav_data'] = {
                    'nav': nav,
                    'daily_chg': daily_chg,
                    'buy_status': match.get('申购状态', 'N/A'),
                    'sell_status': match.get('赎回状态', 'N/A'),
                }
                success += 1
                print(f"  ✅ {code} {h['name'][:20]}: 净值={nav}")
            else:
                h['value'] = h['shares'] * nav
                fail += 1
                print(f"  ⚠️ {code} {h['name'][:20]}: 净值解析失败")
        else:
            h['value'] = h['shares'] * nav
            fail += 1
            print(f"  ❌ {code} {h['name'][:20]}: 未找到")
        
        total_value += h.get('value', h['shares'] * nav)
    
    # 更新占比
    for h in holdings:
        h['weight'] = h.get('value', 0) / total_value * 100
    
    print(f"\n📈 匹配完成: 成功 {success}, 失败 {fail}")
    print(f"💰 总市值: ¥{total_value:,.2f}")
    
    # 获取指数数据
    print("\n📈 获取A股指数数据...")
    index_data = get_index_data()
    
    # 生成报告
    print("\n📝 生成分析报告...")
    portfolio_analysis = build_portfolio_analysis(
        config,
        holdings,
        index_data,
        success_count=success,
        fail_count=fail,
    )
    report = generate_report(config, holdings, index_data, portfolio_analysis)
    
    # 保存报告到项目根目录的 output/
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    report_path = os.path.join(output_dir, f"report_{datetime.now().strftime('%Y%m%d')}.md")
    with open(report_path, 'w') as f:
        f.write(report)
    
    # 保存原始数据
    data_path = os.path.join(output_dir, 'latest_data.json')
    with open(data_path, 'w') as f:
        json.dump({
            'date': datetime.now().isoformat(),
            'total_value': total_value,
            'success_count': success,
            'fail_count': fail,
            'holdings': [{k: v for k, v in h.items()} for h in holdings],
            'index': {k: {kk: vv for kk, vv in v.items() if 'error' not in v} for k, v in index_data.items()},
            'portfolio_analysis': portfolio_analysis,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 报告已生成: {report_path}")
    print(f"✅ 数据已保存: {data_path}")
    
    # 输出报告到 stdout
    print("\n" + "="*60)
    print(report)
    
    return report_path

if __name__ == '__main__':
    main()
