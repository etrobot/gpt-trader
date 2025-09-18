import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CheckCircle, XCircle, Clock } from 'lucide-react'

export type SchedulerOverviewProps = {
  scheduler_running?: boolean
  enabled?: boolean
  last_run?: string | null
  next_run?: string | null
}

export function formatDateTime(dateStr?: string | null) {
  if (!dateStr) return '未知'
  try {
    return new Date(dateStr).toLocaleString('zh-CN')
  } catch {
    return String(dateStr)
  }
}

export function SchedulerOverviewCard({ scheduler_running, enabled, last_run, next_run }: SchedulerOverviewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          调度器概览
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">运行状态</p>
            <div className="flex items-center gap-2">
              {scheduler_running ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
              <span className="font-medium">
                {scheduler_running ? '运行中' : '已停止'}
              </span>
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">任务启用</p>
            <div className="flex items-center gap-2">
              {enabled ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
              <Badge variant={enabled ? 'default' : 'destructive'}>
                {enabled ? '已启用' : '已禁用'}
              </Badge>
            </div>
          </div>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">上次运行</p>
            <span className="text-sm font-mono">{formatDateTime(last_run)}</span>
          </div>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">下次运行</p>
            <span className="text-sm font-mono">{formatDateTime(next_run)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
