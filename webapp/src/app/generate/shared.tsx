'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { Download, Loader2, AlertCircle } from 'lucide-react'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || ''

const VOICES = [
  { value: 'auto', label: 'Auto (random)' },
  { value: 'de-DE-KatjaNeural', label: 'Katja (female)' },
  { value: 'de-DE-ConradNeural', label: 'Conrad (male)' },
]

export type JobState =
  | { phase: 'idle' }
  | { phase: 'submitting' }
  | { phase: 'polling'; jobId: string; cardCount?: number }
  | { phase: 'done'; jobId: string }
  | { phase: 'error'; message: string }

export type Stats = {
  words: {
    total: number
    with_examples: number
    by_band: Record<string, number>
  }
  sentences: {
    total: number
    by_theme: Record<string, number>
  }
  timing_estimates: {
    seconds_per_l1_card: number
    seconds_per_l2_card: number
  }
}

export { BACKEND_URL, VOICES }

export function getToken() {
  return sessionStorage.getItem('auth_token') || ''
}

// ---------- Voice + Speed controls ----------

export function VoiceSpeedControls({
  voice,
  setVoice,
  speed,
  setSpeed,
  disabled,
}: {
  voice: string
  setVoice: (v: string) => void
  speed: string
  setSpeed: (s: string) => void
  disabled: boolean
}) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      <div className="min-w-[160px] flex-1">
        <label className="mb-1 block text-xs font-medium text-slate-500">Voice</label>
        <select
          value={voice}
          onChange={e => setVoice(e.target.value)}
          disabled={disabled}
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
          disabled={disabled}
          min="0.5"
          max="2.0"
          step="0.05"
          className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none disabled:opacity-50"
        />
      </div>
    </div>
  )
}

// ---------- Job result banner ----------

export function JobResult({
  job,
  downloading,
  onDownload,
}: {
  job: JobState
  downloading: boolean
  onDownload: () => void
}) {
  return (
    <>
      {job.phase === 'done' && (
        <div className="mt-6 flex items-center gap-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <button
            onClick={onDownload}
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
    </>
  )
}

// ---------- Hooks ----------

export function useStats() {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    if (!BACKEND_URL) return
    const token = getToken()
    if (!token) return

    fetch(`${BACKEND_URL}/stats`, {
      headers: { Authorization: token },
    })
      .then(r => r.json())
      .then(setStats)
      .catch(() => {})
  }, [])

  return stats
}

export function useJobRunner() {
  const [job, setJob] = useState<JobState>({ phase: 'idle' })
  const [downloading, setDownloading] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval>>()

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const submitJob = useCallback(
    async (endpoint: string, body: Record<string, unknown>) => {
      const token = getToken()
      if (!token) return

      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = undefined
      }

      setJob({ phase: 'submitting' })

      try {
        const res = await fetch(`${BACKEND_URL}${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: token,
          },
          body: JSON.stringify(body),
        })

        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err.detail || 'Failed to submit job')
        }
        const data = await res.json()
        const jobId = data.jobId

        setJob({ phase: 'polling', jobId, cardCount: data.cardCount })

        pollRef.current = setInterval(async () => {
          try {
            const pollRes = await fetch(`${BACKEND_URL}/jobs/${jobId}`, {
              headers: { Authorization: token },
            })
            const pollData = await pollRes.json()

            if (pollData.status === 'done') {
              clearInterval(pollRef.current!)
              pollRef.current = undefined
              setJob({ phase: 'done', jobId })
            } else if (pollData.status === 'error') {
              clearInterval(pollRef.current!)
              pollRef.current = undefined
              setJob({
                phase: 'error',
                message: pollData.error || 'Generation failed',
              })
            }
          } catch {
            clearInterval(pollRef.current!)
            pollRef.current = undefined
            setJob({ phase: 'error', message: 'Lost connection to server' })
          }
        }, 2000)
      } catch (err) {
        setJob({
          phase: 'error',
          message:
            err instanceof Error
              ? err.message
              : 'Could not reach the server. It may be waking up — try again in 30 seconds.',
        })
      }
    },
    [],
  )

  const handleDownload = useCallback(async () => {
    if (job.phase !== 'done') return
    setDownloading(true)
    try {
      const res = await fetch(`${BACKEND_URL}/files/${job.jobId}`, {
        headers: { Authorization: getToken() },
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
  }, [job])

  const busy = job.phase === 'submitting' || job.phase === 'polling'

  return { job, busy, downloading, submitJob, handleDownload }
}
