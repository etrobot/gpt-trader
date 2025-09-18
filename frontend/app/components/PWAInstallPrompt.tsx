import React from 'react'
import { Download, X } from 'lucide-react'
import { usePWA } from '../hooks/usePWA'

export function PWAInstallPrompt() {
  const { isInstallable, installApp } = usePWA()
  const [showPrompt, setShowPrompt] = React.useState(false)

  React.useEffect(() => {
    if (isInstallable) {
      // Show prompt after a delay to not be intrusive
      const timer = setTimeout(() => setShowPrompt(true), 3000)
      return () => clearTimeout(timer)
    }
  }, [isInstallable])

  if (!isInstallable || !showPrompt) return null

  const handleInstall = async () => {
    const success = await installApp()
    if (success) {
      setShowPrompt(false)
    }
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 bg-card border rounded-lg p-4 z-50 shadow-lg dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <Download size={20} className="text-teal-600 dark:text-teal-400" />
            <h3 className="font-medium text-foreground dark:text-gray-200">安装应用</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-3 dark:text-gray-400">
            将Crypto分析系统添加到主屏幕，获得更好的使用体验
          </p>
          <div className="flex space-x-2">
            <button
              onClick={handleInstall}
              className="px-3 py-1.5 bg-teal-600 text-white text-sm rounded-md hover:bg-teal-700 transition-colors dark:bg-teal-700 dark:hover:bg-teal-600"
            >
              安装
            </button>
            <button
              onClick={() => setShowPrompt(false)}
              className="px-3 py-1.5 text-sm rounded-md hover:bg-secondary/50 transition-colors dark:text-gray-300 dark:hover:bg-gray-800"
            >
              稍后
            </button>
          </div>
        </div>
        <button
          onClick={() => setShowPrompt(false)}
          className="text-muted-foreground hover:text-foreground ml-2 dark:text-gray-400 dark:hover:text-gray-200"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  )
}