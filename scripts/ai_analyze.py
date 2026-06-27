#!/usr/bin/env python3
"""
AI 分析脚本 - 读取报告，调用 Gemini/Groq，发送邮件
"""
import json
import os
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

def read_report():
    """读取最新报告"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    report_dir = os.path.normpath(os.path.join(script_dir, '..', 'output'))
    files = [f for f in os.listdir(report_dir) if f.startswith('report_') and f.endswith('.md')]
    if not files:
        return None
    files.sort(reverse=True)
    with open(os.path.join(report_dir, files[0]), 'r') as f:
        return f.read()

def call_gemini(prompt, api_key, retries=3):
    """调用 Gemini API（带重试）"""
    import urllib.request
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    for attempt in range(retries):
        try:
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
            }).encode('utf-8')
            
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                text = data['candidates'][0]['content']['parts'][0]['text']
                return text
        except Exception as e:
            err_str = str(e)
            if '429' in err_str and attempt < retries - 1:
                wait = (attempt + 1) * 10
                print(f"  Gemini 429, retry in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"Gemini error: {e}", file=sys.stderr)
                return None
    return None

def call_groq(prompt, api_key, retries=3):
    """调用 Groq API（带重试）"""
    import urllib.request
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    for attempt in range(retries):
        try:
            payload = json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2048
            }).encode('utf-8')
            
            req = urllib.request.Request(url, data=payload, headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            })
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                text = data['choices'][0]['message']['content']
                return text
        except Exception as e:
            err_str = str(e)
            if ('429' in err_str or '403' in err_str) and attempt < retries - 1:
                wait = (attempt + 1) * 5
                print(f"  Groq error, retry in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"Groq error: {e}", file=sys.stderr)
                return None
    return None

def call_gemini_sdk(prompt, api_key):
    """使用 google-genai SDK 调用（更稳定）"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(
            prompt,
            generation_config={'temperature': 0.3, 'max_output_tokens': 2048}
        )
        return response.text
    except ImportError:
        print("google-genai SDK not installed, using REST", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Gemini SDK error: {e}", file=sys.stderr)
        return None

def send_email(subject, body, username, password, recipient):
    """发送邮件"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"Portfolio Analyzer <{username}>"
    msg['To'] = recipient
    
    # Plain text
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # HTML version
    import re
    lines = body.split('\n')
    html_lines = []
    for line in lines:
        line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
        line = re.sub(r'- (.+)', r'<li>\1</li>', line)
        if line.startswith('# '):
            html_lines.append(f'<h2>{line[2:]}</h2>')
        elif line.startswith('## '):
            html_lines.append(f'<h3>{line[3:]}</h3>')
        elif line.startswith('### '):
            html_lines.append(f'<h4>{line[4:]}</h4>')
        elif line.strip().startswith('<li>'):
            html_lines.append(f'<ul>{line.strip()}</ul>')
        elif line.strip() == '':
            html_lines.append('<br>')
        else:
            html_lines.append(f'<p>{line}</p>')
    
    html_content = '\n'.join(html_lines)
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        print(f"Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"Email error: {e}", file=sys.stderr)
        return False

def main():
    report = read_report()
    if not report:
        print("No report found. Run analyze.py first.")
        sys.exit(1)
    
    # Build prompt
    prompt = """你是一位保守型个人投资顾问。请分析以下基金持仓周报，输出完整的调整建议和风险提示。

## 分析原则
- 保守风格：最大回撤容忍<10%，优先保本，不追热点
- 目标配置：现金35% / 固收35% / 权益25% / QDII 5%
- 持有基金数量控制在10-12只，不随意新增
- 调整阈值：单一资产偏离目标>3%才触发再平衡

## 输出要求（必须包含以下三个部分）

### 第一部分：组合诊断
- 当前总资产和当日盈亏估算
- 实际配置 vs 目标配置的偏离分析
- 标注偏离>3%的资产类别

### 第二部分：具体调整建议
对每只基金给出明确操作：
- 操作类型：增持 / 减持 / 持有 / 赎回
- 建议调整金额（人民币）
- 调整理由（1-2句话）
- 如果建议买入某只新基金，给出具体的基金名称和代码

### 第三部分：风险提示
- 当前市场环境判断（基于指数数据）
- 集中度风险（前3大持仓是否过重）
- 流动性风险（注意持有期限制）
- 近期需关注的事件
- 如果整体仓位偏保守，说明当前现金的机会成本

## 约束
- 总输出控制在800字以内
- 简体中文，列表形式，不用表格
- 建议必须具体可执行，不要泛泛而谈
- 不要推荐卖出低波红利类基金去追热点
- 如果市场无明显机会，明确说"本周不建议操作"

Report:
""" + report
    
    # AI 调用策略
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    groq_key = os.environ.get('GROQ_API_KEY', '')
    
    result = None
    backend = 'none'
    
    # 策略：优先用 SDK（更稳定），失败退到 REST + 重试
    if gemini_key:
        print("Trying Gemini SDK...", file=sys.stderr)
        result = call_gemini_sdk(prompt, gemini_key)
        if result:
            backend = 'gemini-sdk'
    
    if not result and gemini_key:
        print("Trying Gemini REST (with retry)...", file=sys.stderr)
        time.sleep(2)  # 避免限流
        result = call_gemini(prompt, gemini_key, retries=3)
        if result:
            backend = 'gemini-rest'
    
    if not result and groq_key:
        print("Trying Groq...", file=sys.stderr)
        time.sleep(1)
        result = call_groq(prompt, groq_key, retries=2)
        if result:
            backend = 'groq'
    
    if not result:
        print("AI analysis unavailable, sending raw report")
        result = report
        backend = 'raw'
    
    print(f"Analysis backend: {backend}")
    print("---ANALYSIS RESULT---")
    print(result)
    print("---END---")
    
    # Send email
    username = os.environ.get('GMAIL_USERNAME', '')
    password = os.environ.get('GMAIL_APP_PASSWORD', '')
    recipient = os.environ.get('GMAIL_RECIPIENT', '')
    
    if username and password and recipient:
        subject = f"Fund Weekly Report - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"""基金持仓周报 AI 分析报告
报告日期: {datetime.now().strftime('%Y-%m-%d')}
分析风格: 保守型

{result}

---
⚠️ 本分析由 GitHub Actions 自动生成，仅供参考，不构成投资建议。
分析后端: {backend}
"""
        send_email(subject, body, username, password, recipient)
    else:
        print("Email credentials not configured")

if __name__ == '__main__':
    main()
