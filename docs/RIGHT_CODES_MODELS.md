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

## 如何选择模型：效果 vs 价格

### 定价概览（来自 right.codes 网站，per 1M tokens）

| 模型 | 端点 | 输入价 | 输出价 | 综合评分 |
|------|------|--------|--------|----------|
| `claude-sonnet-5` | claude-sale | 约 $3 | 约 $15 | ⭐⭐⭐⭐⭐ 最强推理 |
| `claude-opus-4-8` | claude-sale | 约 $15 | 约 $75 | ⭐⭐⭐⭐⭐ 旗舰，但贵 |
| `claude-haiku-4-5-20251001` | claude-sale | 约 $0.8 | 约 $4 | ⭐⭐⭐⭐ 快且便宜 |
| `gpt-5.4` | codex | $1 | $6 | ⭐⭐⭐⭐ 性价比高 |
| `gpt-5.4-mini` | codex | $0.3 | $1.8 | ⭐⭐⭐ 最便宜 |
| `gpt-5.5` | codex | $2 | $12 | ⭐⭐⭐⭐ 高性能 |
| `gpt-5.6-luna` | codex | $0.4 | $2.4 | ⭐⭐⭐ 轻量快速 |
| `gemini-3.5-flash` | gemini | 极低 | 极低 | ⭐⭐⭐⭐ 速度最快 |
| `gemini-3.1-pro` | gemini | 约 $1.25 | 约 $5 | ⭐⭐⭐⭐ Google 旗舰 |
| `deepseek-v4-pro` | deepseek | $3 | $6 | ⭐⭐⭐⭐ 中文强 |
| `deepseek-v4-flash` | deepseek | 极低 | 极低 | ⭐⭐⭐ 快速版 |
| `qwen3.7-max` | ali | 约 $0.5 | 约 $2 | ⭐⭐⭐⭐ 中文最优 |
| `qwen3.6-flash` | ali | 极低 | 极低 | ⭐⭐⭐ 极速 |
| `kimi-k2.7-code` | ali | 约 $1 | 约 $3 | ⭐⭐⭐⭐ 代码专用 |

---

### 按场景推荐

#### 🏆 效果优先（不计成本）
```
LLM_BASE_URL=https://www.right.codes/claude-sale/v1
LLM_MODEL=claude-sonnet-5
```
> Claude Sonnet 5 是当前推理能力最强的模型，适合 research、proposal、script 等创意阶段。

---

#### 💰 价格最优（每次运行成本 < $0.01）
```
LLM_BASE_URL=https://www.right.codes/codex/v1
LLM_MODEL=gpt-5.4-mini
```
> 输入 $0.3/M，输出 $1.8/M。OpenMontage 每个 stage 约 2000 tokens，成本约 $0.004。

---

#### ⚖️ 效果与价格均衡（推荐日常使用）
```
LLM_BASE_URL=https://www.right.codes/codex/v1
LLM_MODEL=gpt-5.4
```
> 输入 $1/M，输出 $6/M。每 stage 约 $0.013，整条流水线（8 stages）约 $0.10。效果比 mini 好很多。

---

#### 🇨🇳 中文内容优化（电商文案、短视频脚本）
```
LLM_BASE_URL=https://www.right.codes/ali/v1
LLM_MODEL=qwen3.7-max
```
> 通义千问 3.7 Max 对中文电商场景有专项优化，生成的卖点文案、脚本更符合国内平台风格。

---

#### ⚡ 速度优先（快速原型）
```
LLM_BASE_URL=https://www.right.codes/gemini/v1
LLM_MODEL=gemini-3.5-flash
```
> Gemini Flash 系列响应延迟最低，适合快速迭代验证流水线是否跑通。

---

### OpenMontage 实际成本估算

每条完整流水线（research → publish，8 stages）：

| 模型 | 每 stage 估算 | 完整流水线 |
|------|--------------|------------|
| claude-sonnet-5 | ~$0.06 | ~$0.48 |
| gpt-5.4 | ~$0.013 | ~$0.10 |
| gpt-5.4-mini | ~$0.004 | ~$0.03 |
| qwen3.7-max | ~$0.008 | ~$0.06 |
| gemini-3.5-flash | ~$0.001 | ~$0.008 |

> 估算基于每 stage 约 1500 input tokens + 500 output tokens。

---

## OpenMontage `.env` 配置示例

```bash
# 效果最好
LLM_BASE_URL=https://www.right.codes/claude-sale/v1
LLM_MODEL=claude-sonnet-5

# 价格最优
LLM_BASE_URL=https://www.right.codes/codex/v1
LLM_MODEL=gpt-5.4-mini

# 均衡推荐
LLM_BASE_URL=https://www.right.codes/codex/v1
LLM_MODEL=gpt-5.4

# 中文场景
LLM_BASE_URL=https://www.right.codes/ali/v1
LLM_MODEL=qwen3.7-max
```
