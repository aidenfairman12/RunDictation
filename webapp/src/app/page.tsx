'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { KeyRound } from 'lucide-react'

export default function LoginPage() {
  const [passphrase, setPassphrase] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const res = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ passphrase }),
    })

    if (res.ok) {
      const { token } = await res.json()
      sessionStorage.setItem('auth_token', token)
      router.push('/generate')
    } else {
      setError('Wrong passphrase')
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-2xl border border-slate-700/60 bg-slate-800/50 p-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-sky-500/25 bg-sky-500/15">
            <KeyRound className="h-5 w-5 text-sky-400" />
          </div>
          <h1 className="text-xl font-bold text-white">RunDictation</h1>
        </div>

        <input
          type="password"
          value={passphrase}
          onChange={e => setPassphrase(e.target.value)}
          placeholder="Passphrase"
          className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-sky-500 focus:outline-none"
          autoFocus
        />

        {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading || !passphrase}
          className="mt-4 w-full rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-sky-400 disabled:opacity-50"
        >
          {loading ? 'Checking...' : 'Enter'}
        </button>
      </form>
    </div>
  )
}
