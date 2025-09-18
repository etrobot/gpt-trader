import { TaskResult, RunResponse, FactorListResponse, NewsTaskResult } from '../types'

export const API_BASE_URL: string = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:14250'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiCall<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    throw new ApiError(response.status, `HTTP error! status: ${response.status}`)
  }

  return response.json()
}

export const api = {
  async startAnalysis(topN: number = 50, selectedFactors?: string[], collectLatestData: boolean = true): Promise<RunResponse> {
    return apiCall<RunResponse>('/run', {
      method: 'POST',
      body: JSON.stringify({
        top_n: topN,
        selected_factors: selectedFactors,
        collect_latest_data: collectLatestData
      }),
    })
  },

  async getTaskStatus(taskId: string): Promise<TaskResult> {
    return apiCall<TaskResult>(`/task/${taskId}`)
  },

  async stopTask(taskId: string): Promise<TaskResult> {
    return apiCall<TaskResult>(`/task/${taskId}/stop`, { method: 'POST' })
  },


  async getLatestResults(): Promise<TaskResult> {
    return apiCall<TaskResult>('/results')
  },

  async getAllTasks(): Promise<TaskResult[]> {
    return apiCall<TaskResult[]>('/tasks')
  },

  async getFactors(): Promise<FactorListResponse> {
    return apiCall<FactorListResponse>('/factors')
  },

  async startNewsEvaluation(topN: number = 10, newsPerSymbol: number = 3, openaiModel: string = "gpt-oss-120b"): Promise<RunResponse> {
    return apiCall<RunResponse>('/run-news-evaluation', {
      method: 'POST',
      body: JSON.stringify({
        top_n: topN,
        news_per_symbol: newsPerSymbol,
        openai_model: openaiModel
      }),
    })
  },

  async getNewsTaskStatus(taskId: string): Promise<NewsTaskResult> {
    return apiCall<NewsTaskResult>(`/task/${taskId}`)
  },

  async stopNewsTask(taskId: string): Promise<NewsTaskResult> {
    return apiCall<NewsTaskResult>(`/task/${taskId}/stop`, { method: 'POST' })
  },

  async getLatestNewsResults(): Promise<NewsTaskResult> {
    return apiCall<NewsTaskResult>('/results')
  },

  async getRankingData(): Promise<any> {
    return apiCall<any>('/api/ranking')
  },

  // Scheduler and timeframe endpoints
  async getSchedulerStatus(): Promise<import('../types').SchedulerStatusDTO> {
    return apiCall<any>('/api/scheduler/status')
  },
  async setSchedulerEnabled(enabled: boolean): Promise<any> {
    return apiCall<any>(`/api/scheduler/enable?enabled=${enabled}`, { method: 'POST' })
  },
  async stopScheduledTasks(): Promise<any> {
    return apiCall<any>('/api/scheduler/stop', { method: 'POST' })
  },
  async runSchedulerNow(): Promise<any> {
    return apiCall<any>('/api/scheduler/run-now', { method: 'POST' })
  },
  async getTimeframeAnalysis(): Promise<any> {
    return apiCall<any>('/api/timeframe-analysis')
  },

  // SSE for scheduler status with optional auto-retry
  createSchedulerStatusSSE(
    onUpdate: (status: import('../types').SchedulerStatusDTO) => void,
    onError: (error: string) => void,
    options?: { retry?: boolean; maxRetries?: number; baseDelayMs?: number }
  ): () => void {
    const url = `${API_BASE_URL}/api/scheduler/events`
    let closed = false
    let es: EventSource | null = null

    const { retry = false, maxRetries = 3, baseDelayMs = 2000 } = options || {}
    let attempts = 0

    const connect = () => {
      if (closed) return
      try {
        es = new EventSource(url)
      } catch (e) {
        onError('无法连接到调度器事件流')
        return
      }

      es.addEventListener('update', handleUpdate)
      es.onerror = handleError
    }

    const handleUpdate = (ev: MessageEvent) => {
      try {
        const status = JSON.parse(ev.data)
        attempts = 0 // reset attempts on successful update
        onUpdate(status)
      } catch (err) {
        console.error('解析调度器SSE数据失败', err)
      }
    }

    const handleError = (err: any) => {
      if (closed) return
      console.error('调度器SSE连接错误', err)
      es?.close()
      onError('调度器SSE连接错误')

      if (retry && attempts < maxRetries) {
        attempts += 1
        const delay = baseDelayMs * Math.pow(2, attempts - 1)
        setTimeout(() => {
          if (!closed) connect()
        }, delay)
      }
    }

    connect()

    return () => {
      closed = true
      try {
        es?.removeEventListener('update', handleUpdate)
        es?.close()
      } catch {}
    }
  },
}

export function createTaskStatusPoller(
  taskId: string,
  onUpdate: (task: TaskResult) => void,
  onComplete: (task: TaskResult) => void,
  onError: (error: string) => void
): () => void {
  const pollInterval = setInterval(async () => {
    try {
      const taskResult = await api.getTaskStatus(taskId)
      onUpdate(taskResult)

      if (taskResult.status === 'completed' || taskResult.status === 'cancelled') {
        clearInterval(pollInterval)
        onComplete(taskResult)
      } else if (taskResult.status === 'failed') {
        clearInterval(pollInterval)
        onError(taskResult.error || '任务执行失败')
      }
    } catch (err) {
      clearInterval(pollInterval)
      onError(err instanceof Error ? err.message : 'An error occurred')
    }
  }, 1000)

  return () => clearInterval(pollInterval)
}

export function createNewsTaskStatusPoller(
  taskId: string,
  onUpdate: (task: NewsTaskResult) => void,
  onComplete: (task: NewsTaskResult) => void,
  onError: (error: string) => void
): () => void {
  const pollInterval = setInterval(async () => {
    try {
      const taskResult = await api.getNewsTaskStatus(taskId)
      onUpdate(taskResult)

      if (taskResult.status === 'completed' || taskResult.status === 'cancelled') {
        clearInterval(pollInterval)
        onComplete(taskResult)
      } else if (taskResult.status === 'failed') {
        clearInterval(pollInterval)
        onError(taskResult.error || '任务执行失败')
      }
    } catch (err) {
      clearInterval(pollInterval)
      onError(err instanceof Error ? err.message : 'An error occurred')
    }
  }, 1000)

  return () => clearInterval(pollInterval)
}

export function createTaskStatusSSE(
  taskId: string,
  onUpdate: (task: TaskResult) => void,
  onComplete: (task: TaskResult) => void,
  onError: (error: string) => void
): () => void {
  const url = `${API_BASE_URL}/task/${taskId}/events`
  let closed = false
  let es: EventSource | null = null
  try {
    es = new EventSource(url)
  } catch (e) {
    onError('无法连接到事件流，已回退到轮询')
    return createTaskStatusPoller(taskId, onUpdate, onComplete, onError)
  }

  const handleUpdate = (ev: MessageEvent) => {
    try {
      const task: TaskResult = JSON.parse(ev.data)
      onUpdate(task)
      if (task.status === 'completed' || task.status === 'cancelled') {
        es?.close()
        onComplete(task)
      } else if (task.status === 'failed') {
        es?.close()
        onError(task.error || '任务执行失败')
      }
    } catch (err) {
      console.error('解析SSE数据失败', err)
    }
  }

  const handleError = (err: any) => {
    if (closed) return
    console.error('SSE连接错误，回退到轮询', err)
    es?.close()
    // Fallback to polling on error
    const stopPolling = createTaskStatusPoller(taskId, onUpdate, onComplete, onError)
    ;(window as any).__sse_fallback_stop = stopPolling
  }

  es.addEventListener('update', handleUpdate)
  es.onerror = handleError

  return () => {
    closed = true
    try {
      es?.removeEventListener('update', handleUpdate)
      es?.close()
    } catch {}
    const stopFallback = (window as any).__sse_fallback_stop
    if (typeof stopFallback === 'function') {
      stopFallback()
      ;(window as any).__sse_fallback_stop = undefined
    }
  }
}
