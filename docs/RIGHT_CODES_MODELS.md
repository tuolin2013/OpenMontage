# right.codes API 端点与模型列表

> 基础 URL 格式：`https://www.right.codes/<端点>/v1`  
> 认证方式：`Authorization: Bearer <LLM_API_KEY>`  
> 接口格式：OpenAI Chat Completions 兼容（`/v1/chat/completions`）

---

## 1. Codex（通用推理）

**Base URL：** `https://www.right.codes/codex/v1`

| 模型 ID | 说明 |
|---------|------|
| `gpt-5.4` | 主力模型，$1/$6 per M tokens |
| `gpt-5.4-mini` | 轻量版，$0.3/$1.8 per M tokens |
| `gpt-5.5` | 高性能，$2/$12 per M tokens |
| `gpt-5.5-openai-compact` | OpenAI 兼容版 |
| `gpt-5.6-luna` | $0.4/$2.4 per M tokens |
| `gpt-5.6-sol` | $2/$12 per M tokens |
| `gpt-5.6-terra` | 高级版 |
| `codex-auto-review` | 代码审查专用 |

**推荐用于 OpenMontage：** `gpt-5.4`（性价比最高）

---

## 2. Claude Sale（直连 Anthropic）

**Base URL：** `https://www.right.codes/claude-sale/v1`

| 模型 ID | 说明 |
|---------|------|
| `claude-sonnet-5` | Claude Sonnet 最新版 |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 |
| `claude-opus-4-6` | Claude Opus 4.6 |
| `claude-opus-4-7` | Claude Opus 4.7 |
| `claude-opus-4-8` | Claude Opus 4.8（最新） |
| `claude-haiku-4-5-20251001` | 轻量快速 |
| `claude-fable-5` | 创意写作专用 |

---

## 3. Claude AWS（AWS Bedrock 路由）

**Base URL：** `https://www.right.codes/claude-aws/v1`

| 模型 ID | 说明 |
|---------|------|
| `claude-sonnet-5` | Claude Sonnet 最新版 |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 |
| `claude-opus-4-6` | Claude Opus 4.6 |
| `claude-opus-4-7` | Claude Opus 4.7 |
| `claude-opus-4-8` | Claude Opus 4.8 |
| `claude-haiku-4-5-20251001` | 轻量快速 |

---

## 4. Draw（图像生成）

**Base URL：** `https://www.right.codes/draw/v1`

| 模型 ID | 说明 |
|---------|------|
| `gpt-image-2` | 标准图像生成，$0.04/次 |
| `gpt-image-2-vip` | VIP 高质量版 |
| `nano-banana` | 快速生成 |
| `nano-banana-2` | 升级版 |
| `nano-banana-pro` | 专业版 |
| `nano-banana-2-lite` | 轻量版 |

---

## 5. Gemini

**Base URL：** `https://www.right.codes/gemini/v1`

| 模型 ID | 说明 |
|---------|------|
| `gemini-2.5-flash` | 快速版 |
| `gemini-2.5-pro` | 专业版 |
| `gemini-3-flash-preview` | 下一代快速预览 |
| `gemini-3-pro-preview` | 下一代专业预览 |
| `gemini-3.1-pro` | 稳定版 |
| `gemini-3.1-pro-preview` | 预览版 |
| `gemini-3.1-pro-preview-customtools` | 自定义工具版 |
| `gemini-3.5-flash` | 最新快速版 |

---

## 6. DeepSeek V4

**Base URL：** `https://www.right.codes/deepseek/v1`

| 模型 ID | 说明 |
|---------|------|
| `deepseek-v4-pro` | 专业版，$3/$6 per M tokens |
| `deepseek-v4-flash` | 快速版 |

---

## 7. Ali（国产模型聚合）

**Base URL：** `https://www.right.codes/ali/v1`

| 模型 ID | 说明 |
|---------|------|
| `qwen3.7-max` | 通义千问 3.7 最强版 |
| `qwen3.7-plus` | 通义千问 3.7 增强版 |
| `qwen3.6-max-preview` | 通义千问 3.6 Max 预览 |
| `qwen3.6-plus` | 通义千问 3.6 增强版 |
| `qwen3.6-flash` | 通义千问 3.6 快速版 |
| `kimi-k2.7-code` | Kimi 代码专用 |
| `kimi-k2.6` | Kimi K2.6 |
| `kimi-k2.5` | Kimi K2.5 |
| `glm-5.2` | 智谱 GLM 5.2 |
| `glm-5.1` | 智谱 GLM 5.1 |
| `glm-5` | 智谱 GLM 5 |
| `glm-4.7` | 智谱 GLM 4.7 |
| `MiniMax-M2.7` | MiniMax M2.7 |
| `MiniMax-M2.5` | MiniMax M2.5 |

---

## OpenMontage 配置建议

在 `.env` 中配置：

```bash
# 推荐：claude-sale 端点使用 claude-sonnet-5（质量最高）
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://www.right.codes/claude-sale/v1
LLM_MODEL=claude-sonnet-5

# 或：codex 端点使用 gpt-5.4（性价比高）
LLM_BASE_URL=https://www.right.codes/codex/v1
LLM_MODEL=gpt-5.4

# 或：ali 端点使用 qwen3.7-max（中文优化）
LLM_BASE_URL=https://www.right.codes/ali/v1
LLM_MODEL=qwen3.7-max
```
