
interface ProgressBarProps {
  progress: number
  message: string
}

export function ProgressBar({ progress, message }: ProgressBarProps) {
  const pct = Math.max(0, Math.min(1, progress)) * 100
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span>{message}</span>
        <span>{pct.toFixed(0)}%</span>
      </div>
      <div className="w-full h-2 bg-secondary/50 rounded">
        <div 
          className="bg-primary h-2 rounded transition-all duration-300" 
          style={{ width: `${pct}%` }} 
        />
      </div>
    </div>
  )
}