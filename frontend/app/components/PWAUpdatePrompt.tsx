import { RefreshCw } from 'lucide-react'

interface PWAUpdatePromptProps {
  onUpdate: () => void
  show: boolean
}

export function PWAUpdatePrompt({ onUpdate, show }: PWAUpdatePromptProps) {
  if (!show) return null

  return (
    <div className="fixed top-4 left-4 right-4 md:left-auto md:right-4 md:w-80 bg-teal-600 text-white rounded-lg shadow-lg p-4 z-50 dark:bg-teal-700">
      <div className="flex items-center space-x-2 mb-2">
        <RefreshCw size={20} />
        <h3 className="font-medium">新版本可用</h3>
      </div>
      <p className="text-sm text-teal-100 mb-3 dark:text-teal-200">
        发现新版本，点击更新获得最新功能
      </p>
      <button
        onClick={onUpdate}
        className="w-full px-3 py-2 bg-background text-teal-600 text-sm font-medium rounded-md hover:bg-secondary/50 transition-colors dark:bg-gray-800 dark:text-teal-300 dark:hover:bg-gray-700"
      >
        立即更新
      </button>
    </div>
  )
}