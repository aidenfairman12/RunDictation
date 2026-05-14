import { NextRequest, NextResponse } from 'next/server'

export async function middleware(req: NextRequest) {
  const token = req.cookies.get('auth')?.value
  if (!token) {
    return NextResponse.redirect(new URL('/', req.url))
  }

  const passphrase = process.env.WEBAPP_PASSPHRASE || ''
  const encoder = new TextEncoder()
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(passphrase))
  const expected = Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')

  if (token !== expected) {
    return NextResponse.redirect(new URL('/', req.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/generate/:path*'],
}
