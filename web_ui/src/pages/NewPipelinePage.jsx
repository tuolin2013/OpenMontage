/**
 * NewPipelinePage — 新建商品视频流水线表单
 *
 * - 基础输入：商品名称、核心卖点
 * - 视觉特征保真区 (Identity Preservation)：LoRA 模型路径、产品透明底图上传
 * - 流水线选择
 * - 创建后跳转到 Pipeline Monitor
 */
import React, { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { createProject, createProjectWithUpload } from '../api'

const PIPELINES = [
  { id: 'ecommerce-promo',    label: '🛒 电商促销',    desc: '产品展示 · 种草 · 直播引流' },
  { id: 'animated-explainer', label: '🎬 动画解说',    desc: '概念讲解 · 产品说明 · 教育内容' },
  { id: 'cinematic',          label: '🎥 电影风格',    desc: 'Trailer · Teaser · 品牌大片' },
  { id: 'avatar-spokesperson',label: '🤖 AI 代言人',   desc: '虚拟主播 · 唇形同步 · 演讲' },
  { id: 'screen-demo',        label: '🖥️ 屏幕演示',   desc: 'SaaS 产品 · App 走查 · 教程' },
  { id: 'animation',          label: '✨ 动态图形',    desc: 'Motion Graphics · 社媒内容' },
]

export default function NewPipelinePage() {
  const navigate = useNavigate()
  const fileRef = useRef(null)

  const [form, setForm] = useState({
    pipeline: 'ecommerce-promo',
    product_name: '',
    key_selling_points: '',
    project_name: '',
    lora_model_path: '',
    controlnet_weight: '',
  })
  const [pngFile, setPngFile] = useState(null)
  const [pngPreview, setPngPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function set(k, v) { setForm(f => ({ ...f, [k]: v })) }

  function handlePngChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('请上传图片文件（PNG / WebP 透明底图）')
      return
    }
    setPngFile(file)
    setPngPreview(URL.createObjectURL(file))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.product_name.trim()) { setError('请填写商品名称'); return }
    if (!form.key_selling_points.trim()) { setError('请填写核心卖点'); return }
    setError(null)
    setLoading(true)
    try {
      let result
      if (pngFile) {
        const fd = new FormData()
        fd.append('product_name', form.product_name)
        fd.append('key_selling_points', form.key_selling_points)
        fd.append('pipeline', form.pipeline)
        fd.append('project_name', form.project_name)
        if (form.lora_model_path) fd.append('lora_model_path', form.lora_model_path)
        if (form.controlnet_weight) fd.append('controlnet_weight', form.controlnet_weight)
        fd.append('transparent_png', pngFile)
        result = await createProjectWithUpload(fd)
      } else {
        result = await createProject({
          product_name: form.product_name,
          key_selling_points: form.key_selling_points,
          pipeline: form.pipeline,
          project_name: form.project_name || undefined,
          lora_model_path: form.lora_model_path || undefined,
          controlnet_weight: form.controlnet_weight ? parseFloat(form.controlnet_weight) : undefined,
        })
      }
      navigate(`/monitor/${result.project_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold text-white mb-1">✨ 新建商品视频流水线</h1>
      <p className="text-gray-400 text-sm mb-8">
        填写商品信息，选择流水线，系统将自动初始化项目并启动第一阶段。
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* ── Pipeline selector ───────────────────────────── */}
        <section>
          <label className="form-label">生产流水线</label>
          <div className="grid grid-cols-2 gap-3 mt-2">
            {PIPELINES.map(p => (
              <button
                type="button"
                key={p.id}
                onClick={() => set('pipeline', p.id)}
                className={`text-left p-3 rounded-xl border transition-all
                  ${form.pipeline === p.id
                    ? 'bg-brand-600/20 border-brand-500 text-white'
                    : 'bg-surface-800 border-surface-700 text-gray-400 hover:border-surface-500'}`}
              >
                <div className="font-semibold text-sm">{p.label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{p.desc}</div>
              </button>
            ))}
          </div>
        </section>

        {/* ── Core brief ───────────────────────────────────── */}
        <section className="card space-y-4">
          <h2 className="text-sm font-semibold text-gray-300">📋 基础信息</h2>
          <div>
            <label className="form-label">商品名称 *</label>
            <input
              className="form-input"
              placeholder="例如：超薄保温杯 480ml"
              value={form.product_name}
              onChange={e => set('product_name', e.target.value)}
              required
            />
          </div>
          <div>
            <label className="form-label">核心卖点 *</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder={"例如：\n• 双层真空保温 12 小时\n• 316 食品级不锈钢\n• 极轻 220g，单手可握"}
              value={form.key_selling_points}
              onChange={e => set('key_selling_points', e.target.value)}
              required
            />
          </div>
          <div>
            <label className="form-label">项目名称（可选）</label>
            <input
              className="form-input"
              placeholder="my-product-video（留空则自动生成）"
              value={form.project_name}
              onChange={e => set('project_name', e.target.value)}
            />
          </div>
        </section>

        {/* ── Identity preservation ────────────────────────── */}
        <section className="card space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-300">🎨 视觉特征保真
              <span className="ml-2 badge badge-created">Identity Preservation</span>
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              可选。填写后，assets / compose 阶段将自动读取这些参数，保持商品视觉一致性。
            </p>
          </div>
          <div>
            <label className="form-label">LoRA 模型路径</label>
            <input
              className="form-input font-mono text-xs"
              placeholder="例如：/models/lora/my-product-v1.safetensors"
              value={form.lora_model_path}
              onChange={e => set('lora_model_path', e.target.value)}
            />
          </div>
          <div>
            <label className="form-label">ControlNet 权重 <span className="text-gray-600 normal-case font-normal">(0.0 – 2.0)</span></label>
            <input
              className="form-input"
              type="number"
              min="0" max="2" step="0.05"
              placeholder="例如：0.75"
              value={form.controlnet_weight}
              onChange={e => set('controlnet_weight', e.target.value)}
            />
          </div>
          <div>
            <label className="form-label">产品透明底图 PNG</label>
            <div
              onClick={() => fileRef.current?.click()}
              className={`mt-1 flex flex-col items-center justify-center gap-2 border-2 border-dashed
                rounded-xl p-6 cursor-pointer transition-colors
                ${pngFile
                  ? 'border-brand-500 bg-brand-600/10'
                  : 'border-surface-600 hover:border-brand-500 bg-surface-900'}`}
            >
              {pngPreview
                ? <img src={pngPreview} alt="preview"
                    className="max-h-32 max-w-full object-contain rounded-lg" />
                : <>
                    <span className="text-3xl">🖼️</span>
                    <span className="text-sm text-gray-500">点击上传透明底图 (PNG / WebP)</span>
                  </>
              }
              {pngFile && (
                <span className="text-xs text-brand-400">{pngFile.name}</span>
              )}
            </div>
            <input
              ref={fileRef} type="file" accept="image/png,image/webp"
              className="hidden" onChange={handlePngChange}
            />
          </div>
        </section>

        {error && (
          <div className="rounded-lg bg-red-900/40 border border-red-700/50 px-4 py-3 text-red-400 text-sm">
            ⚠️ {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="btn btn-primary btn-lg w-full"
        >
          {loading
            ? <><span className="stage-spinner inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full" /> 正在初始化项目...</>
            : '🚀 创建项目并启动生产'
          }
        </button>

      </form>
    </div>
  )
}
