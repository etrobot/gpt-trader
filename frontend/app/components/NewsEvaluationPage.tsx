import { useState, useEffect, useCallback } from 'react'
import { Play, Square, RefreshCw, TrendingUp, Newspaper, AlertCircle, CheckCircle, Settings, PieChart } from 'lucide-react'
import { Button } from './ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Progress } from './ui/progress'
import { Badge } from './ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs'
import { api, createNewsTaskStatusPoller } from '../services/api'
import { NewsTaskResult, NewsEvaluationResult, TaskStatus } from '../types'
import { useIsMobile } from '../hooks/use-mobile'
import { AuthDialog } from './AuthDialog'
import NewsEvaluationSunburst from './NewsEvaluationSunburst'

export function NewsEvaluationPage() {
  const [currentTask, setCurrentTask] = useState<NewsTaskResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [latestResults, setLatestResults] = useState<NewsTaskResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [stopPoller, setStopPoller] = useState<(() => void) | null>(null)
  const [showConfigDialog, setShowConfigDialog] = useState(false)
  const [showAuthDialog, setShowAuthDialog] = useState(false)
  const [activeTab, setActiveTab] = useState('sunburst')
  
  const isMobile = useIsMobile()

  // Configuration state
  const [topN, setTopN] = useState(10)
  const [newsPerSymbol, setNewsPerSymbol] = useState(3)
  const [openaiModel] = useState("gpt-oss-120b")

  const loadLatestResults = useCallback(async () => {
    try {
      const results = await api.getLatestNewsResults()
      setLatestResults(results)
    } catch (err) {
      console.error('Failed to load latest results:', err)
    }
  }, [])

  useEffect(() => {
    loadLatestResults()
  }, [loadLatestResults])

  const handleRunClick = () => {
    setShowAuthDialog(true)
  }

  const handleAuthSuccess = () => {
    setShowConfigDialog(true)
  }

  const startNewsEvaluation = async () => {
    try {
      setIsLoading(true)
      setError(null)
      setShowConfigDialog(false)
      
      const response = await api.startNewsEvaluation(topN, newsPerSymbol, openaiModel)
      
      const initialTask: NewsTaskResult = {
        task_id: response.task_id,
        status: response.status,
        progress: 0,
        message: response.message,
        created_at: new Date().toISOString()
      }
      
      setCurrentTask(initialTask)
      
      // Start polling for updates
      const poller = createNewsTaskStatusPoller(
        response.task_id,
        (task) => {
          setCurrentTask(task)
        },
        (task) => {
          setCurrentTask(task)
          setIsLoading(false)
          loadLatestResults()
        },
        (error) => {
          setError(error)
          setIsLoading(false)
        }
      )
      
      setStopPoller(() => poller)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      setIsLoading(false)
    }
  }

  const stopNewsEvaluation = async () => {
    if (!currentTask) return
    
    try {
      await api.stopNewsTask(currentTask.task_id)
      if (stopPoller) {
        stopPoller()
        setStopPoller(null)
      }
      setIsLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop task')
    }
  }

  const getStatusIcon = (status: TaskStatus) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-600" />
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-600 animate-spin" />
      default:
        return null
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 4) return 'bg-green-500'
    if (score >= 3) return 'bg-yellow-500'
    if (score >= 2) return 'bg-orange-500'
    return 'bg-red-500'
  }

  return (
    <div className={`min-h-screen bg-background ${isMobile ? 'p-4 pb-20' : 'p-8'}`}>
      
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-2xl font-bold">新闻评估</h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
            <div className="flex gap-2">
              <Button 
                onClick={handleRunClick} 
                disabled={isLoading}
                className="flex items-center gap-2"
              >
                <Play className="h-4 w-4" />
                开始评估
              </Button>
              
              {isLoading && (
                <Button 
                  onClick={stopNewsEvaluation} 
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  <Square className="h-4 w-4" />
                  停止
                </Button>
              )}
            </div>
            
            <div className="text-sm text-muted-foreground">
              当前配置: Top {topN} 币种，每个币种 {newsPerSymbol} 条新闻
            </div>
          </div>

        {/* Current Task Status - Only show if not completed */}
        {currentTask && currentTask.status !== 'completed' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {getStatusIcon(currentTask.status)}
                任务状态
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-2">
                  <span>{currentTask.message}</span>
                  <span>{Math.round(currentTask.progress * 100)}%</span>
                </div>
                <Progress value={currentTask.progress * 100} />
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="font-medium">任务ID:</span> {currentTask.task_id}
                </div>
                <div>
                  <span className="font-medium">状态:</span>
                  <Badge variant={currentTask.status === 'running' ? 'default' : 'secondary'} className="ml-2">
                    {currentTask.status}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Error Display */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-2 text-red-600">
                <AlertCircle className="h-4 w-4" />
                <span className="font-medium">错误:</span>
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Latest Results */}
        {latestResults?.result && (
            <div>
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="sunburst" className="flex items-center gap-2">
                    <PieChart className="h-4 w-4" />
                    旭日图
                  </TabsTrigger>
                  <TabsTrigger value="list" className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    列表视图
                  </TabsTrigger>
                </TabsList>
                
                <TabsContent value="sunburst" className="mt-4">
                  <div className="flex justify-center">
                    <NewsEvaluationSunburst 
                      data={latestResults.result.sunburst_data || null}
                    />
                  </div>
                  {latestResults.result.sunburst_data && latestResults.result.sunburst_data.children && (
                    <div className="mt-4 text-center text-sm text-muted-foreground">
                      <p>旭日图展示了各评估维度下币种的得分分布</p>
                      <div className="flex justify-center flex-wrap gap-3 mt-2 text-xs">
                        {latestResults.result.sunburst_data.children.map((dimension, index) => {
                          const colors = ['bg-blue-500', 'bg-green-500', 'bg-yellow-500', 'bg-purple-500', 'bg-red-500', 'bg-cyan-500', 'bg-lime-500', 'bg-orange-500', 'bg-pink-500', 'bg-gray-500'];
                          const colorClass = colors[index % colors.length];
                          
                          return (
                            <span key={dimension.name} className="flex items-center gap-1">
                              <div className={`w-3 h-3 rounded-full ${colorClass}`}></div>
                              {dimension.name}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </TabsContent>
                
                <TabsContent value="list" className="mt-4">
                  <div className="grid gap-4">
                    {latestResults.result.data.map((result: NewsEvaluationResult) => (
                      <div key={result.symbol} className="border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <div>
                            <h3 className="font-semibold text-lg">{result.base_coin}</h3>
                            <p className="text-sm text-muted-foreground">
                              {result.news_count} 条新闻
                            </p>
                          </div>
                          <div className="text-right">
                            <div className="flex items-center gap-2">
                              <div 
                                className={`w-3 h-3 rounded-full ${getScoreColor(result.evaluation.overall_score)}`}
                              />
                              <span className="text-2xl font-bold">
                                {result.evaluation.overall_score.toFixed(1)}
                              </span>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              最高: {result.evaluation.top_scoring_criterion}
                            </p>
                          </div>
                        </div>
                        
                        <div className="mt-3">
                          <p className="text-sm text-muted-foreground">
                            {result.news_summary}
                          </p>
                        </div>
                        
                        {result.error && (
                          <div className="mt-2 text-sm text-red-600 flex items-center gap-1">
                            <AlertCircle className="h-3 w-3" />
                            {result.error}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </TabsContent>
              </Tabs>
            </div>
        )}

        {/* Configuration Dialog */}
        <Dialog open={showConfigDialog} onOpenChange={setShowConfigDialog}>
          <DialogContent className="sm:max-w-[400px]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                评估配置
              </DialogTitle>
              <DialogDescription>
                配置新闻评估参数
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">成交额Top币种数量</label>
                <select 
                  value={topN} 
                  onChange={(e) => setTopN(Number(e.target.value))}
                  className="w-full mt-1 p-2 border rounded-md"
                >
                  <option value={5}>Top 5</option>
                  <option value={10}>Top 10</option>
                  <option value={20}>Top 20</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">每个币种新闻数量</label>
                <select 
                  value={newsPerSymbol} 
                  onChange={(e) => setNewsPerSymbol(Number(e.target.value))}
                  className="w-full mt-1 p-2 border rounded-md"
                >
                  <option value={1}>1条</option>
                  <option value={3}>3条</option>
                  <option value={5}>5条</option>
                </select>
              </div>
            </div>

            <DialogFooter>
              <Button 
                variant="outline" 
                onClick={() => setShowConfigDialog(false)}
              >
                取消
              </Button>
              <Button onClick={startNewsEvaluation}>
                开始评估
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Authentication Dialog */}
        <AuthDialog
          open={showAuthDialog}
          onOpenChange={setShowAuthDialog}
          onSuccess={handleAuthSuccess}
          title="新闻评估权限验证"
          description="请输入用户名和邮箱以开始新闻评估任务"
        />
      </div>
    </div>
  )
}