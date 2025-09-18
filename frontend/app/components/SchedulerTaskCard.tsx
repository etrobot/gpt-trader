import React from 'react'
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import type { SimpleTaskInfo } from '@/types'

export type SchedulerTaskCardProps = {
  icon: React.ReactNode
  title: string
  description?: string
  task?: SimpleTaskInfo | null
  emptyText?: string
}

function getStatusIcon(status?: SimpleTaskInfo['status']) {
  switch (status) {
    case 'completed':
      return <CheckCircle className="h-4 w-4 text-green-500" />
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-500" />
    case 'running':
      return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />
    default:
      return <RefreshCw className="h-4 w-4 text-gray-400" />
  }
}

function getStatusBadge(status?: SimpleTaskInfo['status']) {
  const variants: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    completed: 'default',
    failed: 'destructive',
    running: 'secondary',
    pending: 'outline',
  }
  const label = status || '未知'
  const variant = variants[status || ''] || 'outline'
  return <Badge variant={variant}>{label}</Badge>
}

export function SchedulerTaskCard({ icon, title, description, task, emptyText = '当前无运行任务' }: SchedulerTaskCardProps) {
  return (
    <Card>
      <CardHeader>
          <div className="flex items-center gap-2">
            {icon}
            {description}
          </div>
      </CardHeader>
      <CardContent>
        {task ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              {getStatusIcon(task.status)}
              {getStatusBadge(task.status)}
            </div>
            {typeof task.progress === 'number' && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>进度</span>
                  <span>{Math.round((task.progress || 0) * 100)}%</span>
                </div>
                <Progress value={(task.progress || 0) * 100} />
              </div>
            )}
            {task.message && (
              <p className="text-sm text-muted-foreground">{task.message}</p>
            )}
          </div>
        ) : (
          <p className="text-muted-foreground">{emptyText}</p>
        )}
      </CardContent>
    </Card>
  )
}
