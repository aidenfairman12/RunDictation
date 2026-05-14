'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { VoiceSpeedControls, JobResult, useJobRunner } from './shared'

export default function TextTab() {
  const [text, setText] = useState('')
  const [voice, setVoice] = useState('auto')
  const [speed, setSpeed] = useState('1.0')
  const { job, busy, downloading, submitJob, handleDownload } = useJobRunner()

  function resolveVoice() {
    if (voice !== 'auto') return voice
    return Math.random() > 0.5 ? 'de-DE-KatjaNeural' : 'de-DE-ConradNeural'
  }

  async function handleGenerate() {
    await submitJob('/jobs', {
      text: text.trim(),
      voice: resolveVoice(),
      speed: parseFloat(speed),
    })
  }

  return (
    <div>
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
        <VoiceSpeedControls
          voice={voice}
          setVoice={setVoice}
          speed={speed}
          setSpeed={setSpeed}
          disabled={busy}
        />
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

      <JobResult job={job} downloading={downloading} onDownload={handleDownload} />
    </div>
  )
}
