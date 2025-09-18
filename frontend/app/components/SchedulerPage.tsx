import { useState, useEffect, useRef } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { SchedulerOverviewCard, formatDateTime } from './SchedulerOverviewCard'
import { SchedulerTaskCard } from './SchedulerTaskCard'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AuthDialog } from './AuthDialog'
import {
  Clock,
  Play,
  Pause,
  RefreshCw,
  XCircle,
  AlertCircle,
  Calendar,
  TrendingUp,
  BarChart3
} from 'lucide-react'
import { useAuth } from '@/services/auth'
import { api } from '@/services/api'
import { CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { SchedulerStatusDTO } from '@/types'

interface TimeframeAnalysis {
  analysis_date?: string
  best_timeframe?: string
  selected_timeframes?: string[]
  trading_symbols?: string[]
  recommendation?: string
  timeframe_analysis?: Record<string, {
    avg_consecutive: number
    max_consecutive: number
    trading_score: number
    symbols_count: number
    symbols_analyzed: Array<{
      symbol: string
      green_consecutive: number
      red_consecutive: number
      max_consecutive: number
    }>
  }>
  method?: string
  completed_at?: string
  file_updated?: string
  error?: string
  message?: string
}

export function SchedulerPage() {
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatusDTO | null>(null)
  const [timeframeAnalysis, setTimeframeAnalysis] = useState<TimeframeAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showAuthDialog, setShowAuthDialog] = useState(false)
  const { isAuthenticated } = useAuth()

  const requireAuth = (action: () => void) => {
    if (!isAuthenticated) {
      setShowAuthDialog(true)
      return
    }
    action()
  }

  const handleAuthSuccess = () => {
    setError(null)
    // 认证成功后可以执行之前被阻止的操作
  }

  const fetchSchedulerStatus = async (): Promise<SchedulerStatusDTO | null> => {
    try {
      const data = await api.getSchedulerStatus()
      setSchedulerStatus(data)
      setError(null)
      return data
    } catch (err) {
      console.error('Error fetching scheduler status:', err)
      setError('获取调度器状态失败')
      return null
    }
  }

  const fetchTimeframeAnalysis = async () => {
    try {
      const data = await api.getTimeframeAnalysis()
      setTimeframeAnalysis(data)
    } catch (err) {
      console.error('Error fetching timeframe analysis:', err)
      setError('获取时间周期分析失败')
    }
  }

  const toggleScheduler = async (enabled: boolean) => {
    try {
      await api.setSchedulerEnabled(enabled)
      await fetchSchedulerStatus()
    } catch (err) {
      console.error('Error toggling scheduler:', err)
      setError('切换调度器状态失败')
    }
  }

  const stopCurrentTasks = async () => {
    try {
      await api.stopScheduledTasks()
      await fetchSchedulerStatus()
    } catch (err) {
      console.error('Error stopping tasks:', err)
      setError('停止任务失败')
    }
  }

  const sseStopRef = useRef<null | (() => void)>(null)

  const startSSE = () => {
    if (sseStopRef.current) sseStopRef.current()
    sseStopRef.current = api.createSchedulerStatusSSE(
      (status) => {
        setSchedulerStatus(status)
        setError(null)
        setLoading(false)
        const isActive = (t?: { status?: string } | null) => t && (t.status === 'running' || t.status === 'pending')
        if (!isActive(status?.current_analysis_task) &&
            !isActive(status?.current_news_task) &&
            !isActive(status?.current_candlestick_task) &&
            !isActive(status?.current_timeframe_review_task)) {
          if (sseStopRef.current) { sseStopRef.current(); sseStopRef.current = null }
        }
      },
      (err) => {
        console.error(err)
        setError('调度器事件流连接失败，已退化为单次获取')
        fetchSchedulerStatus().then((s) => {
          const isActive = (t?: { status?: string } | null) => t && (t.status === 'running' || t.status === 'pending')
          const active = s && (isActive(s.current_analysis_task) || isActive(s.current_news_task) || isActive(s.current_candlestick_task) || isActive(s.current_timeframe_review_task))
          if (active && !sseStopRef.current) {
            sseStopRef.current = api.createSchedulerStatusSSE(
              (d) => { setSchedulerStatus(d); setLoading(false) },
              () => {},
              { retry: true, maxRetries: 3, baseDelayMs: 2000 }
            )
          }
        }).finally(() => setLoading(false))
      },
      { retry: true, maxRetries: 3, baseDelayMs: 2000 }
    )
  }

  useEffect(() => {
    const init = async () => {
      setLoading(true)
      try {
        await fetchTimeframeAnalysis()
        startSSE()
      } catch (e) {
        setError('初始化失败')
        setLoading(false)
      }
    }

    init()

    return () => {
      if (sseStopRef.current) sseStopRef.current()
    }
  }, [])



  if (loading) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin" />
          <span className="ml-2">加载中...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">定时任务管理</h1>
          <p className="text-muted-foreground">管理和监控自动化交易分析任务</p>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant={schedulerStatus?.enabled ? "destructive" : "default"}
            onClick={() => requireAuth(() => toggleScheduler(!schedulerStatus?.enabled))}
          >
            {schedulerStatus?.enabled ? <Pause className="h-4 w-4 mr-2" /> : <Play className="h-4 w-4 mr-2" />}
            {schedulerStatus?.enabled ? '禁用' : '启用'}定时任务
          </Button>

          <Button variant="outline" onClick={() => requireAuth(stopCurrentTasks)}>
            <XCircle className="h-4 w-4 mr-2" />
            停止当前任务
          </Button>

          <Button variant="outline" onClick={() => requireAuth(async () => { setLoading(true); await fetchTimeframeAnalysis(); startSSE(); })}>
            <RefreshCw className="h-4 w-4 mr-2" />
            刷新
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-red-700">
              <XCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="status" className="space-y-4">
        <TabsList>
          <TabsTrigger value="status">调度器状态</TabsTrigger>
          <TabsTrigger value="timeframe">时间周期分析</TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="space-y-4">
          {/* 调度器概览 */}
          <SchedulerOverviewCard
            scheduler_running={schedulerStatus?.scheduler_running}
            enabled={schedulerStatus?.enabled}
            last_run={schedulerStatus?.last_run ?? null}
            next_run={schedulerStatus?.next_run ?? null}
          />

          {/* 当前任务 */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* 分析任务 */}
            <SchedulerTaskCard
              icon={<TrendingUp className="h-4 w-4" />}
              title="分析任务"
              description="每日加密货币分析任务"
              task={schedulerStatus?.current_analysis_task ?? null}
            />

            {/* 新闻任务 */}
            <SchedulerTaskCard
              icon={<Calendar className="h-4 w-4" />}
              title="新闻评估任务"
              description="每日新闻情感分析任务"
              task={schedulerStatus?.current_news_task ?? null}
            />

            {/* K线策略任务 */}
            <SchedulerTaskCard
              icon={<BarChart3 className="h-4 w-4" />}
              title="K线策略任务"
              description="每10分钟K线模式交易策略"
              task={schedulerStatus?.current_candlestick_task ?? null}
            />

            {/* 时间周期梳理任务 */}
            <SchedulerTaskCard
              icon={<Clock className="h-4 w-4" />}
              title="时间周期梳理"
              description="每日交易时间周期分析"
              task={schedulerStatus?.current_timeframe_review_task ?? null}
            />
          </div>
        </TabsContent>

        <TabsContent value="timeframe" className="space-y-4">
          {/* 时间周期分析结果 */}
          {timeframeAnalysis?.error || timeframeAnalysis?.message ? (
            <Card>
              <CardContent className="p-6">
                <div className="text-center space-y-2">
                  <AlertCircle className="h-8 w-8 mx-auto text-muted-foreground" />
                  <p className="text-muted-foreground">
                    {timeframeAnalysis.message || timeframeAnalysis.error}
                  </p>
                </div>
              </CardContent>
            </Card>
          ) : timeframeAnalysis?.timeframe_analysis ? (
            <>
              {/* 推荐结果 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5" />
                    推荐时间周期
                  </CardTitle>
                  <CardDescription>
                    基于 {timeframeAnalysis.analysis_date} 的分析结果
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="text-3xl font-bold text-primary">
                      {timeframeAnalysis.best_timeframe || '未知'}
                    </div>
                    <div className="flex-1">
                      <p className="text-muted-foreground">
                        {timeframeAnalysis.recommendation}
                      </p>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">分析方法: </span>
                      <span>{timeframeAnalysis.method || '连续K线分析'}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">更新时间: </span>
                      <span>{formatDateTime(timeframeAnalysis.completed_at)}</span>
                    </div>
                  </div>
                  
                  {/* 显示选中的时间周期和交易币种 */}
                  {timeframeAnalysis.selected_timeframes && (
                    <div className="space-y-2">
                      <div>
                        <span className="text-muted-foreground">交易时间周期: </span>
                        <div className="flex gap-1 mt-1">
                          {timeframeAnalysis.selected_timeframes.map((tf) => (
                            <Badge key={tf} variant="outline">{tf}</Badge>
                          ))}
                        </div>
                      </div>
                      
                      {timeframeAnalysis.trading_symbols && (
                        <div>
                          <span className="text-muted-foreground">交易币种: </span>
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {timeframeAnalysis.trading_symbols.map((symbol) => (
                              <Badge key={symbol} variant="secondary">{symbol}</Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 详细分析结果 */}
              <Card>
                <CardHeader>
                  <CardTitle>各时间周期详细分析</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4">
                    {Object.entries(timeframeAnalysis.timeframe_analysis).map(([timeframe, stats]) => (
                      <div key={timeframe} className="border rounded-lg p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold">{timeframe}</h4>
                          <Badge variant={timeframe === timeframeAnalysis.best_timeframe ? "default" : "outline"}>
                            评分: {stats.trading_score.toFixed(2)}
                          </Badge>
                        </div>
                        
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-muted-foreground">平均连续:</span>
                            <div className="font-medium">{stats.avg_consecutive.toFixed(1)}</div>
                          </div>
                          <div>
                            <span className="text-muted-foreground">最大连续:</span>
                            <div className="font-medium">{stats.max_consecutive}</div>
                          </div>
                          <div>
                            <span className="text-muted-foreground">分析币种:</span>
                            <div className="font-medium">{stats.symbols_count}</div>
                          </div>
                          <div>
                            <span className="text-muted-foreground">交易评分:</span>
                            <div className="font-medium">{stats.trading_score.toFixed(2)}</div>
                          </div>
                        </div>
                        
                        {stats.symbols_analyzed.length > 0 && (
                          <div className="space-y-2">
                            <p className="text-sm text-muted-foreground">币种详情:</p>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                              {stats.symbols_analyzed.slice(0, 6).map((symbol) => (
                                <div key={symbol.symbol} className="text-xs bg-muted rounded p-2">
                                  <div className="font-medium">{symbol.symbol}</div>
                                  <div className="text-muted-foreground">
                                    绿:{symbol.green_consecutive} 红:{symbol.red_consecutive} 最大:{symbol.max_consecutive}
                                  </div>
                                </div>
                              ))}
                              {stats.symbols_analyzed.length > 6 && (
                                <div className="text-xs text-muted-foreground p-2">
                                  还有 {stats.symbols_analyzed.length - 6} 个币种...
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="p-6">
                <div className="text-center space-y-2">
                  <Clock className="h-8 w-8 mx-auto text-muted-foreground" />
                  <p className="text-muted-foreground">暂无时间周期分析数据</p>
                  <p className="text-sm text-muted-foreground">
                    时间周期分析每日 UTC 1:00 自动运行
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <AuthDialog
        open={showAuthDialog}
        onOpenChange={setShowAuthDialog}
        onSuccess={handleAuthSuccess}
        title="身份验证"
        description="请先登录后再执行定时任务操作"
      />
    </div>
  )
}