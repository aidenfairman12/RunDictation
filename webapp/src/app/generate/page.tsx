'use client'

import { useEffect, useRef, useState } from 'react'
import { Mic, Download, Loader2, AlertCircle, LogOut } from 'lucide-react'

const VOICES = [
  { value: 'auto', label: 'Auto (random)' },
  { value: 'de-DE-KatjaNeural', label: 'Katja (female)' },
  { value: 'de-DE-ConradNeural', label: 'Conrad (male)' },
]

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || ''

type JobState =
  | { phase: 'idle' }
  | { phase: 'submitting' }
  | { phase: 'polling'; jobId: string }
  | { phase: 'done'; jobId: string }
  | { phase: 'error'; message: string }

export default function GeneratePage() {
  const [text, setText] = useState('')
  const [voice, setVoice] = useState('auto')
  const [speed, setSpeed] = useState('1.0')
  const [job, setJob] = useState<JobState>({ phase: 'idle' })
  const [downloading, setDownloading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval>>()

  useEffect(() => {
    if (BACKEND_URL) {
      fetch(`${BACKEND_URL}/health`).catch(() => {})
    }
  }, [])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  function getToken() {
    return sessionStorage.getItem('auth_token') || ''
  }

  function resolveVoice() {
    if (voice !== 'auto') return voice
    return Math.random() > 0.5 ? 'de-DE-KatjaNeural' : 'de-DE-ConradNeural'
  }

  async function handleGenerate() {
    const token = getToken()
    if (!token || !text.trim()) return

    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = undefined
    }

    setJob({ phase: 'submitting' })

    try {
      const res = await fetch(`${BACKEND_URL}/jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token,
        },
        body: JSON.stringify({
          text: text.trim(),
          voice: resolveVoice(),
          speed: parseFloat(speed),
        }),
      })

      if (!res.ok) throw new Error('Failed to submit job')
      const { jobId } = await res.json()

      setJob({ phase: 'polling', jobId })

      pollRef.current = setInterval(async () => {
        try {
          const pollRes = await fetch(`${BACKEND_URL}/jobs/${jobId}`, {
            headers: { 'Authorization': token },
          })
          const data = await pollRes.json()

          if (data.status === 'done') {
            clearInterval(pollRef.current!)
            pollRef.current = undefined
            setJob({ phase: 'done', jobId })
          } else if (data.status === 'error') {
            clearInterval(pollRef.current!)
            pollRef.current = undefined
            setJob({ phase: 'error', message: data.error || 'TTS generation failed' })
          }
        } catch {
          clearInterval(pollRef.current!)
          pollRef.current = undefined
          setJob({ phase: 'error', message: 'Lost connection to server' })
        }
      }, 2000)
    } catch {
      setJob({ phase: 'error', message: 'Could not reach the server. It may be waking up — try again in 30 seconds.' })
    }
  }

  async function handleDownload() {
    if (job.phase !== 'done') return
    setDownloading(true)
    try {
      const res = await fetch(`${BACKEND_URL}/files/${job.jobId}`, {
        headers: { 'Authorization': getToken() },
      })
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'dictation.mp3'
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  async function handleLogout() {
    sessionStorage.removeItem('auth_token')
    await fetch('/api/auth', { method: 'DELETE' })
    window.location.href = '/'
  }

  const busy = job.phase === 'submitting' || job.phase === 'polling'

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
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Paste German text here..."
            disabled={busy}
            rows={10}
            className="w-full resize-y rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm leading-relaxed text-slate-900 placeholder-slate-400 focus:border-slate-500 focus:outline-none disabled:opacity-50"
          />
          <p className="mt-1 text-right text-xs text-slate-400">
            {text.length.toLocaleString()} characters
          </p>

          <div className="mt-4 flex flex-wrap items-end gap-4">
            <div className="min-w-[160px] flex-1">
              <label className="mb-1 block text-xs font-medium text-slate-500">Voice</label>
              <select
                value={voice}
                onChange={e => setVoice(e.target.value)}
                disabled={busy}
                className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none disabled:opacity-50"
              >
                {VOICES.map(v => (
                  <option key={v.value} value={v.value}>{v.label}</option>
                ))}
              </select>
            </div>

            <div className="w-24">
              <label className="mb-1 block text-xs font-medium text-slate-500">Speed</label>
              <input
                type="number"
                value={speed}
                onChange={e => setSpeed(e.target.value)}
                disabled={busy}
                min="0.5"
                max="2.0"
                step="0.05"
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none disabled:opacity-50"
              />
            </div>

            <button
              onClick={handleGenerate}
              disabled={busy || !text.trim()}
              className="rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:opacity-50"
            >
              {busy ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {job.phase === 'submitting' ? 'Submitting...' : 'Generating...'}
                </span>
              ) : (
                'Generate'
              )}
            </button>
          </div>

          {job.phase === 'done' && (
            <div className="mt-6 flex items-center gap-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
              <button
                onClick={handleDownload}
                disabled={downloading}
                className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                {downloading ? 'Downloading...' : 'Download MP3'}
              </button>
              <p className="text-xs text-emerald-600">Ready to download</p>
            </div>
          )}

          {job.phase === 'error' && (
            <div className="mt-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
              <p className="text-sm text-red-600">{job.message}</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
