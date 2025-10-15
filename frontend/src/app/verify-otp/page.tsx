'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Cookies from 'js-cookie'
import { apiClient } from '@/lib/api'

export default function VerifyOtpPage() {
  const router = useRouter()
  const [code, setCode] = useState('')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    // Get email from session storage
    const storedEmail = sessionStorage.getItem('otp_email')
    if (!storedEmail) {
      router.push('/login')
      return
    }
    setEmail(storedEmail)
  }, [router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const tokens = await apiClient.verifyOtp(email, code)
      
      // Store tokens
      apiClient.setAccessToken(tokens.access_token)
      Cookies.set('refresh_token', tokens.refresh_token, {
        httpOnly: false,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'strict'
      })

      // Clear stored email
      sessionStorage.removeItem('otp_email')
      
      // Redirect to tasks page
      router.push('/tasks')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'OTP verification failed')
    } finally {
      setLoading(false)
    }
  }

  const handleCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/\D/g, '').slice(0, 6)
    setCode(value)
  }

  if (!email) {
    return <div>Loading...</div>
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Verify Code</h1>
          <p className="mt-2 text-gray-600">
            We've sent a 6-digit code to <strong>{email}</strong>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="code" className="block text-sm font-medium text-gray-700">
              Verification Code
            </label>
            <input
              id="code"
              name="code"
              type="text"
              required
              maxLength={6}
              className="mt-1 input text-center text-2xl tracking-widest"
              placeholder="000000"
              value={code}
              onChange={handleCodeChange}
            />
            <p className="mt-1 text-sm text-gray-500">
              Enter the 6-digit code from your email
            </p>
          </div>

          <button
            type="submit"
            disabled={loading || code.length !== 6}
            className="w-full btn btn-primary disabled:opacity-50"
          >
            {loading ? 'Verifying...' : 'Verify Code'}
          </button>
        </form>

        <div className="text-center">
          <Link href="/login" className="text-primary-600 hover:text-primary-500">
            Back to login
          </Link>
        </div>

        <div className="text-center text-sm text-gray-500">
          <p>In development, check the backend logs for the OTP code</p>
        </div>
      </div>
    </div>
  )
}