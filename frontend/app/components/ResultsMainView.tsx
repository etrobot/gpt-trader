import { useState } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { ScoreBar } from './ScoreBar'
import { SymbolLink } from './SymbolLink' // I will create this component later
import { FactorRecord, FactorMeta, ColumnSpec } from '../types'

type SortField = string | null
type SortDirection = 'asc' | 'desc'

interface ResultsMainViewProps {
  data: FactorRecord[]
  factorMeta?: FactorMeta[]
}

export function ResultsMainView({ data, factorMeta = [] }: ResultsMainViewProps) {
  const [sortField, setSortField] = useState<SortField | null>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  const getValue = (record: FactorRecord, key: string): any => {
    switch (key) {
      case 'name':
        return record.name || record.symbol
      case '当前价格':
        return record.当前价格 || record.收盘 || 0
      case '涨跌幅':
        return record.涨跌幅 || 0
      default:
        return (record as any)[key]
    }
  }

  const getSortedData = () => {
    if (!sortField) return data

    return [...data].sort((a, b) => {
      const aValue: any = getValue(a, sortField)
      const bValue: any = getValue(b, sortField)

      if (typeof aValue === 'string' && typeof bValue === 'string') {
        return sortDirection === 'asc' 
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue)
      }

      return sortDirection === 'asc' ? (Number(aValue) - Number(bValue)) : (Number(bValue) - Number(aValue))
    })
  }

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ChevronsUpDown className="w-4 h-4 text-muted-foreground ml-1 inline" />
    }
    return sortDirection === 'asc' ? (
      <ChevronUp className="w-4 h-4 ml-1 inline" />
    ) : (
      <ChevronDown className="w-4 h-4 ml-1 inline" />
    )
  }

  const getColumnClassName = (field: SortField, baseClassName: string) => {
    const isActive = sortField === field
    return `${baseClassName} ${isActive ? 'bg-secondary' : ''}`
  }

  const hasDataInColumn = (columnKey: string): boolean => {
    if (data.length === 0) return false
    return data.some(record => {
      const value = getValue(record, columnKey)
      if (value === null || value === undefined) return false
      if (typeof value === 'string' && value.trim() === '') return false
      if (typeof value === 'number' && isNaN(value)) return false
      return true
    })
  }

  const factorColumns: ColumnSpec[] = []
  factorMeta.forEach(f => {
    (f.columns || []).forEach(c => {
      if (!factorColumns.find(x => x.key === c.key)) {
        factorColumns.push(c)
      }
    })
  })

  const knownBaseKeys = new Set<string>([
    'symbol', 'name', '当前价格', '收盘', '涨跌幅', '综合评分'
  ])
  if (data && data.length > 0) {
    const existingKeys = new Set(factorColumns.map(c => c.key))
    const sampleKeys = Object.keys(data.reduce((acc, cur) => Object.assign(acc, cur), {} as Record<string, any>))
    sampleKeys.forEach((key) => {
      if (existingKeys.has(key) || knownBaseKeys.has(key)) return
      if (!hasDataInColumn(key)) return
      const value = getValue(data[0], key)
      let type: ColumnSpec['type'] = 'string'
      if (typeof value === 'number') {
        type = key.endsWith('评分') ? 'score' : 'number'
      } else if (typeof value === 'string') {
        type = 'string'
      }
      factorColumns.push({ key, label: key, type, sortable: true })
    })
  }

  const filteredFactorColumns = factorColumns.filter(col => hasDataInColumn(col.key))
  const factorValueColumns = filteredFactorColumns.filter(col => col.type !== 'score')
  const scoreColumns = filteredFactorColumns.filter(col => col.type === 'score')

  const renderCell = (record: FactorRecord, col: ColumnSpec) => {
    const value = getValue(record, col.key)
    switch (col.type) {
      case 'percent':
        return `${(Number(value || 0) * 100).toFixed(2)}%`
      case 'score':
        return <ScoreBar value={Number(value || 0)} />
      case 'integer':
        return Number(value || 0)
      case 'number':
        return Number(value || 0).toFixed(2)
      default:
        return String(value ?? '')
    }
  }

  return (
    <div className="overflow-auto border rounded max-h-[70vh] dark:border-gray-700" style={{ WebkitOverflowScrolling: 'touch', overscrollBehavior: 'none' }}>
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 z-30">
          <tr className="bg-muted dark:bg-gray-800">
            <th className="text-center p-2 bg-muted sticky left-0 z-30 border-r whitespace-nowrap dark:bg-gray-800 dark:border-gray-700">序号</th>
            <th className={getColumnClassName('name', "text-left p-2 cursor-pointer hover:bg-secondary/50 select-none bg-muted sticky left-[40px] z-30 border-r whitespace-nowrap dark:bg-gray-800 dark:border-gray-700 dark:hover:bg-gray-700")} onClick={() => handleSort('name')}>
              交易对{renderSortIcon('name')}
            </th>
            <th className={getColumnClassName('当前价格', "text-right p-2 cursor-pointer hover:bg-secondary/50 select-none bg-muted whitespace-nowrap dark:bg-gray-800 dark:hover:bg-gray-700")} onClick={() => handleSort('当前价格')}>
              当前价格{renderSortIcon('当前价格')}
            </th>
            <th className={getColumnClassName('涨跌幅', "text-right p-2 cursor-pointer hover:bg-secondary/50 select-none bg-muted whitespace-nowrap dark:bg-gray-800 dark:hover:bg-gray-700")} onClick={() => handleSort('涨跌幅')}>
              涨跌幅{renderSortIcon('涨跌幅')}
            </th>
            {factorValueColumns.map((col) => (
              <th
                key={col.key}
                className={getColumnClassName(col.key, `text-right p-2 cursor-pointer hover:bg-secondary/50 select-none bg-muted whitespace-nowrap dark:bg-gray-800 dark:hover:bg-gray-700`)}
                onClick={() => col.sortable !== false ? handleSort(col.key) : undefined}
              >
                {col.label}{col.sortable !== false ? renderSortIcon(col.key) : null}
              </th>
            ))}
            {scoreColumns.map((col) => (
              <th
                key={col.key}
                className={getColumnClassName(col.key, `text-left p-2 cursor-pointer hover:bg-secondary/50 select-none bg-muted whitespace-nowrap w-32 dark:bg-gray-800 dark:hover:bg-gray-700`)}
                onClick={() => col.sortable !== false ? handleSort(col.key) : undefined}
              >
                {col.label}{col.sortable !== false ? renderSortIcon(col.key) : null}
              </th>
            ))}
            <th className={getColumnClassName('综合评分', "text-left p-2 cursor-pointer hover:bg-secondary/50 select-none bg-muted whitespace-nowrap w-32 dark:bg-gray-800 dark:hover:bg-gray-700")} onClick={() => handleSort('综合评分')}>
              综合评分{renderSortIcon('综合评分')}
            </th>
          </tr>
        </thead>
        <tbody>
          {getSortedData().map((record, index) => {
            const currentPrice = record.当前价格 || record.收盘 || 0
            const changePct = record.涨跌幅 || 0
            const compositeScore = record.综合评分 || 0

            return (
              <tr key={record.symbol} className="border-t dark:border-gray-700">
                <td className="p-2 text-center text-muted-foreground font-mono sticky left-0 bg-background z-20 border-r dark:bg-gray-900 dark:border-gray-700 dark:text-gray-400">{index + 1}</td>
                <td className={getColumnClassName('name', "p-2 sticky left-[40px] bg-background z-20 border-r dark:bg-gray-900 dark:border-gray-700")}>
                  <SymbolLink symbol={record.symbol} name={record.name} />
                </td>
                <td className={getColumnClassName('当前价格', "p-2 text-right dark:text-gray-200")}>{currentPrice.toFixed(2)}</td>
                <td className={getColumnClassName('涨跌幅', `p-2 text-right ${changePct >= 0 ? 'text-pink-500' : 'text-teal-500'} dark:${changePct >= 0 ? 'text-pink-400' : 'text-teal-400'}`)}>
                  {changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%
                </td>
                {factorValueColumns.map((col) => (
                  <td key={col.key} className={getColumnClassName(col.key, "p-2 text-right dark:text-gray-200")}>
                    {renderCell(record, col)}
                  </td>
                ))}
                {scoreColumns.map((col) => (
                  <td key={col.key} className={getColumnClassName(col.key, "p-2 w-32 dark:text-gray-200")}>
                    {renderCell(record, col)}
                  </td>
                ))}
                <td className={getColumnClassName('综合评分', "p-2 w-32")}><ScoreBar value={compositeScore} color="bg-teal-500" /></td>
              </tr>
            )
          })}
          {data.length === 0 && (
            <tr>
              <td className="p-4 text-center text-muted-foreground dark:text-gray-400" colSpan={4 + filteredFactorColumns.length}>暂无数据，请点击"运行"</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}