/**
 * api.js — typed wrappers around the web_api FastAPI backend.
 * All calls go through the Vite proxy (/api → localhost:8000).
 */
import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 30_000 })

http.interceptors.response.use(
  (r) => r.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Unknown error'
    return Promise.reject(new Error(msg))
  }
)

// ── Projects ──────────────────────────────────────────────────

export const createProject = (body) =>
  http.post('/project/create', body)

export const createProjectWithUpload = (formData) =>
  http.post('/project/create/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
  })

export const getProjectStatus = (id) =>
  http.get(`/project/${id}/status`)

export const runStage = (id, body = {}) =>
  http.post(`/project/${id}/run_stage`, body)

// ── Checkpoints ───────────────────────────────────────────────

export const getCheckpoint = (id, stage) =>
  http.get(`/project/${id}/checkpoint`, { params: stage ? { stage } : {} })

export const patchCheckpoint = (id, body) =>
  http.patch(`/project/${id}/checkpoint`, body)

export const approveStage = (id, body) =>
  http.post(`/project/${id}/approve`, body)

export const abortProject = (id, reason) =>
  http.post(`/project/${id}/abort`, { reason: reason || 'User aborted via Web UI' })

export const getAgentLog = (id, tail = 300) =>
  http.get(`/project/${id}/log`, { params: { tail } })

// ── Health ────────────────────────────────────────────────────

export const getHealth = () => http.get('/health')
