import { ProgressBar } from './ProgressBar'
import { TaskResult } from '../types'

interface TaskProgressCardProps {
  task: TaskResult
  title?: string
}

export function TaskProgressCard({ task, title = "分析进度" }: TaskProgressCardProps) {
  if (task.status !== 'running' && task.status !== 'pending') {
    return null
  }

  return (
    <div className="border rounded p-4 bg-card dark:border-gray-700">
      <h3 className="font-semibold mb-2">{title}</h3>
      <ProgressBar progress={task.progress} message={task.message} />
    </div>
  )
}