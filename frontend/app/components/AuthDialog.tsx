import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog'
import { Button } from './ui/button'
import { AuthService } from '../services/auth'

interface AuthDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
  title?: string
  description?: string
}

export function AuthDialog({ 
  open, 
  onOpenChange, 
  onSuccess,
  title = "用户身份验证",
  description = "请输入用户名和邮箱以继续操作（弱校验模式）"
}: AuthDialogProps) {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!username.trim() || !email.trim()) {
      setError('请输入用户名和邮箱')
      return
    }

    // 简单的邮箱格式验证
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setError('请输入有效的邮箱地址')
      return
    }

    setLoading(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const result = await AuthService.authenticate(username, email)
      
      if (result.success) {
        setSuccessMessage(result.message || '认证成功')
        // 延迟关闭对话框，让用户看到成功消息
        setTimeout(() => {
          onSuccess()
          onOpenChange(false)
          // 清空表单
          setUsername('')
          setEmail('')
          setSuccessMessage(null)
        }, 1500)
      } else {
        setError(result.error || '认证失败')
      }
    } catch (err) {
      setError('验证失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = () => {
    setUsername('')
    setEmail('')
    setError(null)
    setSuccessMessage(null)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px] dark:bg-gray-900 dark:border-gray-700">
        <DialogHeader>
          <DialogTitle className="dark:text-gray-200">{title}</DialogTitle>
          <DialogDescription className="dark:text-gray-400">
            {description}
          </DialogDescription>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="username" className="text-sm font-medium dark:text-gray-300">
              用户名
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-800 dark:border-gray-700 dark:text-gray-200 dark:placeholder-gray-400"
              placeholder="请输入用户名"
              disabled={loading}
            />
          </div>
          
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium dark:text-gray-300">
              邮箱
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-800 dark:border-gray-700 dark:text-gray-200 dark:placeholder-gray-400"
              placeholder="请输入邮箱"
              disabled={loading}
            />
          </div>
          
          {error && (
            <div className="text-pink-500 text-sm bg-red-50 p-2 rounded dark:bg-red-900/20 dark:border-red-800">
              {error}
            </div>
          )}

          {successMessage && (
            <div className="text-green-600 text-sm bg-green-50 p-2 rounded dark:bg-green-900/20 dark:border-green-800 dark:text-green-400">
              {successMessage}
            </div>
          )}

          <DialogFooter>
            <Button 
              type="button" 
              variant="outline" 
              onClick={handleCancel}
              disabled={loading}
              className="dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              取消
            </Button>
            <Button 
              type="submit" 
              disabled={loading || !username.trim() || !email.trim() || !!successMessage}
            >
              {loading ? '验证中...' : successMessage ? '认证成功' : '确认'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}