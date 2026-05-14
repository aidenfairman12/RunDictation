'use client'

import { useState } from 'react'
import { Loader2, Calendar, BookOpen, MessageSquare, Info } from 'lucide-react'
import {
  VoiceSpeedControls,
  JobResult,
  useJobRunner,
  useStats,
} from './shared'

const FREQ_BANDS = [
  { value: 'top100', label: 'Top 100' },
  { value: '101-500', label: '101–500' },
  { value: '501-2000', label: '501–2,000' },
  { value: '2001-5000', label: '2,001–5,000' },
]

const THEMES = [
  { value: 'all', label: 'All topics' },
  { value: 'daily_life', label: 'Daily Life' },
  { value: 'food', label: 'Food & Drink' },
  { value: 'travel', label: 'Travel' },
  { value: 'business', label: 'Business' },
]

const COUNT_OPTIONS = [25, 50, 100, 200]
const DURATION_OPTIONS = [
  { value: 15, label: '15 min' },
  { value: 30, label: '30 min' },
  { value: 60, label: '1 hour' },
]

export default function QuickTab() {
  const [mode, setMode] = useState<'l1' | 'l2'>('l1')
  const [freqBand, setFreqBand] = useState('top100')
  const [inputType, setInputType] = useState<'count' | 'duration'>('count')
  const [count, setCount] = useState(50)
  const [duration, setDuration] = useState(30)
  const [theme, setTheme] = useState('all')
  const [voice, setVoice] = useState('auto')
  const [speed, setSpeed] = useState('1.0')

  const stats = useStats()
  const { job, busy, downloading, submitJob, handleDownload } = useJobRunner()

  function getAvailableCount(band: string): number | null {
    return stats?.words.by_band[band] ?? null
  }

  function getThemeCount(t: string): number | null {
    if (t === 'all') return stats?.sentences.total ?? null
    return stats?.sentences.by_theme[t] ?? null
  }

  function estimateDuration(): string {
    const cardCount = inputType === 'count' ? count : null
    const targetMin = inputType === 'duration' ? duration : null

    if (targetMin) return `~${targetMin} min`

    const secsPerCard = mode === 'l1' ? 27.5 : 17.5
    if (cardCount) {
      const mins = Math.round((cardCount * secsPerCard) / 60)
      return `~${mins} min`
    }
    return ''
  }

  async function handleGenerate(dailyMix = false) {
    const seed = dailyMix
      ? new Date().toISOString().slice(0, 10)
      : undefined

    await submitJob('/jobs/quick', {
      type: mode,
      voice,
      speed: parseFloat(speed),
      ...(inputType === 'count' ? { count } : { duration }),
      freq_band: freqBand,
      theme,
      seed,
    })
  }

  return (
    <div className="space-y-5">
      {/* Mode toggle: L1 / L2 */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-slate-500">Mode</label>
        <div className="inline-flex rounded-lg border border-slate-300 bg-slate-50 p-0.5">
          <button
            onClick={() => setMode('l1')}
            disabled={busy}
            className={`flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-all ${
              mode === 'l1'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <BookOpen className="h-3.5 w-3.5" />
            Words (L1)
          </button>
          <button
            onClick={() => setMode('l2')}
            disabled={busy}
            className={`flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium transition-all ${
              mode === 'l2'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Sentences (L2)
          </button>
        </div>
      </div>

      {/* Frequency band selector (L1) or Theme selector (L2) */}
      {mode === 'l1' ? (
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-500">
            Frequency Band
          </label>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {FREQ_BANDS.map(band => {
              const available = getAvailableCount(band.value)
              return (
                <button
                  key={band.value}
                  onClick={() => setFreqBand(band.value)}
                  disabled={busy}
                  className={`rounded-lg border px-3 py-2.5 text-left transition-all ${
                    freqBand === band.value
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                  }`}
                >
                  <div className="text-sm font-medium">{band.label}</div>
                  {available !== null && (
                    <div
                      className={`text-xs ${
                        freqBand === band.value ? 'text-slate-300' : 'text-slate-400'
                      }`}
                    >
                      {available.toLocaleString()} words
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      ) : (
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-500">Topic</label>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {THEMES.map(t => {
              const available = getThemeCount(t.value)
              return (
                <button
                  key={t.value}
                  onClick={() => setTheme(t.value)}
                  disabled={busy}
                  className={`rounded-lg border px-3 py-2.5 text-left transition-all ${
                    theme === t.value
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                  }`}
                >
                  <div className="text-sm font-medium">{t.label}</div>
                  {available !== null && (
                    <div
                      className={`text-xs ${
                        theme === t.value ? 'text-slate-300' : 'text-slate-400'
                      }`}
                    >
                      {available.toLocaleString()} sentences
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Count vs Duration toggle */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-slate-500">Amount</label>
        <div className="space-y-3">
          <div className="inline-flex rounded-lg border border-slate-300 bg-slate-50 p-0.5">
            <button
              onClick={() => setInputType('count')}
              disabled={busy}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                inputType === 'count'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              By count
            </button>
            <button
              onClick={() => setInputType('duration')}
              disabled={busy}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                inputType === 'duration'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              By duration
            </button>
          </div>

          {inputType === 'count' ? (
            <div className="flex flex-wrap gap-2">
              {COUNT_OPTIONS.map(c => (
                <button
                  key={c}
                  onClick={() => setCount(c)}
                  disabled={busy}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium transition-all ${
                    count === c
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                  }`}
                >
                  {c} {mode === 'l1' ? 'words' : 'sentences'}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {DURATION_OPTIONS.map(d => (
                <button
                  key={d.value}
                  onClick={() => setDuration(d.value)}
                  disabled={busy}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium transition-all ${
                    duration === d.value
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400'
                  }`}
                >
                  {d.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Voice + Speed */}
      <VoiceSpeedControls
        voice={voice}
        setVoice={setVoice}
        speed={speed}
        setSpeed={setSpeed}
        disabled={busy}
      />

      {/* Generate buttons */}
      <div className="flex flex-wrap items-center gap-3 pt-1">
        <button
          onClick={() => handleGenerate(false)}
          disabled={busy}
          className="rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:opacity-50"
        >
          {busy ? (
            <span className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              {job.phase === 'submitting'
                ? 'Submitting...'
                : `Generating${
                    job.phase === 'polling' && job.cardCount
                      ? ` (${job.cardCount} cards)...`
                      : '...'
                  }`}
            </span>
          ) : (
            `Generate ${estimateDuration()}`
          )}
        </button>

        <button
          onClick={() => handleGenerate(true)}
          disabled={busy}
          className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
        >
          <Calendar className="h-4 w-4" />
          Daily Mix
        </button>

        {estimateDuration() && !busy && (
          <span className="text-xs text-slate-400">{estimateDuration()}</span>
        )}
      </div>

      {/* Stats info */}
      {stats && (
        <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
          <p className="text-xs text-slate-500">
            {stats.words.total.toLocaleString()} words and{' '}
            {stats.sentences.total.toLocaleString()} sentence pairs available.
            {mode === 'l1' && (
              <> {stats.words.with_examples.toLocaleString()} words include example sentences.</>
            )}
          </p>
        </div>
      )}

      <JobResult job={job} downloading={downloading} onDownload={handleDownload} />
    </div>
  )
}
