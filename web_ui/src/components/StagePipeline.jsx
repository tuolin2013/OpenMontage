/**
 * StagePipeline — horizontal progress bar / node graph
 *
 * Shows: Research → Script → Scene Plan → Assets → Compose
 * Each node has status styling + a "🚀 运行此阶段" button below it.
 */
import React from 'react'

const STAGE_META = {
  research:   { label: '调研',    icon: '🔍' },
  proposal:   { label: '方案',    icon: '📋' },
  idea:       { label: '创意',    icon: '💡' },
  script:     { label: '脚本',    icon: '📝' },
  scene_plan: { label: '场景规划', icon: '🗂️' },
  assets:     { label: '素材',    icon: '🎨' },
  edit:       { label: '剪辑',    icon: '✂️' },
  compose:    { label: '合成',    icon: '🎬' },
  publish:    { label: '发布',    icon: '🚀' },
}

function nodeClass(status) {
  switch (status) {
    case 'completed':     return 'bg-emerald-700 border-emerald-500 text-white'
    case 'in_progress':   return 'bg-blue-700 border-blue-500 text-white'
    case 'awaiting_human':return 'bg-amber-700 border-amber-500 text-white'
    case 'failed':        return 'bg-red-800 border-red-600 text-white'
    default:              return 'bg-surface-700 border-surface-500 text-gray-400'
  }
}

function nodeIcon(status, meta) {
  if (status === 'completed')      return '✓'
  if (status === 'failed')         return '✗'
  if (status === 'awaiting_human') return '⏳'
  if (status === 'in_progress')
    return <span className="stage-spinner inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full" />
  return meta?.icon ?? '○'
}

function connectorClass(fromStatus) {
  if (fromStatus === 'completed')   return 'bg-emerald-600'
  if (fromStatus === 'in_progress') return 'bg-blue-600 animate-pulse'
  return 'bg-surface-600'
}

/**
 * @param {string[]} stages  - ordered list of stage ids
 * @param {object}   cpMap   - { [stage]: checkpoint }
 * @param {string}   nextStage - next runnable stage (from API)
 * @param {boolean}  runningStage - stage currently being dispatched
 * @param {function} onRunStage(stageId) - called when user clicks run button
 */
export default function StagePipeline({ stages, cpMap, nextStage, runningStage, onRunStage }) {
  if (!stages || stages.length === 0) {
    return <p className="text-sm text-gray-500">暂无阶段信息</p>
  }

  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex items-start gap-0 min-w-max">
        {stages.map((stage, i) => {
          const cp = cpMap?.[stage]
          const status = cp?.status ?? 'pending'
          const meta = STAGE_META[stage] ?? { label: stage, icon: '○' }
          const isNext = stage === nextStage
          const isRunning = stage === runningStage

          return (
            <React.Fragment key={stage}>
              {/* Node + label + button column */}
              <div className="flex flex-col items-center gap-2" style={{ minWidth: 88 }}>
                {/* Circle node */}
                <div
                  className={`w-10 h-10 rounded-full border-2 flex items-center justify-center
                               text-sm font-bold transition-all ${nodeClass(status)}`}
                  title={`${meta.label} (${status})`}
                >
                  {nodeIcon(status, meta)}
                </div>

                {/* Stage label */}
                <span className={`text-xs font-medium text-center leading-tight
                  ${status === 'completed' ? 'text-emerald-400'
                    : status === 'in_progress' ? 'text-blue-400'
                    : status === 'awaiting_human' ? 'text-amber-400'
                    : status === 'failed' ? 'text-red-400'
                    : 'text-gray-500'}`}>
                  {meta.label}
                </span>

                {/* Run button — shown for next pending stage or if explicitly runnable */}
                {onRunStage && (isNext || status === 'awaiting_human') && (
                  <button
                    onClick={() => onRunStage(stage)}
                    disabled={isRunning}
                    className={`btn btn-sm text-xs px-2 py-1 transition-all
                      ${status === 'awaiting_human'
                        ? 'btn-success'
                        : 'btn-primary'}`}
                    title={status === 'awaiting_human' ? '批准并继续' : '运行此阶段'}
                  >
                    {isRunning
                      ? <span className="stage-spinner inline-block w-3 h-3 border border-white/40 border-t-white rounded-full" />
                      : status === 'awaiting_human' ? '✅ 批准' : '🚀 运行'
                    }
                  </button>
                )}
              </div>

              {/* Connector line */}
              {i < stages.length - 1 && (
                <div className="flex items-center mt-5 flex-1" style={{ minWidth: 24 }}>
                  <div className={`h-0.5 w-full transition-colors ${connectorClass(status)}`} />
                </div>
              )}
            </React.Fragment>
          )
        })}
      </div>
    </div>
  )
}
