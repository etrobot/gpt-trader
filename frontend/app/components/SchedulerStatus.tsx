import { useState, useEffect } from 'react'
import { Card } from './ui/card'
import { Button } from './ui/button'
import { Clock, Play, Square, AlertCircle } from 'lucide-react'
import { api } from '@/services/api'
import { SchedulerTaskCard } from './SchedulerTaskCard'

import type { SchedulerStatusDTO } from '@/types'

type SchedulerStatusData = SchedulerStatusDTO

export function SchedulerStatus() {
  const [status, setStatus] = useState<SchedulerStatusData | null>(null)
  const [loading, setLoading] = useState(true)
  const [stopping, setStopping] = useState(false)
  const [toggling, setToggling] = useState(false)

  const fetchStatus = async (): Promise<SchedulerStatusData | null> => {
    try {
      const data = await api.getSchedulerStatus()
      setStatus(data)
      return data
    } catch (error) {
      console.error('Failed to fetch scheduler status:', error)
      return null
    } finally {
      setLoading(false)
    }
  }

  const stopCurrentTask = async () => {
    setStopping(true)
    try {
      const result = await api.stopScheduledTasks()
      console.log(result.message)
      // Refresh status after a short delay
      setTimeout(fetchStatus, 1000)
    } catch (error) {
      console.error('Failed to stop task:', error)
    } finally {
      setStopping(false)
    }
  }

  const toggleScheduler = async () => {
    if (!status) return
    
    setToggling(true)
    try {
      const result = await api.setSchedulerEnabled(!status.enabled)
      console.log(result.message)
      // Refresh status
      fetchStatus()
    } catch (error) {
      console.error('Failed to toggle scheduler:', error)
    } finally {
      setToggling(false)
    }
  }

  useEffect(() => {
    // Prefer SSE over polling
    let stop: (() => void) | null = api.createSchedulerStatusSSE(
      (data) => {
        setStatus(data)
        setLoading(false)
        // 如果检测到不在运行中（已成功或失败/空闲），则关闭 SSE，不再继续
        const isActive = (t?: { status?: string } | null) => t && (t.status === 'running' || t.status === 'pending')
        if (!isActive(data?.current_analysis_task) &&
            !isActive(data?.current_news_task) &&
            !isActive(data?.current_candlestick_task) &&
            !isActive(data?.current_timeframe_review_task)) {
          if (stop) { stop(); stop = null }
        }
      },
      (err) => {
        console.error(err)
        // fallback: 单次抓取，并在有任务运行时自动重连 SSE（带退避）
        fetchStatus().then((s: SchedulerStatusData | null) => {
          const isActive = (t?: { status?: string } | null) => t && (t.status === 'running' || t.status === 'pending')
          const active = s && (isActive(s.current_analysis_task) || isActive(s.current_news_task) || isActive(s.current_candlestick_task) || isActive(s.current_timeframe_review_task))
          if (active && !stop) {
            stop = api.createSchedulerStatusSSE(
              (d) => { setStatus(d); setLoading(false) },
              () => {},
              { retry: true, maxRetries: 3, baseDelayMs: 2000 }
            )
          }
        })
      },
      { retry: true, maxRetries: 3, baseDelayMs: 2000 }
    )
    return () => { if (stop) stop() }
  }, [])

  if (loading) {
    return (
      <Card className="p-4">
        <div className="flex items-center space-x-2">
          <Clock className="h-5 w-5 animate-spin" />
          <span>加载调度器状态...</span>
        </div>
      </Card>
    )
  }

  if (!status) {
    return (
      <Card className="p-4">
        <div className="flex items-center space-x-2 text-red-500">
          <AlertCircle className="h-5 w-5" />
          <span>无法获取调度器状态</span>
        </div>
      </Card>
    )
  }

  const getCurrentPhase = () => {
    if (status?.current_analysis_task?.status === 'running' || status?.current_analysis_task?.status === 'pending') {
      return { text: '分析任务运行中', color: 'bg-blue-500', isRunning: true }
    }
    if (status?.current_news_task?.status === 'running' || status?.current_news_task?.status === 'pending') {
      return { text: '新闻评估运行中', color: 'bg-green-500', isRunning: true }
    }
    if (status?.current_analysis_task?.status === 'failed' || status?.current_news_task?.status === 'failed') {
      return { text: '任务失败', color: 'bg-red-500', isRunning: false }
    }
    if (status?.current_analysis_task?.status === 'cancelled' || status?.current_news_task?.status === 'cancelled') {
      return { text: '任务已取消', color: 'bg-gray-500', isRunning: false }
    }
    return { text: '空闲', color: 'bg-gray-400', isRunning: false }
  }

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return '无'
    return new Date(dateString).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'UTC',
      timeZoneName: 'short'
    })
  }

  const phaseDisplay = getCurrentPhase()
  const isTaskRunning = phaseDisplay.isRunning

  return (
    <Card className="p-2 space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium">{status.enabled ? '调度器已启用' : '调度器已禁用'}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={toggleScheduler}
            disabled={toggling}
            className="flex items-center"
          >
            <span>{toggling ? '切换中...' : (status.enabled ? '禁用' : '启用')}</span>
          </Button>
          <div className="text-xs">当前阶段:  {phaseDisplay.text} 上次运行: {formatDateTime(status.last_run ?? null)}</div>

        </div>
      </div>
      {(status.current_analysis_task || status.current_news_task) && 
             <div className="grid md:grid-cols-2 gap-4">
             <SchedulerTaskCard
               icon={<Clock className="h-4 w-4" />}
               title="分析任务"
               task={status.current_analysis_task ?? null}
               emptyText="当前无运行任务"
             />
             <SchedulerTaskCard
               icon={<Clock className="h-4 w-4" />}
               title="新闻任务"
               task={status.current_news_task ?? null}
               emptyText="当前无运行任务"
             />
           </div>
      }

      {isTaskRunning && (
        <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded">
          <div className="flex items-center space-x-2">
            <Play className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-800">
              定时任务正在运行中
            </span>
          </div>
          
          <Button
            variant="outline"
            size="sm"
            onClick={stopCurrentTask}
            disabled={stopping}
            className="flex items-center space-x-1"
          >
            <Square className="h-4 w-4" />
            <span>
              {stopping ? '停止中...' : '停止任务'}
            </span>
          </Button>
        </div>
      )}
    </Card>
  )
}