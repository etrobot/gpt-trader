import { useState, useEffect, useCallback } from 'react'
import { ResultsTable } from './ResultsTable'
import { TaskProgressCard } from './TaskProgressCard'
import { ThemeToggle } from './ThemeToggle'
import { SchedulerStatus } from './SchedulerStatus'
import { TaskResult } from '../types'
import { api, createTaskStatusSSE, ApiError } from '../services/api'
import { useIsMobile } from '../hooks/use-mobile'

export function DashboardPage() {
  const [currentTask, setCurrentTask] = useState<TaskResult | null>(null)
  const [previousResults, setPreviousResults] = useState<TaskResult | null>(null)
  const [isTaskRunning, setIsTaskRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isMobile = useIsMobile()

  const handleTaskUpdate = useCallback((task: TaskResult) => {
    setCurrentTask(task)
    const running = task.status === 'pending' || task.status === 'running'
    setIsTaskRunning(running)
    if (running) {
      setError(null)
    }
  }, [])

  const handleTaskComplete = useCallback((task: TaskResult) => {
    setCurrentTask(task)
    setPreviousResults(task)
    setIsTaskRunning(false)
  }, [])

  const handleTaskError = useCallback((errorMessage: string) => {
    setError(errorMessage)
    setIsTaskRunning(false)
  }, [])

  const startStreaming = useCallback((taskId: string) => {
    const stopStream = createTaskStatusSSE(
      taskId,
      handleTaskUpdate,
      handleTaskComplete,
      handleTaskError
    )
    return stopStream
  }, [handleTaskUpdate, handleTaskComplete, handleTaskError])

  const handleRunAnalysis = useCallback((taskId: string) => {
    setError(null)
    setIsTaskRunning(true)
    api.getTaskStatus(taskId).then(setCurrentTask)
    const stopStream = startStreaming(taskId)
    ;(window as any).stopTaskStream = stopStream
  }, [startStreaming])
  
  const handleStopAnalysis = useCallback(() => {
    if (currentTask?.task_id) {
      api.stopTask(currentTask.task_id).then(() => {
        // The poller will eventually update the status to cancelled
      })
    }
  }, [currentTask])

  useEffect(() => {
    // Fetch latest results on initial load
    api.getLatestResults().then(task => {
      if (task && 'task_id' in task) {
        setCurrentTask(task)
        if (task.status === 'running' || task.status === 'pending') {
          setIsTaskRunning(true)
          const stopStream = startStreaming(task.task_id)
          ;(window as any).stopTaskStream = stopStream
        }
      }
    }).catch(err => {
      // Handle case where there are no results yet
      if (err instanceof ApiError && err.status === 404) {
        console.info("No previous results found.")
      } else {
        setError(err.message)
      }
    })

    return () => {
      if ((window as any).stopTaskStream) {
        (window as any).stopTaskStream()
      }
    }
  }, [startStreaming])

  return (
    <div className={`${isMobile ? 'p-2 pb-20' : 'p-6 pb-20'} space-y-4`}>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Crypto Analysis Dashboard</h1>
        <ThemeToggle />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 dark:bg-red-900/20 dark:border-red-800">
          <div className="text-pink-800 dark:text-pink-200">错误: {error}</div>
          <button 
            onClick={() => setError(null)}
            className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm dark:bg-red-700 dark:hover:bg-red-600"
          >
            关闭
          </button>
        </div>
      )}

      {isTaskRunning && currentTask && (
        <TaskProgressCard task={currentTask} title="分析任务进度" />
      )}

      <SchedulerStatus />

      <ResultsTable
        data={isTaskRunning ? (previousResults?.data || []) : (currentTask?.data || [])}
        factorMeta={[]} // This should be fetched from the /factors endpoint
        onRunAnalysis={handleRunAnalysis}
        onStopAnalysis={handleStopAnalysis}
        currentTaskId={currentTask?.task_id}
        isTaskRunning={isTaskRunning}
      />
    </div>
  )
}
