#!/usr/bin/env python3
"""
AI 分析脚本 - 读取报告，调用 Gemini/Groq，发送邮件
"""
import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

def read_report():
    """读取最新报告"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # output/ is at repo root, scripts/ is one level deep
    report_dir = os.path.normpath(os.path.join(script_dir, '..', 'output'))
    files = [f for f in os.listdir(report_dir) if f.startswith('report_') and f.endswith('.md')]
    if not files:
        return None
    files.sort(reverse=True)
    with open(os.path.join(report_dir, files[0]), 'r') as f:
        return f.read()

def call_gemini(prompt, api_key):
    """调用 Gemini API"""
    import urllib.request
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048}
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Gemini error: {e}", file=sys.stderr)
        return None

def call_groq(prompt, api_key):
    """调用 Groq API"""
    import urllib.request
    
    url = "https://api.groq.com/openai/v1/chat/completions"
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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"Groq error: {e}", file=sys.stderr)
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
    html_body = body
    # Convert markdown-like to basic HTML
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
    prompt = """You are a conservative personal investment advisor. Analyze the following fund portfolio weekly report and provide adjustment suggestions.

Principles:
- Conservative style: maximum drawdown tolerance <10%
- Target allocation: Cash 35% / Bonds 35% / Equity 25% / QDII 5%
- Give specific per-fund action: increase/decrease/hold
- Flag asset classes deviating >3% from target
- Maximum 500 Chinese characters, bullet points only, no tables
- Output in Simplified Chinese only

Report:
""" + report
    
    # Try Gemini first
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    groq_key = os.environ.get('GROQ_API_KEY', '')
    
    result = None
    backend = 'none'
    
    if gemini_key:
        print("Trying Gemini...")
        result = call_gemini(prompt, gemini_key)
        if result:
            backend = 'gemini'
    
    if not result and groq_key:
        print("Trying Groq...")
        result = call_groq(prompt, groq_key)
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
        body = f"""基金持仓周报分析报告

{result}

---
本分析由 GitHub Actions 自动生成
分析后端: {backend}
"""
        send_email(subject, body, username, password, recipient)
    else:
        print("Email credentials not configured")

if __name__ == '__main__':
    main()
