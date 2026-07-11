# OpenMontage Web UI (v2)

Modern React + Vite + Tailwind frontend for the OpenMontage Web SaaS platform.

## Stack

| Layer | Tech |
|-------|------|
| Framework | React 18 + React Router v6 |
| Build | Vite 5 |
| Styling | Tailwind CSS v3 |
| Data fetching | TanStack React Query v5 |
| HTTP | Axios |
| State | Zustand (available, used for future global state) |

## Pages

### `/ ` — 新建商品视频流水线

Product pipeline creation form with:
- Pipeline selector (6 pipeline types)
- Product name + key selling points
- Identity Preservation section:
  - LoRA model path input
  - ControlNet weight input
  - Transparent PNG upload (drag-drop area, preview)
- Submits to `POST /api/project/create` or `/create/upload`
- On success: redirects to `/monitor/:projectId`

### `/monitor/:projectId` — 状态机工作台

Real-time pipeline state machine monitor with:
- Horizontal node graph (Research → Script → Scene Plan → Assets → Compose)
- Per-node status (completed / in_progress / awaiting_human / failed)
- Per-node **🚀 运行此阶段** button
- Approval gate (amber pulsing card) when `awaiting_human`
- Inline JSON editor for AI-generated artifacts (script, scene_plan, etc.)
- **✅ 保存并批准** button — saves edits + approves + unlocks next stage
- Agent log tail (polling every 4s)
- Abort button

## Dev Setup

```bash
npm install
npm run dev        # http://localhost:5173
```

The Vite proxy forwards `/api/*` → `http://localhost:8000` (the FastAPI backend).

## Build

```bash
npm run build      # outputs to dist/
```
