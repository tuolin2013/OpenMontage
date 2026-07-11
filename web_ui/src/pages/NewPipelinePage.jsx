/**
 * NewPipelinePage — 新建商品视频流水线表单
 *
 * 功能：
 * 1. 从 GET /api/products 读取 products.xlsx 数据
 * 2. 下拉选择商品 → 自动填充名称、卖点、白底图（实拍图 URL）
 * 3. 用户可手动覆盖任意字段
 * 4. Identity Preservation：LoRA 路径、ControlNet 权重
 * 5. 透明底图：优先使用 xlsx 中的实拍图 URL；用户也可上传本地 PNG
 */
import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listProducts, createProject, createProjectWithUpload } from '../api'

const PIPELINES = [
  { id: 'ecommerce-promo',     label: '🛒 电商促销',    desc: '产品展示 · 种草 · 直播引流' },
  { id: 'animated-explainer',  label: '🎬 动画解说',    desc: '概念讲解 · 产品说明 · 教育内容' },
  { id: 'cinematic',           label: '🎥 电影风格',    desc: 'Trailer · Teaser · 品牌大片' },
  { id: 'avatar-spokesperson', label: '🤖 AI 代言人',   desc: '虚拟主播 · 唇形同步 · 演讲' },
  { id: 'screen-demo',         label: '🖥️ 屏幕演示',   desc: 'SaaS 产品 · App 走查 · 教程' },
  { id: 'animation',           label: '✨ 动态图形',    desc: 'Motion Graphics · 社媒内容' },
]

export default function NewPipelinePage() {
  const navigate = useNavigate()
  const fileRef = useRef(null)

  // Product catalog from xlsx
  const [catalog, setCatalog] = useState([])
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [selectedProduct, setSelectedProduct] = useState(null)

  // Form
  const [form, setForm] = useState({
    pipeline: 'ecommerce-promo',
    product_name: '',
    key_selling_points: '',
    project_name: '',
    lora_model_path: '',
    controlnet_weight: '',
  })

  // PNG upload (local file override)
  const [pngFile, setPngFile] = useState(null)
  const [pngPreview, setPngPreview] = useState(null)   // local blob URL
  const [imageUrl, setImageUrl] = useState('')         // from xlsx

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Load product catalog on mount
  useEffect(() => {
    listProducts()
      .then(data => setCatalog(data?.products ?? []))
      .catch(() => setCatalog([]))
      .finally(() => setCatalogLoading(false))
  }, [])

  function set(k, v) { setForm(f => ({ ...f, [k]: v })) }

  // When user picks a product from dropdown — auto-fill
  function handleProductSelect(e) {
    const name = e.target.value
    if (!name) {
      setSelectedProduct(null)
      setImageUrl('')
      return
    }
    const p = catalog.find(c => c.name === name)
    if (!p) return
    setSelectedProduct(p)
    set('product_name', p.name)
    set('key_selling_points', p.selling_points || '')
    setImageUrl(p.image_url || '')
    // Clear any local upload preview if switching products
    setPngFile(null)
    setPngPreview(null)
  }

  function handlePngChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('请上传图片文件（PNG / WebP 透明底图）')
      return
    }
    setPngFile(file)
    setPngPreview(URL.createObjectURL(file))
    setError(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.product_name.trim()) { setError('请填写或选择商品名称'); return }
    if (!form.key_selling_points.trim()) { setError('请填写核心卖点'); return }
    setError(null)
    setLoading(true)
    try {
      let result
      if (pngFile) {
        // User uploaded a local PNG → multipart
        const fd = new FormData()
        fd.append('product_name', form.product_name)
        fd.append('key_selling_points', form.key_selling_points)
        fd.append('pipeline', form.pipeline)
        if (form.project_name) fd.append('project_name', form.project_name)
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
          // Pass xlsx image URL as the transparent_png_path when no local file
          transparent_png_path: imageUrl || undefined,
        })
      }
      navigate(`/monitor/${result.project_id}`)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // The image shown in the preview area
  const previewSrc = pngPreview || imageUrl || null

  return (
    <div className="max-w-2xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold text-white mb-1">✨ 新建商品视频流水线</h1>
      <p className="text-gray-400 text-sm mb-8">
        选择商品自动填充信息，或手动输入。
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">

        {/* ── Product selector ────────────────────────────── */}
        <section className="card space-y-3">
          <h2 className="text-sm font-semibold text-gray-300">📦 从商品库选择</h2>
          {catalogLoading ? (
            <div className="flex items-center gap-2 text-gray-500 text-sm py-2">
              <span className="stage-spinner inline-block w-4 h-4 border-2 border-gray-600 border-t-brand-400 rounded-full" />
              加载商品库...
            </div>
          ) : catalog.length === 0 ? (
            <p className="text-xs text-gray-500">商品库为空或后端未启动，请手动填写。</p>
          ) : (
            <div className="space-y-2">
              <select
                className="form-input bg-surface-800"
                onChange={handleProductSelect}
                defaultValue=""
              >
                <option value="">— 请选择商品（自动填充）—</option>
                {catalog.map(p => (
                  <option key={p.name} value={p.name}>
                    {p.name}{p.brand ? ` · ${p.brand}` : ''}{p.spec ? ` · ${p.spec}` : ''}
                  </option>
                ))}
              </select>

              {/* Selected product quick info */}
              {selectedProduct && (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-surface-900 border border-surface-700">
                  {selectedProduct.image_url && (
                    <img
                      src={selectedProduct.image_url}
                      alt={selectedProduct.name}
                      className="w-14 h-14 object-contain rounded-lg bg-white flex-shrink-0"
                    />
                  )}
                  <div className="text-xs text-gray-400 space-y-0.5 min-w-0">
                    <div className="text-white font-medium">{selectedProduct.name}</div>
                    {selectedProduct.brand && <div>品牌: {selectedProduct.brand}</div>}
                    {selectedProduct.category && <div>品类: {selectedProduct.category}</div>}
                    {selectedProduct.spec && <div>规格: {selectedProduct.spec}</div>}
                    {selectedProduct.price && <div>价格: ¥{selectedProduct.price}</div>}
                    {selectedProduct.key_ingredients && (
                      <div className="truncate">核心成分: {selectedProduct.key_ingredients}</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

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
              可选。assets / compose 阶段将自动读取这些参数，保持商品视觉一致性。
            </p>
          </div>
          <div>
            <label className="form-label">LoRA 模型路径</label>
            <input
              className="form-input font-mono text-xs"
              placeholder="/models/lora/my-product-v1.safetensors"
              value={form.lora_model_path}
              onChange={e => set('lora_model_path', e.target.value)}
            />
          </div>
          <div>
            <label className="form-label">
              ControlNet 权重
              <span className="text-gray-600 normal-case font-normal ml-1">(0.0 – 2.0)</span>
            </label>
            <input
              className="form-input"
              type="number" min="0" max="2" step="0.05"
              placeholder="0.75"
              value={form.controlnet_weight}
              onChange={e => set('controlnet_weight', e.target.value)}
            />
          </div>

          {/* Product image — shows xlsx URL or local upload */}
          <div>
            <label className="form-label">
              产品实拍图（白底图）
              {imageUrl && !pngFile && (
                <span className="ml-2 text-xs text-emerald-400 font-normal">✓ 已从商品库读取</span>
              )}
            </label>

            {/* Preview area */}
            <div
              onClick={() => fileRef.current?.click()}
              className={`mt-1 flex flex-col items-center justify-center gap-2 border-2 border-dashed
                rounded-xl p-4 cursor-pointer transition-colors min-h-[100px]
                ${previewSrc
                  ? 'border-brand-500 bg-brand-600/10'
                  : 'border-surface-600 hover:border-brand-500 bg-surface-900'}`}
            >
              {previewSrc ? (
                <>
                  <img
                    src={previewSrc}
                    alt="product preview"
                    className="max-h-32 max-w-full object-contain rounded-lg bg-white"
                  />
                  <span className="text-xs text-gray-500">
                    {pngFile ? pngFile.name : '商品库图片 · 点击上传本地文件替换'}
                  </span>
                </>
              ) : (
                <>
                  <span className="text-3xl">🖼️</span>
                  <span className="text-sm text-gray-500">
                    选择商品后自动填入，或点击上传本地 PNG / WebP
                  </span>
                </>
              )}
            </div>
            <input
              ref={fileRef} type="file" accept="image/png,image/webp"
              className="hidden" onChange={handlePngChange}
            />
            {imageUrl && !pngFile && (
              <p className="text-xs text-gray-600 mt-1 break-all">{imageUrl}</p>
            )}
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
            ? <>
                <span className="stage-spinner inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full mr-2" />
                正在初始化项目...
              </>
            : '🚀 创建项目并启动生产'
          }
        </button>

      </form>
    </div>
  )
}
