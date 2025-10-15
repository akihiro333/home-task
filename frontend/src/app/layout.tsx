import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TaskManager - Multi-tenant Task Management',
  description: 'Organize your team\'s tasks efficiently',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 min-h-screen">
        {children}
      </body>
    </html>
  )
}