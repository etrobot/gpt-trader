import { ScoreBar } from './ScoreBar'
import { FactorRecord } from '../types'
import { SymbolLink } from './SymbolLink'

interface TopScoresListProps {
  title: string
  data: FactorRecord[]
  getScore: (record: FactorRecord) => number
  color: string
}

export function TopScoresList({ title, data, getScore, color }: TopScoresListProps) {
  const sortedData = data
    .slice()
    .sort((a, b) => getScore(b) - getScore(a))
    .slice(0, 10)

  return (
    <div className="border rounded p-4 bg-card dark:border-gray-700">
      <h2 className="font-semibold mb-3 dark:text-gray-200">{title}</h2>
      <div className="space-y-2">
        {sortedData.map((record) => {
          const score = getScore(record)
          return (
            <div key={record.symbol} className="flex items-center justify-between gap-2">
              <div className="w-28 text-left">
                <SymbolLink symbol={record.symbol} name={record.name} />
              </div>
              <ScoreBar value={score} color={color} />
              <span className="w-14 text-right text-sm dark:text-gray-300">{(score * 100).toFixed(0)}%</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
