/**
 * MonitorPage — 状态机工作台 (Pipeline Monitor)
 *
 * - URL: /monitor  (list) or /monitor/:projectId (detail)
 * - Polls project status every 3s via React Query
 * - Shows StagePipeline with per-node Run buttons
 * - When a stage is awaiting_human, renders ArtifactEditor
 *   so user can edit + approve in the same view
 */
import React, { useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getProjectStatus, runStage, abortProject, getAgentLog } from '../api'
import StagePipeline from '../components/StagePipeline'
import ArtifactEditor from '../components/ArtifactEditor'

// ── Stage ordering used when meta doesn't specify ─────────────
const DEFAULT_STAGES = ['research', 'proposal', 'idea', 'script', 'scene_plan', 'assets', 'edit', 'compose']

const STATUS_BADGE = {
  completed:      <span className="badge badge-completed">✓ 完成</span>,
  in_progress:    <span className="badge badge-in-progress">⟳ 运行中</span>,
  awaiting_human: <span className="badge badge-awaiting">⏳ 等待审批</span>,
  failed:         <span className="badge badge-failed">✗ 失败</span>,
  created:        <span className="badge badge-created">○ 新建</span>,
}

// ── Project list (when no :projectId) ─────────────────────────
function ProjectList() {
  // Load the first batch from the older /api/projects endpoint (ui backend)
  // or fall back to scanning via status calls is not feasible here,
  // so we provide a manual input field to jump directly.
  const [projectId, setProjectId] = useState('')
  const navigate = useNavigate()

  return (
    <div className="max-w-xl mx-auto px-6 py-12">
      <h1 className="text-2xl font-bold text-white mb-2">📊 状态机工作台</h1>
      <p className="text-gray-400 text-sm mb-8">输入项目 ID 进入监控视图，或在下方创建新项目。</p>
      <div className="flex gap-3">
        <input
          className="form-input flex-1"
          placeholder="输入项目 ID，例如：my-product-1720600000"
          value={projectId}
          onChange={e => setProjectId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && projectId && navigate(`/monitor/${projectId}`)}
        />
        <button
          className="btn btn-primary"
          disabled={!projectId.trim()}
          onClick={() => navigate(`/monitor/${projectId.trim()}`)}
        >
          进入 →
        </button>
      </div>
      <div className="mt-8 text-center">
        <Link to="/" className="btn btn-secondary">✨ 新建流水线</Link>
      </div>
    </div>
  )
}

// ── Project detail monitor ─────────────────────────────────────
function ProjectMonitor({ projectId }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [runningStage, setRunningStage] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [selectedArtifactStage, setSelectedArtifactStage] = useState(null)

  const { data: project, isLoading, error } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProjectStatus(projectId),
    refetchInterval: 3000,
  })

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['project', projectId] })
  }, [qc, projectId])

  // Build a stage→checkpoint map
  const checkpoints = project?.checkpoints ?? []
  const cpMap = Object.fromEntries(checkpoints.map(cp => [cp.stage, cp]))

  // Derive ordered stages from checkpoints + defaults
  const cpStages = checkpoints.map(cp => cp.stage)
  const stages = [...new Set([...DEFAULT_STAGES.filter(s => cpStages.includes(s) || DEFAULT_STAGES.includes(s))])]
    .filter(s => cpStages.includes(s) || DEFAULT_STAGES.includes(s))

  // The awaiting_human checkpoint (approval gate)
  const awaitingCp = checkpoints.find(cp => cp.status === 'awaiting_human')
  const awaitingArtifacts = awaitingCp?.artifacts ?? {}
  const awaitingArtifactKeys = Object.keys(awaitingArtifacts)

  // Determine which artifact to show in the editor
  const editorStage = selectedArtifactStage ?? awaitingCp?.stage
  const editorArtifactKey = awaitingArtifactKeys[0]
  const editorData = editorArtifactKey ? awaitingArtifacts[editorArtifactKey] : undefined

  async function handleRunStage(stage) {
    setActionError(null)
    setRunningStage(stage)
    try {
      // If stage is awaiting_human, approve it; otherwise run it
      if (cpMap[stage]?.status === 'awaiting_human') {
        const { approveStage: approve } = await import('../api')
        await approve(projectId, { stage, auto_run_next: false })
      } else {
        await runStage(projectId, { stage })
      }
      refresh()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setRunningStage(null)
    }
  }

  async function handleAbort() {
    if (!window.confirm('确认中止该项目吗？')) return
    setActionError(null)
    try {
      await abortProject(projectId, '用户通过 Web UI 中止')
      refresh()
    } catch (err) {
      setActionError(err.message)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-gray-400">
        <span className="stage-spinner inline-block w-6 h-6 border-2 border-gray-600 border-t-brand-400 rounded-full" />
        加载项目中...
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-lg mx-auto py-16 px-6 text-center">
        <div className="text-4xl mb-4">⚠️</div>
        <div className="text-red-400 font-semibold mb-2">项目加载失败</div>
        <div className="text-gray-500 text-sm mb-6">{error.message}</div>
        <button className="btn btn-ghost" onClick={() => navigate('/monitor')}>← 返回</button>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">

      {/* ── Header ─────────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/monitor')}>← 返回</button>
            <h1 className="text-xl font-bold text-white truncate max-w-xs" title={projectId}>
              {projectId}
            </h1>
            {STATUS_BADGE[project?.status] ?? <span className="badge badge-created">{project?.status}</span>}
          </div>
          <div className="text-xs text-gray-500">
            流水线: <span className="text-gray-400">{project?.pipeline}</span>
            {project?.current_stage && (
              <> &nbsp;·&nbsp; 当前阶段: <span className="text-blue-400">{project.current_stage}</span></>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-ghost btn-sm" onClick={refresh}>🔄 刷新</button>
          {project?.status !== 'completed' && project?.status !== 'failed' && (
            <button className="btn btn-danger btn-sm" onClick={handleAbort}>🛑 中止</button>
          )}
        </div>
      </div>

      {actionError && (
        <div className="rounded-lg bg-red-900/40 border border-red-700/50 px-4 py-3 text-red-400 text-sm">
          ⚠️ {actionError}
        </div>
      )}

      {/* ── Stage pipeline ──────────────────────────────────── */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-300">🗺️ 流水线进度</h2>
          {project?.next_stage && (
            <span className="text-xs text-gray-500">
              下一阶段: <span className="text-brand-400">{project.next_stage}</span>
            </span>
          )}
        </div>
        <StagePipeline
          stages={stages.length > 0 ? stages : DEFAULT_STAGES}
          cpMap={cpMap}
          nextStage={project?.next_stage}
          runningStage={runningStage}
          onRunStage={handleRunStage}
        />
      </div>

      {/* ── Approval gate + artifact editor ─────────────────── */}
      {awaitingCp && (
        <div className="card approval-pulse border-amber-700/60 bg-amber-900/10 space-y-4">
          <div className="flex items-start gap-4">
            <div className="text-3xl">⏳</div>
            <div>
              <div className="text-amber-400 font-bold text-lg">
                审批拦截 — {awaitingCp.stage}
              </div>
              <div className="text-sm text-gray-400 mt-1">
                AI 已完成该阶段，请检查下方生成内容，修改后点击"保存并批准"解锁下一步。
              </div>
            </div>
          </div>

          {editorArtifactKey && editorData !== undefined ? (
            <ArtifactEditor
              projectId={projectId}
              stage={awaitingCp.stage}
              artifactKey={editorArtifactKey}
              initialData={editorData}
              onSaved={refresh}
            />
          ) : (
            <div className="space-y-2">
              <p className="text-sm text-gray-400">此阶段无可编辑的 artifact。</p>
              <div className="flex gap-3">
                <button
                  className="btn btn-success"
                  onClick={async () => {
                    const { approveStage: approve } = await import('../api')
                    try {
                      await approve(projectId, { stage: awaitingCp.stage, auto_run_next: true })
                      refresh()
                    } catch (err) { setActionError(err.message) }
                  }}
                >
                  ✅ 批准并继续
                </button>
                <button className="btn btn-danger btn-sm" onClick={handleAbort}>🛑 中止</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── All artifacts viewer (read-only tabs) ───────────── */}
      <ArtifactViewer checkpoints={checkpoints} projectId={projectId} onRefresh={refresh} />

      {/* ── Agent log ───────────────────────────────────────── */}
      <AgentLogPanel projectId={projectId} projectStatus={project?.status} />
    </div>
  )
}

// ── Artifact viewer (read-only, tabbed) ───────────────────────
function ArtifactViewer({ checkpoints, projectId, onRefresh }) {
  const allArtifacts = {}
  checkpoints.forEach(cp => {
    Object.entries(cp.artifacts ?? {}).forEach(([k, v]) => {
      if (typeof v === 'object' && v !== null) allArtifacts[k] = { data: v, stage: cp.stage }
    })
  })

  const keys = Object.keys(allArtifacts)
  const [active, setActive] = useState(null)
  const activeKey = active ?? keys[0]

  if (keys.length === 0) return null

  const item = allArtifacts[activeKey]

  return (
    <div className="card space-y-4">
      <h2 className="text-sm font-semibold text-gray-300">📄 产出物 (Artifacts)</h2>

      <div className="flex flex-wrap gap-2">
        {keys.map(k => (
          <button
            key={k}
            onClick={() => setActive(k)}
            className={`btn btn-sm ${activeKey === k ? 'btn-primary' : 'btn-ghost'}`}
          >
            {k}
          </button>
        ))}
      </div>

      {item && (
        <div>
          <div className="text-xs text-gray-500 mb-1">
            阶段: <span className="text-gray-400">{item.stage}</span>
          </div>
          <pre className="json-editor text-xs overflow-auto max-h-80">
            {JSON.stringify(item.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

// ── Agent log panel ───────────────────────────────────────────
function AgentLogPanel({ projectId, projectStatus }) {
  const { data } = useQuery({
    queryKey: ['log', projectId],
    queryFn: () => getAgentLog(projectId, 300),
    refetchInterval: 4000,
  })

  const lines = data?.lines ?? []
  const hasError = lines.some(l => l.includes('[ERROR]'))
  const isStuck = projectStatus === 'in_progress' && lines.length <= 1

  // Color-code individual log lines
  function lineClass(line) {
    if (line.includes('[ERROR]')) return 'text-red-400'
    if (line.includes('---')) return 'text-yellow-400'
    if (line.includes('completed') || line.includes('✓')) return 'text-emerald-400'
    if (line.includes('WARNING') || line.includes('warn')) return 'text-amber-400'
    return 'text-purple-300'
  }

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-300">🖥️ Agent 实时日志</h2>
        <span className={`flex items-center gap-1.5 text-xs ${hasError ? 'text-red-400' : 'text-emerald-400'}`}>
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${hasError ? 'bg-red-400' : 'bg-emerald-400 animate-pulse'}`} />
          {hasError ? '有错误' : 'LIVE'}
        </span>
      </div>

      {/* Diagnostic banner — shown when agent exits immediately */}
      {isStuck && (
        <div className="rounded-lg border border-amber-700/50 bg-amber-900/20 px-4 py-3 space-y-2">
          <div className="text-amber-400 font-semibold text-sm">⚠️ Agent 无响应</div>
          <div className="text-xs text-gray-400 space-y-1">
            <p>日志停止更新，可能是以下原因：</p>
            <ol className="list-decimal list-inside space-y-0.5 text-gray-500">
              <li><span className="text-gray-300">Claude CLI 未安装</span>：运行 <code className="bg-surface-800 px-1 rounded">npm install -g @anthropic-ai/claude-code</code></li>
              <li><span className="text-gray-300">API Key 未配置</span>：检查项目根目录的 <code className="bg-surface-800 px-1 rounded">.env</code> 文件，确认 <code className="bg-surface-800 px-1 rounded">ANTHROPIC_API_KEY=sk-...</code></li>
              <li><span className="text-gray-300">claude.cmd 不在 PATH</span>：在终端运行 <code className="bg-surface-800 px-1 rounded">claude --version</code> 验证</li>
            </ol>
          </div>
        </div>
      )}

      {/* Error details banner */}
      {hasError && (
        <div className="rounded-lg border border-red-700/50 bg-red-900/20 px-4 py-3">
          <div className="text-red-400 font-semibold text-sm mb-1">✗ Agent 启动失败</div>
          <div className="text-xs text-gray-400">
            查看下方日志获取详细错误信息，修复后可重新点击"🚀 运行此阶段"。
          </div>
        </div>
      )}

      <pre className="bg-surface-950 rounded-lg p-4 text-xs font-mono
                      max-h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed border border-surface-700">
        {lines.length > 0
          ? lines.map((line, i) => (
              <span key={i} className={lineClass(line)}>{line}{'\n'}</span>
            ))
          : <span className="text-gray-600">暂无日志...</span>
        }
      </pre>
    </div>
  )
}

// ── Page root ─────────────────────────────────────────────────
export default function MonitorPage() {
  const { projectId } = useParams()
  if (!projectId) return <ProjectList />
  return <ProjectMonitor projectId={projectId} />
}
