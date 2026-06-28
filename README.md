# Fund Portfolio Analyzer

个人基金持仓智能分析系统 - 自动生成周报，AI 驱动调整建议。

## 功能

- 自动拉取基金净值（akshare）+ A股指数行情
- 计算持仓市值、占比、技术指标（RSI、均线、趋势）
- 基于保守型配置目标生成调整建议
- 支持 Gemini / Groq 双 AI 后端分析
- 通过 GitHub Actions 定时执行，邮件发送报告

## 快速开始

### 1. 配置 GitHub Secrets

在仓库 Settings > Secrets and variables > Actions 中添加：

| Secret | 说明 | 必需 |
|--------|------|------|
| `GEMINI_API_KEY` | Google AI Studio API Key（免费额度够用） | 二选一 |
| `GROQ_API_KEY` | Groq API Key（免费高速推理） | 二选一 |
| `GMAIL_USERNAME` | 发送方 Gmail 地址 | 是 |
| `GMAIL_APP_PASSWORD` | Gmail 应用密码（不是登录密码） | 是 |
| `GMAIL_RECIPIENT` | 接收报告的邮箱 | 是 |

可选 GitHub Variables：

| Variable | 默认值 | 说明 |
|----------|--------|------|
| `GEMINI_MODELS` | `gemini-2.5-flash-lite,gemini-2.5-flash` | Google AI Studio REST API 模型候选，按顺序重试 |
| `GEMINI_MODEL` | 空 | 兼容旧配置；未设置 `GEMINI_MODELS` 时使用 |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq 兜底模型 |
| `ENABLE_GROQ_FALLBACK` | `false` | 是否在 Gemini 失败后尝试 Groq |

**获取 Gmail 应用密码**：
1. 登录 Google 账户
2. 前往 https://myaccount.google.com/apppasswords
3. 生成新应用密码
4. 填入 `GMAIL_APP_PASSWORD`

**获取 Gemini API Key**（推荐，免费额度充足）：
1. 前往 https://aistudio.google.com/apikey
2. 创建 API Key → 填入 `GEMINI_API_KEY`

**获取 Groq API Key**（备选，速度快）：
1. 前往 https://console.groq.com/keys
2. 创建 API Key → 填入 `GROQ_API_KEY`

### 2. 修改持仓配置

编辑 `config/holdings.json`，填入你的实际持仓：

```json
{
  "user": "your_name",
  "style": "conservative",
  "target_allocation_conservative": {
    "现金类": {"target": 35},
    "固收类": {"target": 35},
    "权益类": {"target": 25},
    "权益类QDII": {"target": 5}
  },
  "holdings": [
    {"code": "008774", "name": "招商鑫福中短债债券A", "type": "债券型", "shares": 174619.63, "nav": 1.195}
  ]
}
```

基金代码 6 位数字，类型：货币型/债券型/混合型/股票型

### 3. 手动触发

GitHub 仓库页面 > Actions > Fund Portfolio Weekly Analysis > Run workflow

或本地测试：
```bash
pip install akshare pandas numpy
python scripts/analyze.py
python scripts/ai_analyze.py
```

## 如何更新持仓

每次买卖基金后，修改 `config/holdings.json` 中的 shares（份额），然后 push：

```bash
git add config/holdings.json
git commit -m "update: 持仓变更"
git push
```

## AI 后端优先级

1. **Gemini** → Google AI Studio REST API（默认 `gemini-2.5-flash-lite`，失败后尝试 `gemini-2.5-flash`）
2. **Groq** → 仅当 `ENABLE_GROQ_FALLBACK=true` 时启用
3. **无 API Key** → 只输出原始分析报告

脚本不依赖 `google-genai` SDK，直接请求：

```text
https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
```

如果 GitHub Actions 日志出现 `Gemini HTTP 429`，说明 Google AI Studio 当前 API key 命中了请求或配额限制。可以等待配额恢复，或把 `GEMINI_MODELS` 设置为更轻的模型优先级，例如只保留 `gemini-2.5-flash-lite`。

自动构建会生成两类产物：

- `output/report_YYYYMMDD.md`：基金净值、配置偏离、市场指数等基础周报
- `output/ai_analysis_YYYYMMDD.md`：Gemini/Groq 生成的持仓诊断、调仓建议和风险提示

GitHub Actions 会上传 `output/` 为 artifact，并把最新报告复制到 `reports/` 后提交到仓库。

## Schedule

- 每周一 UTC 01:00 执行（北京时间 9:00）
- 报告自动发给 `GMAIL_RECIPIENT`

## License
MIT
