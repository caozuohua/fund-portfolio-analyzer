#!/usr/bin/env python3
"""
AI 分析脚本 - 读取报告，调用 Gemini/Groq，保存分析结果并发送邮件
"""
import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'output'))
DEFAULT_GEMINI_MODEL = os.environ.get('GEMINI_MODEL') or 'gemini-3.5-flash'
DEFAULT_GROQ_MODEL = os.environ.get('GROQ_MODEL') or 'llama-3.3-70b-versatile'

def read_report():
    """读取最新报告"""
    files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith('report_') and f.endswith('.md')]
    if not files:
        return None
    files.sort(reverse=True)
    with open(os.path.join(OUTPUT_DIR, files[0]), 'r', encoding='utf-8') as f:
        return f.read()

def read_latest_data():
    """读取结构化持仓数据，供 AI 做更精确的金额和占比判断"""
    data_path = os.path.join(OUTPUT_DIR, 'latest_data.json')
    if not os.path.exists(data_path):
        return None
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_gemini_text(data):
    """兼容 generateContent 返回结构，提取文本结果"""
    candidates = data.get('candidates') or []
    if not candidates:
        raise ValueError(f"Gemini response has no candidates: {data}")

    parts = candidates[0].get('content', {}).get('parts', [])
    text = ''.join(part.get('text', '') for part in parts if part.get('text'))
    if not text:
        raise ValueError(f"Gemini response has no text: {data}")
    return text

def call_gemini_rest(prompt, api_key, model=DEFAULT_GEMINI_MODEL, retries=3):
    """调用 Gemini API（带重试）"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    for attempt in range(retries):
        try:
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.25,
                    "maxOutputTokens": 2048,
                    "responseMimeType": "text/plain"
                }
            }).encode('utf-8')
            
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return extract_gemini_text(data)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            retriable = e.code in (408, 429, 500, 502, 503, 504)
            if retriable and attempt < retries - 1:
                wait = min(60, (attempt + 1) * 10)
                print(f"  Gemini HTTP {e.code}, retry in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"Gemini REST HTTP {e.code}: {body[:500]}", file=sys.stderr)
                return None
        except Exception as e:
            if attempt < retries - 1:
                wait = min(60, (attempt + 1) * 10)
                print(f"  Gemini REST error, retry in {wait}s: {e}", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"Gemini REST error: {e}", file=sys.stderr)
                return None
    return None

def call_groq(prompt, api_key, model=DEFAULT_GROQ_MODEL, retries=3):
    """调用 Groq API（带重试）"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    for attempt in range(retries):
        try:
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.25,
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
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            if e.code in (408, 429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = min(30, (attempt + 1) * 5)
                print(f"  Groq HTTP {e.code}, retry in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"Groq HTTP {e.code}: {body[:500]}", file=sys.stderr)
                return None
        except Exception as e:
            if attempt < retries - 1:
                wait = min(30, (attempt + 1) * 5)
                print(f"  Groq error, retry in {wait}s: {e}", file=sys.stderr)
                time.sleep(wait)
            else:
                print(f"Groq error: {e}", file=sys.stderr)
                return None
    return None

def call_gemini_sdk(prompt, api_key, model=DEFAULT_GEMINI_MODEL):
    """使用新版 google-genai SDK 调用 Google AI Studio Gemini API"""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.25,
                max_output_tokens=2048,
                response_mime_type='text/plain',
            ),
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

def save_ai_analysis(result, backend):
    """保存 AI 分析结果到 output，方便 GitHub Actions 上传 artifact"""
    output_path = os.path.join(OUTPUT_DIR, f"ai_analysis_{datetime.now().strftime('%Y%m%d')}.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# AI 基金持仓分析 - {datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(f"- 分析后端: {backend}\n")
        f.write(f"- Gemini 模型: {DEFAULT_GEMINI_MODEL}\n\n")
        f.write(result)
        f.write("\n")
    return output_path

def build_prompt(report, latest_data):
    data_block = ""
    if latest_data:
        data_block = "\n\nStructured data JSON:\n" + json.dumps(latest_data, ensure_ascii=False, indent=2)

    return """你是一位保守型个人基金组合分析助手。请基于以下自动生成的基金持仓周报和结构化数据，给出本周是否需要调整以及具体操作建议。

## 分析原则
- 保守风格：最大回撤容忍<10%，优先保本，不追热点
- 目标配置：现金35% / 固收35% / 权益25% / QDII 5%
- 持有基金数量控制在10-12只，不随意新增
- 调整阈值：单一资产类别偏离目标>3%才触发再平衡
- 金额建议需与当前总市值、持仓占比、目标配置相匹配

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
- 仅基于输入数据分析，不要编造没有给出的实时新闻或基金信息
- 明确声明结果仅供参考，不构成投资建议

Report:
""" + report + data_block

def main():
    report = read_report()
    if not report:
        print("No report found. Run analyze.py first.")
        sys.exit(1)
    
    latest_data = read_latest_data()
    prompt = build_prompt(report, latest_data)
    
    # AI 调用策略
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    groq_key = os.environ.get('GROQ_API_KEY', '')
    
    result = None
    backend = 'none'
    
    # 策略：优先用 SDK（更稳定），失败退到 REST + 重试
    if gemini_key:
        print(f"Trying Gemini SDK ({DEFAULT_GEMINI_MODEL})...", file=sys.stderr)
        result = call_gemini_sdk(prompt, gemini_key)
        if result:
            backend = 'gemini-sdk'
    
    if not result and gemini_key:
        print(f"Trying Gemini REST ({DEFAULT_GEMINI_MODEL}, with retry)...", file=sys.stderr)
        time.sleep(2)  # 避免限流
        result = call_gemini_rest(prompt, gemini_key, retries=3)
        if result:
            backend = 'gemini-rest'
    
    if not result and groq_key:
        print(f"Trying Groq ({DEFAULT_GROQ_MODEL})...", file=sys.stderr)
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

    analysis_path = save_ai_analysis(result, backend)
    print(f"AI analysis saved: {analysis_path}")
    
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
