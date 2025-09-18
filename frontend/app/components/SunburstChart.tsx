import React, { useEffect, useState } from 'react';
import * as d3 from 'd3';
import { useCategories } from '@/hooks/use-categories';
import { useTheme } from 'next-themes';
import { RefreshCw } from 'lucide-react';


interface Data {
  name: string;
  value?: number;
  children?: Data[];
}

const SunburstChart: React.FC = () => {
  const [chartData, setChartData] = useState<Data | null>(null);
  const [prevChartData, setPrevChartData] = useState<Data | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const { categories, loading: categoriesLoading, fetchCategories } = useCategories();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<string>('1year');
  const { resolvedTheme } = useTheme();
  const svgRef = React.useRef<SVGSVGElement>(null);
  const [viewBox, setViewBox] = React.useState("0,0,0,0");
  const [hoveredSegment, setHoveredSegment] = useState<{name: string, value: number} | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{x: number, y: number}>({x: 0, y: 0});
  const [isTransitioning, setIsTransitioning] = useState<boolean>(false);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  const SIZE = 600;
  const RADIUS = SIZE / 2;

  useEffect(() => {
    fetchCategories();
  }, []);

  useEffect(() => {
    if (categories && categories.length > 0 && !selectedCategory) {
      setSelectedCategory(categories[0].id);
    }
  }, [categories, selectedCategory]);

  useEffect(() => {
    if (!selectedCategory) {
      setChartData(null);
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      setIsTransitioning(true);

      // Store previous data for transition
      setPrevChartData(chartData);

      try {
        const response = await fetch(`/api/database/sunburst-data?category_id=${selectedCategory}&time_range=${timeRange}`);
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const result = await response.json();
        if (result.success) {
          const newData = transformDataForD3(result.data);

          // Add a small delay to show the transition
          setTimeout(() => {
            setChartData(newData);
            setIsTransitioning(false);
          }, 150);
        } else {
          setChartData(null);
          setIsTransitioning(false);
          throw new Error(result.message || 'Failed to fetch data');
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An unknown error occurred');
        setIsTransitioning(false);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [selectedCategory, timeRange, refreshKey]);

  const transformDataForD3 = (data: any[]): Data | null => {
    if (!data || data.length === 0) return null;

    const transform = (item: any): Data => {
      const children = item.children ? item.children.map(transform) : undefined;

      let value = item.value;
      if (children && children.length > 0) {
        value = children.reduce((sum: number, child: Data) => sum + (child.value || 0), 0);
      }

      return {
        name: item.name || item.id,
        value: value,
        children: children
      };
    };

    const transformedData = data.map(transform);

    if (transformedData.length === 1 &&
        transformedData[0].children &&
        transformedData[0].children.length > 1) {
      return {
        name: 'root',
        children: transformedData[0].children
      };
    }

    return {
      name: 'root',
      children: transformedData
    };
  };

  const partition = (data: Data) =>
    d3.partition<Data>().size([2 * Math.PI, RADIUS])(
      d3
        .hierarchy(data)
        .sum((d) => d.value || 0)
        .sort((a, b) => (b.value || 0) - (a.value || 0))
    );

  const getColor = () => {
    const macaronColors = [
      '#FFB3C6', // Pink macaron
      '#FFC9B3', // Peach macaron
      '#FFFAB3', // Lemon macaron
      '#C6FFB3', // Pistachio macaron
      '#B3F0FF', // Blue macaron
      '#D4B3FF', // Lavender macaron
      '#FFD4B3', // Orange macaron
      '#B3FFD4', // Mint macaron
      '#FFB3F0', // Rose macaron
      '#F0B3FF', // Violet macaron
      '#B3CFFF', // Sky blue macaron
      '#CFFFB3'    // Light green macaron
    ];

  if (!chartData?.children) return d3.scaleOrdinal<string, string>().range([macaronColors[0]]);

  // Use the top-level child names as the domain so each top-level segment
  // gets a consistent, distinct color. The range is the macaron palette.
  const domain = chartData.children.map((c) => c.name);
  return d3.scaleOrdinal<string, string>().domain(domain).range(macaronColors);
  };

  const format = d3.format(",d");

  const truncateText = (text: string, maxLength: number = 7): string => {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  const arc = d3
    .arc<d3.HierarchyRectangularNode<Data>>()
    .startAngle((d) => d.x0)
    .endAngle((d) => d.x1)
    .padAngle((d) => Math.min((d.x1 - d.x0) / 2, 0.005))
    .padRadius(RADIUS / 2)
    .innerRadius((d) => d.y0)
    .outerRadius((d) => d.y1 - 1);

  const getAutoBox = () => {
    if (!svgRef.current) {
      return "";
    }

    const { x, y, width, height } = svgRef.current.getBBox();
    return [x, y, width, height].toString();
  };

  useEffect(() => {
    if (chartData) {
      setTimeout(() => setViewBox(getAutoBox()), 100);
    }
  }, [chartData]);

  const getSegmentColor = (d: d3.HierarchyRectangularNode<Data>) => {
    const color = getColor();
    // Find the top-level parent for consistent coloring
    let node = d;
    while (node.depth > 1) node = node.parent!;
    return color(node.data.name);
  };

  const getTextTransform = (d: d3.HierarchyRectangularNode<Data>) => {
    const angle = (d.x0 + d.x1) / 2;
    const radius = (d.y0 + d.y1) / 2;
    const x = Math.cos(angle - Math.PI / 2) * radius;
    const y = Math.sin(angle - Math.PI / 2) * radius;
    const rotation = (angle * 180) / Math.PI - 90;

    return `translate(${x},${y}) rotate(${rotation > 90 ? rotation + 180 : rotation})`;
  };

  const getMaxDepth = (data: Data): number => {
    if (!data) return 0;
    if (!data.children || data.children.length === 0) return 1;
    return 1 + Math.max(...data.children.map(getMaxDepth));
  };

  if (categoriesLoading) {
    return <div>Loading categories...</div>;
  }

  return (
    <div>
      <div>
        <div className="flex gap-6 items-center">
          {categories.map((category) => (
            <button
              key={category.id}
              className={selectedCategory === category.id ? 'font-bold' : 'text-muted-foreground'}
              onClick={() => setSelectedCategory(category.id)}
            >
              {category.name}
            </button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-sm text-muted-foreground">时间范围:</span>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="bg-background border rounded px-2 py-1 text-sm"
            >
              <option value="1month">近1个月</option>
              <option value="3months">近3个月</option>
              <option value="6months">近6个月</option>
              <option value="1year">近1年</option>
              <option value="all">全部时间</option>
            </select>
            <button
              onClick={handleRefresh}
              disabled={loading || isTransitioning}
              className="p-1 rounded border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              title="刷新数据"
            >
              <RefreshCw
                size={16}
                className={`${(loading || isTransitioning) ? 'animate-spin' : ''}`}
              />
            </button>
          </div>
        </div>
      </div>
      <div>
        {loading ? (<></>
        ) : error ? (
          <div className="text-red-500">Error: {error}</div>
        ) : chartData && chartData.children ? (
          <div style={{ display: 'flex', justifyContent: 'center', position: 'relative' }}>
            {/* Previous chart for fade out transition */}
            {isTransitioning && prevChartData && prevChartData.children && (
              <div className="absolute" style={{
                opacity: isTransitioning ? 0.3 : 0,
                transition: 'opacity 0.3s ease-out',
                zIndex: 1
              }}>
                <svg width={SIZE} height={SIZE} viewBox={viewBox || `0 0 ${SIZE} ${SIZE}`}>
                  <g transform={`translate(${SIZE/2},${SIZE/2})`} fillOpacity={0.3}>
                    {partition(prevChartData)
                      .descendants()
                      .filter((d) => d.depth)
                      .map((d, i) => (
                        <path
                          key={`prev-${d.data.name}-${i}`}
                          fill={getSegmentColor(d)}
                          stroke="hsl(var(--background))"
                          strokeWidth={1}
                          strokeLinejoin="round"
                          d={arc(d) || undefined}
                        />
                      ))}
                  </g>
                </svg>
              </div>
            )}
            <div style={{
              opacity: isTransitioning ? 0.5 : 1,
              transform: isTransitioning ? 'scale(0.95)' : 'scale(1)',
              transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
              zIndex: 2,
              position: 'relative'
            }}>
              <svg width={SIZE} height={SIZE} viewBox={viewBox || `0 0 ${SIZE} ${SIZE}`} ref={svgRef}>
                <g transform={`translate(${SIZE/2},${SIZE/2})`} fillOpacity={0.6}>
                  {partition(chartData)
                    .descendants()
                    .filter((d) => d.depth)
                    .map((d, i) => (
                      <path
                        key={`${d.data.name}-${i}`}
                        fill={getSegmentColor(d)}
                        stroke="hsl(var(--background))"
                        strokeWidth={1}
                        strokeLinejoin="round"
                        d={arc(d) || undefined}
                        style={{
                          transition: 'all 0.3s ease-in-out',
                          opacity: isTransitioning ? 0.7 : 1
                        }}
                        onMouseEnter={(e) => {
                          if (!isTransitioning) {
                            e.currentTarget.style.stroke = '#f59e0b';
                            e.currentTarget.style.strokeWidth = '2';
                            setHoveredSegment({name: d.data.name, value: d.value || 0});
                          }
                        }}
                        onMouseLeave={(e) => {
                          if (!isTransitioning) {
                            e.currentTarget.style.stroke = 'hsl(var(--background))';
                            e.currentTarget.style.strokeWidth = '1';
                            setHoveredSegment(null);
                          }
                        }}
                        onMouseMove={(e) => {
                          if (!isTransitioning) {
                            // Get mouse position relative to the page
                            const svgRect = svgRef.current?.getBoundingClientRect();
                            if (svgRect) {
                              setTooltipPosition({
                                x: e.clientX - svgRect.left,
                                y: e.clientY - svgRect.top
                              });
                            }
                          }
                        }}
                      >
                      </path>
                    ))}
                </g>
                <g
                  transform={`translate(${SIZE/2},${SIZE/2})`}
                  pointerEvents="none"
                  textAnchor="middle"
                  fontSize={10}
                  fontFamily="sans-serif"
                  style={{
                    opacity: isTransitioning ? 0.5 : 1,
                    transition: 'opacity 0.3s ease-in-out'
                  }}
                >
                  {chartData && (() => {
                    const maxDepth = getMaxDepth(chartData);
                    return partition(chartData)
                      .descendants()
                      .filter((d) => d.depth && d.depth < maxDepth && ((d.y0 + d.y1) / 2) * (d.x1 - d.x0) > 10)
                      .map((d, i) => (
                        <text
                          key={`${d.data.name}-${i}`}
                          transform={getTextTransform(d)}
                          dy="0.35em"
                          dx="3"
                          fill={resolvedTheme === 'dark' ? '#fff' : '#000'}
                        >
                          {truncateText(d.data.name)}
                        </text>
                      ));
                  })()}
                </g>
              </svg>
            </div>
            {hoveredSegment && (
              <div
                className="absolute bg-background border rounded-lg p-2 shadow-lg pointer-events-none text-xs"
                style={{
                  left: tooltipPosition.x,
                  top: tooltipPosition.y,
                  transform: 'translate(10px, -30px)',
                  zIndex: 1000,
                  minWidth: '100px',
                  opacity: 0.7
                }}
              >
                <div>{hoveredSegment.name}</div>
                <div className="font-bold">{format(hoveredSegment.value)}</div>
              </div>
            )}
          </div>
        ) : (
          <div>No data available for this category.</div>
        )}
      </div>
    </div>
  );
};

export default SunburstChart;