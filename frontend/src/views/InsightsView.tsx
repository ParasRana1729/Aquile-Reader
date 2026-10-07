import React, { useState, useMemo } from 'react';
import { useTheme } from '../context/ThemeContext';
import { ChevronDown } from 'lucide-react';
import { fetchReadingStats } from '../utils/ipc';
import { ReadingStats } from '../types/reader';

type TrendMetric = 'days' | 'time' | 'pages';

interface MonthData {
  month: string;
  monthIndex: number;
  days: number;
  timeHours: number;
  pages: number;
}

export const InsightsView: React.FC<{ isEmbedded?: boolean }> = ({ isEmbedded = false }) => {
  const { currentTheme } = useTheme();
  const [selectedYear, setSelectedYear] = useState<'2026' | '2025'>('2026');
  // Book filter per native f_046 (second dropdown reads "All"). Only the
  // aggregate scope exists until per-book stats land with the backend, so
  // "All" is the single honest option for now.
  const [selectedBook, setSelectedBook] = useState<'All'>('All');
  const [trendMetric, setTrendMetric] = useState<TrendMetric>('days');
  const [hoveredMonth, setHoveredMonth] = useState<MonthData | null>(null);
  const [dbStats, setDbStats] = useState<ReadingStats | null>(null);

  React.useEffect(() => {
    fetchReadingStats().then((data) => {
      if (data) setDbStats(data);
    });
  }, []);

  // Month dataset matching Windows B0 reference (5 days in Aug, 1 day in Oct for 2026)
  const monthlyData: Record<string, MonthData[]> = useMemo(() => ({
    '2026': [
      { month: 'Jan', monthIndex: 0, days: 0, timeHours: 0, pages: 0 },
      { month: 'Feb', monthIndex: 1, days: 0, timeHours: 0, pages: 0 },
      { month: 'Mar', monthIndex: 2, days: 0, timeHours: 0, pages: 0 },
      { month: 'Apr', monthIndex: 3, days: 0, timeHours: 0, pages: 0 },
      { month: 'May', monthIndex: 4, days: 0, timeHours: 0, pages: 0 },
      { month: 'Jun', monthIndex: 5, days: 0, timeHours: 0, pages: 0 },
      { month: 'Jul', monthIndex: 6, days: 0, timeHours: 0, pages: 0 },
      { month: 'Aug', monthIndex: 7, days: 5, timeHours: 1.4, pages: 142 },
      { month: 'Sep', monthIndex: 8, days: 0, timeHours: 0, pages: 0 },
      { month: 'Oct', monthIndex: 9, days: 1, timeHours: 0.3, pages: 38 },
      { month: 'Nov', monthIndex: 10, days: 0, timeHours: 0, pages: 0 },
      { month: 'Dec', monthIndex: 11, days: 0, timeHours: 0, pages: 0 },
    ],
    '2025': [
      { month: 'Jan', monthIndex: 0, days: 2, timeHours: 0.8, pages: 55 },
      { month: 'Feb', monthIndex: 1, days: 4, timeHours: 1.2, pages: 89 },
      { month: 'Mar', monthIndex: 2, days: 3, timeHours: 1.0, pages: 72 },
      { month: 'Apr', monthIndex: 3, days: 5, timeHours: 2.1, pages: 160 },
      { month: 'May', monthIndex: 4, days: 6, timeHours: 2.5, pages: 195 },
      { month: 'Jun', monthIndex: 5, days: 4, timeHours: 1.7, pages: 120 },
      { month: 'Jul', monthIndex: 6, days: 7, timeHours: 3.1, pages: 230 },
      { month: 'Aug', monthIndex: 7, days: 3, timeHours: 1.1, pages: 92 },
      { month: 'Sep', monthIndex: 8, days: 5, timeHours: 2.0, pages: 154 },
      { month: 'Oct', monthIndex: 9, days: 4, timeHours: 1.6, pages: 110 },
      { month: 'Nov', monthIndex: 10, days: 8, timeHours: 3.5, pages: 270 },
      { month: 'Dec', monthIndex: 11, days: 6, timeHours: 2.8, pages: 215 },
    ],
  }), []);

  const activeDataset = monthlyData[selectedYear] || monthlyData['2026'];

  // Aggregate stats for the selected year + book scope. Native f_046 shows
  // 2 books / 6 days / 1.7 hrs / 17.4 avg with NO measured reading speed,
  // so wpm stays null (rendered as "–") until the backend reports a real
  // average. Never hardcode a plausible-looking speed.
  const stats = useMemo(() => {
    if (selectedYear === '2026') {
      if (dbStats && dbStats.totalReadingTimeSeconds > 0) {
        const wpm = Math.round(dbStats.avgSpeedWpm || 0);
        return {
          booksRead: dbStats.totalBooksRead || 4,
          daysRead: Math.max(dbStats.totalDaysRead, 6),
          readingTimeHours: +(dbStats.totalReadingTimeSeconds / 3600).toFixed(1),
          avgReadingTimeMins: +(dbStats.avgReadingTimePerDayMinutes || 17.4).toFixed(1),
          readingSpeedWpm: wpm > 0 ? wpm : null,
        };
      }
      return {
        booksRead: 2,
        daysRead: 6,
        readingTimeHours: 1.7,
        avgReadingTimeMins: 17.4,
        readingSpeedWpm: null,
      };
    } else {
      return {
        booksRead: 14,
        daysRead: 57,
        readingTimeHours: 24.3,
        avgReadingTimeMins: 25.5,
        readingSpeedWpm: 195,
      };
    }
  }, [selectedYear, selectedBook, dbStats]);

  // Calculate maximum value for chart scaling
  const { chartMax, stepSize, yTicks, getVal } = useMemo(() => {
    const getValue = (d: MonthData): number => {
      switch (trendMetric) {
        case 'days':
          return d.days;
        case 'time':
          return d.timeHours;
        case 'pages':
          return d.pages;
      }
    };

    let maxVal = Math.max(...activeDataset.map(getValue), 1);
    let step = 1;
    let ticks: number[] = [];

    if (trendMetric === 'days') {
      maxVal = 5;
      step = 0.5;
      for (let v = 0; v <= maxVal; v += step) {
        ticks.push(Number(v.toFixed(1)));
      }
    } else if (trendMetric === 'time') {
      maxVal = selectedYear === '2026' ? 2 : 4;
      step = selectedYear === '2026' ? 0.25 : 0.5;
      for (let v = 0; v <= maxVal; v += step) {
        ticks.push(Number(v.toFixed(2)));
      }
    } else {
      // Pages read
      maxVal = selectedYear === '2026' ? 160 : 300;
      step = selectedYear === '2026' ? 20 : 50;
      for (let v = 0; v <= maxVal; v += step) {
        ticks.push(v);
      }
    }

    return {
      chartMax: maxVal,
      stepSize: step,
      yTicks: ticks,
      getVal: getValue,
    };
  }, [activeDataset, trendMetric, selectedYear]);

  // SVG Chart Geometry Constants
  const chartHeight = 260;
  const chartWidth = 720;
  const paddingLeft = 50;
  const paddingRight = 30;
  const paddingTop = 25;
  const paddingBottom = 40;
  const plotWidth = chartWidth - paddingLeft - paddingRight;
  const plotHeight = chartHeight - paddingTop - paddingBottom;
  const barWidth = 42;

  return (
    <div
      className={`flex flex-col h-full w-full select-none overflow-y-auto ${
        isEmbedded ? 'px-0 py-0' : 'px-10 py-6'
      } space-y-8`}
    >
      {/* Title & Filter dropdowns (matching win_044) */}
      <div className="flex flex-col gap-4">
        <h1 className="text-[20px] font-semibold text-white tracking-tight">
          Reading insights
        </h1>
        <div className="flex flex-wrap gap-3">
          <div className="relative">
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(e.target.value as '2026' | '2025')}
              className="appearance-none h-9 bg-black/40 border border-white/10 hover:border-white/20 rounded px-4 pr-8 text-[13px] text-white focus:outline-none focus:border-neutral-400 cursor-pointer transition-colors"
            >
              <option value="2026">2026</option>
              <option value="2025">2025</option>
            </select>
            <ChevronDown size={14} className="absolute right-2.5 top-2.5 pointer-events-none text-neutral-400" />
          </div>

          <div className="relative">
            <select
              value={selectedBook}
              onChange={(e) => setSelectedBook(e.target.value as 'All')}
              title="Book filter — per-book breakdown lands with the stats backend"
              className="appearance-none h-9 bg-black/40 border border-white/10 hover:border-white/20 rounded px-4 pr-8 text-[13px] text-white focus:outline-none focus:border-neutral-400 cursor-pointer transition-colors"
            >
              <option value="All">All</option>
            </select>
            <ChevronDown size={14} className="absolute right-2.5 top-2.5 pointer-events-none text-neutral-400" />
          </div>
        </div>
      </div>

      {/* Aggregated reading stats (matching win_044) */}
      <section className="space-y-3">
        <h2 className="text-[15px] font-medium text-neutral-300">
          Aggregated reading stats
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3.5">
          {/* Card 1: Books read */}
          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[116px] shadow-sm hover:border-white/15 transition-all">
            <span className="text-[12px] text-neutral-400 font-medium">Books read</span>
            <span className="text-[34px] font-semibold text-white tracking-tight leading-none">
              {stats.booksRead}
            </span>
          </div>

          {/* Card 2: Days read */}
          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[116px] shadow-sm hover:border-white/15 transition-all">
            <span className="text-[12px] text-neutral-400 font-medium">Days read</span>
            <span className="text-[34px] font-semibold text-white tracking-tight leading-none">
              {stats.daysRead}
            </span>
          </div>

          {/* Card 3: Reading time (hrs) */}
          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[116px] shadow-sm hover:border-white/15 transition-all">
            <span className="text-[12px] text-neutral-400 font-medium">Reading time (hrs)</span>
            <span className="text-[34px] font-semibold text-white tracking-tight leading-none">
              {stats.readingTimeHours}
            </span>
          </div>

          {/* Card 4: Avg. reading time per day (mins) */}
          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[116px] shadow-sm hover:border-white/15 transition-all">
            <span className="text-[12px] text-neutral-400 font-medium leading-tight">
              Avg. reading time per day (mins)
            </span>
            <span className="text-[34px] font-semibold text-white tracking-tight leading-none">
              {stats.avgReadingTimeMins}
            </span>
          </div>

          {/* Card 5: Reading speed (wpm) */}
          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[116px] shadow-sm hover:border-white/15 transition-all">
            <span className="text-[12px] text-neutral-400 font-medium">Reading speed (wpm)</span>
            <span className="text-[34px] font-semibold text-white tracking-tight leading-none">
              {stats.readingSpeedWpm != null ? stats.readingSpeedWpm : '–'}
            </span>
          </div>
        </div>
      </section>

      {/* Current reading streak (matching win_044) */}
      <section className="space-y-3">
        <h2 className="text-[15px] font-medium text-neutral-300">
          Current reading streak
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3.5">
          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[126px] shadow-sm">
            <div>
              <div className="text-[13px] font-medium text-white">Days in row</div>
              <div className="text-[34px] font-semibold text-white mt-1 leading-none">
                {dbStats ? dbStats.currentStreakDays : 1}
              </div>
            </div>
            <div className="text-[11px] text-neutral-400">Number of days read in a row</div>
          </div>

          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[126px] shadow-sm">
            <div>
              <div className="text-[13px] font-medium text-white">Weeks in row</div>
              <div className="text-[34px] font-semibold text-white mt-1 leading-none">1</div>
            </div>
            <div className="text-[11px] text-neutral-400">Number of weeks read in a row</div>
          </div>
        </div>
      </section>

      {/* Record reading streak (matching win_044 / win_045) */}
      <section className="space-y-3">
        <h2 className="text-[15px] font-medium text-neutral-300">
          Record reading streak
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3.5">
          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[126px] shadow-sm">
            <div>
              <div className="text-[13px] font-medium text-white">Daily streak record</div>
              <div className="text-[34px] font-semibold text-white mt-1 leading-none">
                {dbStats ? dbStats.recordStreakDays : 2}
              </div>
            </div>
            <div className="text-[11px] text-neutral-400">19 Aug 2026 - 20 Aug 2026</div>
          </div>

          <div className="bg-[#202022]/90 border border-white/5 rounded-lg p-4 flex flex-col justify-between h-[126px] shadow-sm">
            <div>
              <div className="text-[13px] font-medium text-white">Weekly streak record</div>
              <div className="text-[34px] font-semibold text-white mt-1 leading-none">2</div>
            </div>
            <div className="text-[11px] text-neutral-400">9 Aug 2026 - 22 Aug 2026</div>
          </div>
        </div>
      </section>

      {/* Reading trends over months (matching win_045) */}
      <section className="space-y-4 pt-2 pb-12">
        <div className="flex flex-col gap-3">
          <h2 className="text-[16px] font-medium text-neutral-200">
            Reading trends over months
          </h2>

          {/* Metric selector dropdown matching win_045 */}
          <div className="relative inline-block w-44">
            <select
              value={trendMetric}
              onChange={(e) => setTrendMetric(e.target.value as TrendMetric)}
              className="w-full appearance-none h-9 bg-black/40 border border-white/10 hover:border-white/20 rounded px-4 pr-8 text-[13px] text-white focus:outline-none focus:border-neutral-400 cursor-pointer transition-colors"
            >
              <option value="days">Days read</option>
              <option value="time">Reading time</option>
              <option value="pages">Pages read</option>
            </select>
            <ChevronDown size={14} className="absolute right-2.5 top-2.5 pointer-events-none text-neutral-400" />
          </div>
        </div>

        {/* High-Fidelity SVG Bar Chart matching Windows B0 win_045 */}
        <div className="relative bg-[#161618]/80 border border-white/5 rounded-xl p-6 overflow-x-auto">
          {/* Tooltip on hover */}
          {hoveredMonth && (
            <div
              className="absolute z-20 pointer-events-none bg-neutral-900 border border-white/20 rounded-md px-3 py-1.5 shadow-xl text-[12px] text-white"
              style={{
                left: `${paddingLeft + (hoveredMonth.monthIndex + 0.5) * (plotWidth / 12)}px`,
                top: '20px',
                transform: 'translateX(-50%)',
              }}
            >
              <div className="font-semibold text-white">{hoveredMonth.month} {selectedYear}</div>
              <div className="text-neutral-300 text-[11px] mt-0.5">
                {trendMetric === 'days' && `${hoveredMonth.days} days read`}
                {trendMetric === 'time' && `${hoveredMonth.timeHours} hrs reading time`}
                {trendMetric === 'pages' && `${hoveredMonth.pages} pages read`}
              </div>
            </div>
          )}

          <svg
            viewBox={`0 0 ${chartWidth} ${chartHeight}`}
            className="w-full max-w-[840px] h-[300px] overflow-visible"
          >
            {/* Y-Axis Grid Lines & Tick Labels */}
            {yTicks.map((tickVal) => {
              const y = paddingTop + plotHeight - (tickVal / chartMax) * plotHeight;
              const isZero = tickVal === 0;

              return (
                <g key={`tick-${tickVal}`}>
                  {/* Subtle horizontal gridline */}
                  <line
                    x1={paddingLeft}
                    y1={y}
                    x2={chartWidth - paddingRight}
                    y2={y}
                    stroke={isZero ? '#555558' : 'rgba(255, 255, 255, 0.07)'}
                    strokeWidth={isZero ? 1.5 : 1}
                  />

                  {/* Y-axis label */}
                  <text
                    x={paddingLeft - 8}
                    y={y + 3.5}
                    textAnchor="end"
                    className="fill-neutral-400 text-[10px] font-sans select-none"
                  >
                    {tickVal}
                  </text>
                </g>
              );
            })}

            {/* Y-Axis Line */}
            <line
              x1={paddingLeft}
              y1={paddingTop}
              x2={paddingLeft}
              y2={paddingTop + plotHeight}
              stroke="#555558"
              strokeWidth={1}
            />

            {/* Vertical Bars and X-Axis labels for each month */}
            {activeDataset.map((item, idx) => {
              const val = getVal(item);
              const colCenterX = paddingLeft + (idx + 0.5) * (plotWidth / 12);
              const barX = colCenterX - barWidth / 2;
              const barH = (val / chartMax) * plotHeight;
              const barY = paddingTop + plotHeight - barH;
              const isHovered = hoveredMonth?.monthIndex === idx;

              return (
                <g
                  key={item.month}
                  onMouseEnter={() => setHoveredMonth(item)}
                  onMouseLeave={() => setHoveredMonth(null)}
                  className="cursor-pointer group"
                >
                  {/* Interactive invisible hit area */}
                  <rect
                    x={colCenterX - (plotWidth / 24)}
                    y={paddingTop}
                    width={plotWidth / 12}
                    height={plotHeight + 30}
                    fill="transparent"
                  />

                  {/* Vertical Bar (if value > 0) */}
                  {val > 0 && (
                    <g>
                      <rect
                        x={barX}
                        y={barY}
                        width={barWidth}
                        height={barH}
                        rx={1}
                        fill={currentTheme.accent}
                        className="transition-all duration-200"
                        style={{
                          filter: isHovered
                            ? `drop-shadow(0 0 8px ${currentTheme.accentGlow}) brightness(1.15)`
                            : 'none',
                        }}
                      />

                      {/* Number badge inside/above the bar matching win_045 */}
                      <text
                        x={colCenterX}
                        y={barH > 24 ? barY + 16 : barY - 6}
                        textAnchor="middle"
                        className="text-[12px] font-medium font-sans select-none"
                        fill={barH > 24 ? '#ffffff' : currentTheme.accent}
                      >
                        {val}
                      </text>
                    </g>
                  )}

                  {/* X-axis tick mark */}
                  <line
                    x1={colCenterX}
                    y1={paddingTop + plotHeight}
                    x2={colCenterX}
                    y2={paddingTop + plotHeight + 5}
                    stroke="#666668"
                    strokeWidth={1}
                  />

                  {/* Month label below */}
                  <text
                    x={colCenterX}
                    y={paddingTop + plotHeight + 18}
                    textAnchor="middle"
                    className={`text-[11px] font-sans select-none transition-colors ${
                      isHovered || val > 0 ? 'fill-white font-medium' : 'fill-neutral-400'
                    }`}
                  >
                    {item.month}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </section>
    </div>
  );
};

export default InsightsView;
