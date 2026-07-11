import React from 'react'
import { Routes, Route, NavLink, useNavigate } from 'react-router-dom'
import NewPipelinePage from './pages/NewPipelinePage'
import MonitorPage from './pages/MonitorPage'

const NAV = [
  { to: '/', label: '新建流水线', icon: '✨', end: true },
  { to: '/monitor', label: '状态机工作台', icon: '📊' },
]

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-surface-950">
        <Routes>
          <Route path="/" element={<NewPipelinePage />} />
          <Route path="/monitor" element={<MonitorPage />} />
          <Route path="/monitor/:projectId" element={<MonitorPage />} />
        </Routes>
      </main>
    </div>
  )
}

function Sidebar() {
  return (
    <aside className="w-56 shrink-0 bg-surface-900 border-r border-surface-700
                      flex flex-col py-6 px-3 gap-1">
      <div className="px-3 mb-6">
        <div className="text-lg font-bold text-white tracking-tight">🎬 OpenMontage</div>
        <div className="text-xs text-gray-500 mt-0.5">AI 视频生产平台 v2</div>
      </div>

      {NAV.map(({ to, label, icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors
             ${isActive
               ? 'bg-brand-600/20 text-brand-400 border border-brand-600/30'
               : 'text-gray-400 hover:text-gray-200 hover:bg-surface-700'}`
          }
        >
          <span>{icon}</span>
          <span>{label}</span>
        </NavLink>
      ))}
    </aside>
  )
}
