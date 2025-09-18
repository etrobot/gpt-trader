export type FactorRecord = {
  symbol: string
  name?: string
  当前价格?: number
  收盘?: number
  支撑位?: number
  支撑因子?: number
  动量?: number
  动量因子?: number
  支撑位评分?: number
  动量评分?: number
  支撑评分?: number
  综合评分?: number
  涨跌幅?: number
  [key: string]: any
}

export type ColumnSpec = {
  key: string
  label: string
  type: 'number' | 'integer' | 'percent' | 'string' | 'score'
  description?: string
  sortable?: boolean
}

export type FactorMeta = {
  id: string
  name: string
  description?: string
  columns: ColumnSpec[]
}

export type FactorListResponse = { items: FactorMeta[] }

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export type TaskResult = {
  task_id: string
  status: TaskStatus
  progress: number
  message: string
  created_at: string
  completed_at?: string
  top_n: number
  selected_factors?: string[]
  data?: FactorRecord[]
  count?: number
  error?: string
}

export type RunResponse = {
  task_id: string
  status: TaskStatus
  message: string
}

export type TaskMeta = {
  task_id?: string
  created_at?: string
  count?: number
}

export type NewsItem = {
  title: string
  content: string
  url: string
  published_at: string
  source: string
  symbol: string
}

export type NewsEvaluation = {
  overall_score: number
  detailed_scores: Record<string, number>
  top_scoring_criterion: string
  top_score: number
}

export type NewsEvaluationResult = {
  symbol: string
  base_coin: string
  news_count: number
  evaluation: NewsEvaluation
  news_summary: string
  news_items?: NewsItem[]
  error?: string
}

export type SunburstData = {
  name: string
  value?: number
  children?: SunburstData[]
}

export type NewsEvaluationResponse = {
  data: NewsEvaluationResult[]
  count: number
  sunburst_data?: SunburstData
  summary: {
    total_symbols: number
    total_news: number
    evaluation_model: string
    top_performer: NewsEvaluationResult | null
    average_score: number
  }
}

export type NewsTaskResult = {
  task_id: string
  status: TaskStatus
  progress: number
  message: string
  created_at: string
  completed_at?: string
  result?: NewsEvaluationResponse
  error?: string
}

export type RankingData = {
  task_id: string
  completed_at: string
  count: number
  data: FactorRecord[]
}

// Scheduler types
export type SimpleTaskInfo = {
  task_id?: string
  status?: string
  progress?: number
  message?: string
}

export type SchedulerStatusDTO = {
  scheduler_running: boolean
  enabled: boolean
  last_run?: string | null
  next_run?: string | null
  current_analysis_task?: SimpleTaskInfo | null
  current_news_task?: SimpleTaskInfo | null
  current_candlestick_task?: SimpleTaskInfo | null
  current_timeframe_review_task?: SimpleTaskInfo | null
}
