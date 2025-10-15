'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Cookies from 'js-cookie'
import { apiClient } from '@/lib/api'

export default function LoginPage() {
  const router = useRouter()
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await apiClient.login(formData.email, formData.password)
      
      if (response.otp_required) {
        // Store email for OTP verification
        sessionStorage.setItem('otp_email', formData.email)
        router.push('/verify-otp')
      } else if (response.access_token) {
        // Direct login (shouldn't happen with OTP enabled)
        apiClient.setAccessToken(response.access_token)
        if (response.refresh_token) {
          Cookies.set('refresh_token', response.refresh_token, {
            httpOnly: false,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict'
          })
        }
        router.push('/tasks')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleLogin = async () => {
    setLoading(true)
    setError('')

    try {
      // Check if Google Client ID is configured
      const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID
      
      if (googleClientId) {
        // TODO: Implement actual Google OAuth
        setError('Google OAuth not implemented in this demo')
      } else {
        // Use mock token for development
        const tokens = await apiClient.loginWithGoogle('MOCK_ID_TOKEN')
        
        apiClient.setAccessToken(tokens.access_token)
        Cookies.set('refresh_token', tokens.refresh_token, {
          httpOnly: false,
          secure: process.env.NODE_ENV === 'production',
          sameSite: 'strict'
        })
        
        router.push('/tasks')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: value
    }))
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Sign In</h1>
          <p className="mt-2 text-gray-600">Access your organization's tasks</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              className="mt-1 input"
              placeholder="admin@acme.com"
              value={formData.email}
              onChange={handleChange}
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              className="mt-1 input"
              placeholder="••••••••"
              value={formData.password}
              onChange={handleChange}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn btn-primary disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-gray-50 text-gray-500">Or continue with</span>
          </div>
        </div>

        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          className="w-full btn btn-secondary disabled:opacity-50"
        >
          {process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ? 'Google' : 'Google (Mock)'}
        </button>

        <div className="text-center">
          <Link href="/register" className="text-primary-600 hover:text-primary-500">
            Don't have an organization? Create one
          </Link>
        </div>

        <div className="text-center text-sm text-gray-500">
          <p>Demo accounts:</p>
          <p>admin@acme.com / admin123</p>
          <p>member@acme.com / member123</p>
        </div>
      </div>
    </div>
  )
}