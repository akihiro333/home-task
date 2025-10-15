import Link from 'next/link'

export default function HomePage() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">TaskManager</h1>
          <p className="text-gray-600 mb-8">Multi-tenant task management for teams</p>
        </div>
        
        <div className="space-y-4">
          <Link 
            href="/login" 
            className="w-full btn btn-primary block text-center"
          >
            Sign In
          </Link>
          
          <Link 
            href="/register" 
            className="w-full btn btn-secondary block text-center"
          >
            Create Organization
          </Link>
        </div>
        
        <div className="text-center text-sm text-gray-500">
          <p>Demo organizations:</p>
          <p>acme.example.local | beta.example.local</p>
        </div>
      </div>
    </div>
  )
}