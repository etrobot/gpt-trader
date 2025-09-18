import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { TrendingUp, Newspaper, Clock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useMediaQuery } from '@/hooks/use-media-query'

interface NavItem {
  path: string
  label: string
  icon: React.ComponentType<{ className?: string }>
}

const navItems: NavItem[] = [
  {
    path: '/',
    label: '定时任务',
    icon: Clock
  },
  {
    path: '/analysis',
    label: '分析',
    icon: TrendingUp
  },
  {
    path: '/news-evaluation',
    label: '新闻评估',
    icon: Newspaper
  }
]

export function UnifiedNavigation() {
  const location = useLocation()
  const isDesktop = useMediaQuery('(min-width: 768px)')

  if (isDesktop) {
    return (
      <nav className="hidden md:flex flex-col p-2 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-r border-border z-50 w-24">
        <div className="flex flex-col items-center gap-2 mt-4">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path

            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={cn(
                  "flex flex-col items-center justify-center gap-1 p-3 rounded-lg transition-colors w-full",
                  "hover:bg-accent hover:text-accent-foreground",
                  isActive
                    ? "text-primary bg-primary/10"
                    : "text-muted-foreground"
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
                <span className="text-xs font-medium truncate">{item.label}</span>
              </NavLink>
            )
          })}
        </div>
      </nav>
    )
  }

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-t border-border z-50 md:hidden">
      <div className="flex items-center justify-around h-16 max-w-md mx-auto px-4">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = location.pathname === item.path

          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={cn(
                "flex flex-col items-center justify-center gap-1 px-3 py-2 rounded-lg transition-colors min-w-0 flex-1",
                "hover:bg-accent hover:text-accent-foreground",
                isActive
                  ? "text-primary bg-primary/10"
                  : "text-muted-foreground"
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              <span className="text-xs font-medium truncate">{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}