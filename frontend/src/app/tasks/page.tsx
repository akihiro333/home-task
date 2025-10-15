'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { apiClient } from '@/lib/api'
import { Task, WebSocketMessage, CreateTaskRequest, UpdateTaskRequest } from '@/types'
import TaskModal from '@/components/TaskModal'

export default function TasksPage() {
  const router = useRouter()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState<string | undefined>()
  const [loadingMore, setLoadingMore] = useState(false)
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('')
  const [assigneeFilter, setAssigneeFilter] = useState('')
  
  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | undefined>()
  
  // Mock users (in real app, fetch from API)
  const [users] = useState([
    { id: 1, email: 'admin@acme.com' },
    { id: 2, email: 'member@acme.com' }
  ])
  
  // Mock org ID (in real app, get from JWT or context)
  const [orgId] = useState(1)
  
  // WebSocket connection
  const [ws, setWs] = useState<WebSocket | null>(null)

  const loadTasks = useCallback(async (cursor?: string, reset = false) => {
    try {
      if (reset) {
        setLoading(true)
      } else {
        setLoadingMore(true)
      }

      const params: any = { limit: 20 }
      if (cursor) params.cursor = cursor
      if (statusFilter) params.status = statusFilter
      if (assigneeFilter) params.assignee = parseInt(assigneeFilter)

      const response = await apiClient.getTasks(orgId, params)
      
      if (reset) {
        setTasks(response.tasks)
      } else {
        setTasks(prev => [...prev, ...response.tasks])
      }
      
      setHasMore(response.has_more)
      setNextCursor(response.next_cursor)
    } catch (err) {
      if (err instanceof Error && err.message.includes('401')) {
        router.push('/login')
        return
      }
      setError(err instanceof Error ? err.message : 'Failed to load tasks')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [orgId, statusFilter, assigneeFilter, router])

  // Initialize WebSocket connection
  useEffect(() => {
    if (!apiClient.getAccessToken()) {
      router.push('/login')
      return
    }

    const websocket = apiClient.createWebSocket(orgId)
    
    websocket.onopen = () => {
      console.log('WebSocket connected')
      setWs(websocket)
    }
    
    websocket.onmessage = (event) => {
      const message: WebSocketMessage = JSON.parse(event.data)
      
      switch (message.type) {
        case 'task_created':
          if (message.task) {
            setTasks(prev => [message.task!, ...prev])
          }
          break
        case 'task_updated':
          if (message.task) {
            setTasks(prev => prev.map(task => 
              task.id === message.task!.id ? message.task! : task
            ))
          }
          break
        case 'task_deleted':
          if (message.task) {
            setTasks(prev => prev.filter(task => task.id !== message.task!.id))
          }
          break
        case 'ping':
          websocket.send(JSON.stringify({ type: 'pong' }))
          break
      }
    }
    
    websocket.onclose = () => {
      console.log('WebSocket disconnected')
      setWs(null)
    }
    
    websocket.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    return () => {
      websocket.close()
    }
  }, [orgId, router])

  // Load initial tasks
  useEffect(() => {
    loadTasks(undefined, true)
  }, [loadTasks])

  const handleCreateTask = async (taskData: CreateTaskRequest) => {
    await apiClient.createTask(orgId, taskData)
    // Task will be added via WebSocket
  }

  const handleUpdateTask = async (taskData: UpdateTaskRequest) => {
    if (!editingTask) return
    await apiClient.updateTask(editingTask.id, taskData)
    // Task will be updated via WebSocket
  }

  const handleDeleteTask = async (taskId: number) => {
    if (confirm('Are you sure you want to delete this task?')) {
      await apiClient.deleteTask(taskId)
      // Task will be removed via WebSocket
    }
  }

  const handleLogout = async () => {
    await apiClient.logout()
    router.push('/login')
  }

  const openCreateModal = () => {
    setEditingTask(undefined)
    setIsModalOpen(true)
  }

  const openEditModal = (task: Task) => {
    setEditingTask(task)
    setIsModalOpen(true)
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'todo': return 'bg-gray-100 text-gray-800'
      case 'doing': return 'bg-blue-100 text-blue-800'
      case 'done': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString()
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg">Loading tasks...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">Tasks</h1>
              <div className="ml-4 flex items-center space-x-2">
                <div className={`w-2 h-2 rounded-full ${ws ? 'bg-green-500' : 'bg-red-500'}`}></div>
                <span className="text-sm text-gray-500">
                  {ws ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={openCreateModal}
                className="btn btn-primary"
              >
                Create Task
              </button>
              <button
                onClick={handleLogout}
                className="btn btn-secondary"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
          <div className="flex space-x-4">
            <div>
              <label htmlFor="status-filter" className="block text-sm font-medium text-gray-700">
                Status
              </label>
              <select
                id="status-filter"
                className="mt-1 input w-32"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All</option>
                <option value="todo">To Do</option>
                <option value="doing">Doing</option>
                <option value="done">Done</option>
              </select>
            </div>
            <div>
              <label htmlFor="assignee-filter" className="block text-sm font-medium text-gray-700">
                Assignee
              </label>
              <select
                id="assignee-filter"
                className="mt-1 input w-48"
                value={assigneeFilter}
                onChange={(e) => setAssigneeFilter(e.target.value)}
              >
                <option value="">All</option>
                {users.map(user => (
                  <option key={user.id} value={user.id}>
                    {user.email}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Tasks List */}
        <div className="space-y-4">
          {tasks.map(task => (
            <div key={task.id} className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <h3 className="text-lg font-medium text-gray-900">
                      {task.title}
                    </h3>
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(task.status)}`}>
                      {task.status.toUpperCase()}
                    </span>
                  </div>
                  
                  {task.description && (
                    <p className="text-gray-600 mb-3">{task.description}</p>
                  )}
                  
                  <div className="flex items-center space-x-4 text-sm text-gray-500">
                    {task.assignee_id && (
                      <span>
                        Assigned to: {users.find(u => u.id === task.assignee_id)?.email || 'Unknown'}
                      </span>
                    )}
                    {task.due_date && (
                      <span>Due: {formatDate(task.due_date)}</span>
                    )}
                    <span>Created: {formatDate(task.created_at)}</span>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2 ml-4">
                  <button
                    onClick={() => openEditModal(task)}
                    className="text-primary-600 hover:text-primary-700 text-sm"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDeleteTask(task.id)}
                    className="text-red-600 hover:text-red-700 text-sm"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Load More */}
        {hasMore && (
          <div className="text-center mt-8">
            <button
              onClick={() => loadTasks(nextCursor)}
              disabled={loadingMore}
              className="btn btn-secondary disabled:opacity-50"
            >
              {loadingMore ? 'Loading...' : 'Load More'}
            </button>
          </div>
        )}

        {tasks.length === 0 && !loading && (
          <div className="text-center py-12">
            <p className="text-gray-500 text-lg">No tasks found</p>
            <button
              onClick={openCreateModal}
              className="mt-4 btn btn-primary"
            >
              Create your first task
            </button>
          </div>
        )}
      </main>

      {/* Task Modal */}
      <TaskModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={editingTask ? handleUpdateTask : handleCreateTask}
        task={editingTask}
        users={users}
      />
    </div>
  )
}