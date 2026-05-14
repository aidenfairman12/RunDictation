import { createHash } from 'crypto'
import { NextResponse } from 'next/server'

export async function POST(req: Request) {
  const { passphrase } = await req.json()
  const expected = process.env.WEBAPP_PASSPHRASE

  if (!expected || passphrase !== expected) {
    return NextResponse.json({ error: 'Invalid passphrase' }, { status: 401 })
  }

  const token = createHash('sha256').update(passphrase).digest('hex')

  const response = NextResponse.json({ ok: true, token })
  response.cookies.set('auth', token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 30,
    path: '/',
  })

  return response
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true })
  response.cookies.delete('auth')
  return response
}
