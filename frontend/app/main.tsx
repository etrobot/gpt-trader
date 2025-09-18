import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { DashboardPage } from './components/DashboardPage'
import { NewsEvaluationPage } from './components/NewsEvaluationPage'
import { SchedulerPage } from './components/SchedulerPage'
import { UnifiedNavigation } from './components/UnifiedNavigation'
import { PWAInstallPrompt } from './components/PWAInstallPrompt'
import { PWAUpdatePrompt } from './components/PWAUpdatePrompt'
import { ThemeProvider } from './components/ThemeProvider'
import './index.css'

function App() {
  const [showUpdatePrompt, setShowUpdatePrompt] = useState(false)

  // PWA Update functionality
  useEffect(() => {
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js')
        .then((registration) => {
          console.log('SW registered: ', registration)
        })
        .catch((registrationError) => {
          console.log('SW registration failed: ', registrationError)
        })

      navigator.serviceWorker.addEventListener('controllerchange', () => {
        setShowUpdatePrompt(true)
      })
    }
  }, [])

  const handlePWAUpdate = () => {
    setShowUpdatePrompt(false)
    window.location.reload()
  }

  return (
    <ThemeProvider>
      <BrowserRouter>
        <div className="min-h-screen flex w-full">
          <UnifiedNavigation />
          <div className="flex-1 flex flex-col w-full">
            <Routes>
              <Route path="/" element={<SchedulerPage />} />
              <Route path="/analysis" element={<DashboardPage />} />
              <Route path="/news-evaluation" element={<NewsEvaluationPage />} />
            </Routes>
          </div>

          {/* PWA Components */}
          <PWAInstallPrompt />
          <PWAUpdatePrompt show={showUpdatePrompt} onUpdate={handlePWAUpdate} />
        </div>
      </BrowserRouter>
    </ThemeProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)