'use client'

import { useEffect, useState } from 'react'
import { Mic, LogOut, Zap, Type } from 'lucide-react'
import TextTab from './TextTab'
import QuickTab from './QuickTab'
import { BACKEND_URL } from './shared'

type Tab = 'quick' | 'text'

export default function GeneratePage() {
  const [activeTab, setActiveTab] = useState<Tab>('quick')

  useEffect(() => {
    if (BACKEND_URL) {
      fetch(`${BACKEND_URL}/health`).catch(() => {})
    }
  }, [])

  async function handleLogout() {
    sessionStorage.removeItem('auth_token')
    await fetch('/api/auth', { method: 'DELETE' })
    window.location.href = '/'
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white/90 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-slate-50">
              <Mic className="h-4 w-4 text-slate-600" />
            </div>
            <span className="text-sm font-bold tracking-tight text-slate-900">RunDictation</span>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
          >
            <LogOut className="h-3.5 w-3.5" /> Logout
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-10">
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          {/* Tab bar */}
          <div className="mb-6 flex border-b border-slate-200">
            <button
              onClick={() => setActiveTab('quick')}
              className={`flex items-center gap-2 border-b-2 px-4 pb-3 text-sm font-medium transition-colors ${
                activeTab === 'quick'
                  ? 'border-slate-900 text-slate-900'
                  : 'border-transparent text-slate-400 hover:text-slate-600'
              }`}
            >
              <Zap className="h-4 w-4" />
              Quick Generate
            </button>
            <button
              onClick={() => setActiveTab('text')}
              className={`flex items-center gap-2 border-b-2 px-4 pb-3 text-sm font-medium transition-colors ${
                activeTab === 'text'
                  ? 'border-slate-900 text-slate-900'
                  : 'border-transparent text-slate-400 hover:text-slate-600'
              }`}
            >
              <Type className="h-4 w-4" />
              From Text
            </button>
          </div>

          {/* Tab content */}
          {activeTab === 'quick' ? <QuickTab /> : <TextTab />}
        </div>
      </main>
    </div>
  )
}
