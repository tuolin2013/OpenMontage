/**
 * ArtifactEditor — inline JSON / form editor for pipeline artifacts.
 *
 * Shows the AI-generated JSON (script, scene_plan, etc.) in a
 * contenteditable textarea. User can edit it, then click
 * "✅ 保存并批准" to save and unlock the next stage.
 */
import React, { useState, useEffect } from 'react'
import { patchCheckpoint, approveStage } from '../api'

export default function ArtifactEditor({ projectId, stage, artifactKey, initialData, onSaved }) {
  const [jsonText, setJsonText] = useState('')
  const [parseError, setParseError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [approving, setApproving] = useState(false)
  const [notes, setNotes] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (initialData !== undefined) {
      setJsonText(JSON.stringify(initialData, null, 2))
      setParseError(null)
      setSaved(false)
    }
  }, [initialData, stage])

  function handleChange(e) {
    const val = e.target.value
    setJsonText(val)
    setSaved(false)
    try {
      JSON.parse(val)
      setParseError(null)
    } catch (err) {
      setParseError(err.message)
    }
  }

  async function handleSave() {
    let parsed
    try { parsed = JSON.parse(jsonText) }
    catch (err) { setParseError(err.message); return }

    setSaving(true)
    try {
      await patchCheckpoint(projectId, {
        stage,
        artifact_key: artifactKey,
        artifact_data: parsed,
      })
      setSaved(true)
      setParseError(null)
    } catch (err) {
      setParseError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleApprove() {
    // Save first if unsaved
    if (!saved) {
      await handleSave()
      if (parseError) return
    }
    setApproving(true)
    try {
      await approveStage(projectId, { stage, notes, auto_run_next: true })
      onSaved?.()
    } catch (err) {
      setParseError(err.message)
    } finally {
      setApproving(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          编辑 · {artifactKey}
        </span>
        {saved && (
          <span className="text-xs text-emerald-400">✓ 已保存</span>
        )}
      </div>

      <textarea
        className="json-editor w-full"
        rows={16}
        value={jsonText}
        onChange={handleChange}
        spellCheck={false}
        aria-label={`编辑 ${artifactKey} JSON`}
      />

      {parseError && (
        <div className="text-xs text-red-400 font-mono bg-red-900/20 rounded px-3 py-2">
          ⚠ JSON 解析错误: {parseError}
        </div>
      )}

      <div className="space-y-2">
        <textarea
          className="form-textarea text-sm"
          rows={2}
          placeholder="审批说明（可选）：填写修改意见或备注..."
          value={notes}
          onChange={e => setNotes(e.target.value)}
          aria-label="审批说明"
        />
        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving || !!parseError}
            className="btn btn-secondary btn-sm"
          >
            {saving ? '保存中...' : '💾 保存编辑'}
          </button>
          <button
            onClick={handleApprove}
            disabled={approving || !!parseError}
            className="btn btn-success flex-1"
          >
            {approving
              ? <><span className="stage-spinner inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> 处理中...</>
              : '✅ 保存并批准 → 解锁下一阶段'
            }
          </button>
        </div>
      </div>
    </div>
  )
}
