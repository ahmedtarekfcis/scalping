/**
 * Behavioral Trading Mistakes Definition & Evaluation Engine
 * Evaluates manually entered trade records for specific behavioral and discipline mistakes.
 * 
 * Rules:
 * - Missing or unanswered fields are NOT classified as mistakes.
 * - Only confirmed answered violations count.
 * - Avoid double-counting within the same trade.
 */

export const MISTAKE_DEFINITIONS = {
  NOT_FRONTSIDE: {
    id: 'NOT_FRONTSIDE',
    title: 'Trading Backside (Not Frontside)',
    shortName: 'Backside Trade',
    category: 'Setup Selection',
    severity: 'high',
    color: '#f97316', // Orange
    bg: 'rgba(249, 115, 22, 0.15)',
    border: 'rgba(249, 115, 22, 0.35)',
    description: 'Entered a stock that was not trading on the frontside. Frontside momentum has higher statistical edge.',
    ruleExplanation: 'Frontside Setup answer was explicitly "No".',
  },
  OVERTRADING_SYMBOL: {
    id: 'OVERTRADING_SYMBOL',
    title: 'Overtrading Same Stock (3+ Trades)',
    shortName: 'Overtrading Ticker',
    category: 'Discipline',
    severity: 'medium',
    color: '#eab308', // Yellow
    bg: 'rgba(234, 179, 8, 0.15)',
    border: 'rgba(234, 179, 8, 0.35)',
    description: 'Executed 3 or more trades on the same stock in a single session, indicating potential revenge or overstaying.',
    ruleExplanation: 'Trade sequence on this symbol was 3 or higher.',
  },
  NO_PREDEFINED_ENTRY: {
    id: 'NO_PREDEFINED_ENTRY',
    title: 'No Predefined Entry Price',
    shortName: 'No Plan Entry',
    category: 'Entry Discipline',
    severity: 'high',
    color: '#ec4899', // Pink
    bg: 'rgba(236, 72, 153, 0.15)',
    border: 'rgba(236, 72, 153, 0.35)',
    description: 'Entered the trade without defining a specific, objective entry price level in advance.',
    ruleExplanation: 'Predefined Entry was answered "No".',
  },
  CHASED_ENTRY: {
    id: 'CHASED_ENTRY',
    title: 'Chased Entry (Above Planned Price)',
    shortName: 'Chased Entry',
    category: 'Entry Discipline',
    severity: 'high',
    color: '#f43f5e', // Rose
    bg: 'rgba(244, 63, 94, 0.15)',
    border: 'rgba(244, 63, 94, 0.35)',
    description: 'Deviated from planned entry by executing above the predefined price, compromising risk/reward.',
    ruleExplanation: 'Planned entry was set, but entry was executed above planned price.',
  },
  FAILED_TO_REDUCE_BAD_ENTRY: {
    id: 'FAILED_TO_REDUCE_BAD_ENTRY',
    title: 'Held Full Size After Chasing',
    shortName: 'Full Size Bad Entry',
    category: 'Risk Management',
    severity: 'critical',
    color: '#ef4444', // Red
    bg: 'rgba(239, 68, 68, 0.18)',
    border: 'rgba(239, 68, 68, 0.45)',
    description: 'Held the full position size after chasing an extended price instead of mitigating risk by selling half or closing.',
    ruleExplanation: 'Entered above planned price and held full position rather than reducing size.',
  },
  NO_PREDEFINED_STOP: {
    id: 'NO_PREDEFINED_STOP',
    title: 'No Predefined Stop Loss',
    shortName: 'No Stop Loss',
    category: 'Risk Management',
    severity: 'critical',
    color: '#dc2626', // Deep Red
    bg: 'rgba(220, 38, 38, 0.18)',
    border: 'rgba(220, 38, 38, 0.45)',
    description: 'Entered the position without a predetermined stop-loss level, exposing capital to open-ended downside.',
    ruleExplanation: 'Predefined Stop Loss answer was explicitly "No".',
  },
  AVERAGED_DOWN: {
    id: 'AVERAGED_DOWN',
    title: 'Averaged Down on Losing Trade',
    shortName: 'Averaged Down',
    category: 'Risk Management',
    severity: 'critical',
    color: '#b91c1c', // Crimson
    bg: 'rgba(185, 28, 28, 0.22)',
    border: 'rgba(185, 28, 28, 0.5)',
    description: 'Added shares to a losing position to lower average cost, violating fundamental scalping risk management.',
    ruleExplanation: 'Averaged Down answer was explicitly "Yes".',
  },
  FROZE_ON_LOSS: {
    id: 'FROZE_ON_LOSS',
    title: 'Froze During Losing Trade',
    shortName: 'Froze / Hesitated',
    category: 'Execution / Psychology',
    severity: 'critical',
    color: '#a855f7', // Purple
    bg: 'rgba(168, 85, 247, 0.18)',
    border: 'rgba(168, 85, 247, 0.45)',
    description: 'Stock moved against the position and psychological paralysis prevented executing the planned exit.',
    ruleExplanation: 'Freezing on losing trade answer was explicitly "Yes".',
  },
  FEAR_BASED_EXIT: {
    id: 'FEAR_BASED_EXIT',
    title: 'Exited Final Size Out of Fear',
    shortName: 'Fear Exit',
    category: 'Execution / Psychology',
    severity: 'high',
    color: '#d946ef', // Fuchsia
    bg: 'rgba(217, 70, 239, 0.18)',
    border: 'rgba(217, 70, 239, 0.45)',
    description: 'Exited the final remaining position size due to fear or anxiety rather than following technical setup exit rules.',
    ruleExplanation: 'Final size exit was explicitly answered "Fear Exit".',
  },
  FLUSH_OCCURRED: {
    id: 'FLUSH_OCCURRED',
    title: 'Caught in a Flush',
    shortName: 'Flush Caught',
    category: 'Risk Management',
    severity: 'critical',
    color: '#ef4444', // Red
    bg: 'rgba(239, 68, 68, 0.18)',
    border: 'rgba(239, 68, 68, 0.45)',
    description: 'Caught in a sudden flush or breakdown, especially when the stock stalled or weakened before the flush and exit rules were not executed.',
    ruleExplanation: 'Flush occurred answer was explicitly "Yes".',
  },
};

export const MISTAKE_CATEGORIES = [
  { id: 'Entry Discipline', label: 'Entry Discipline', color: '#ec4899' },
  { id: 'Risk Management', label: 'Risk Management', color: '#ef4444' },
  { id: 'Setup Selection', label: 'Setup Selection', color: '#f97316' },
  { id: 'Execution / Psychology', label: 'Execution / Psychology', color: '#a855f7' },
  { id: 'Discipline', label: 'General Discipline', color: '#eab308' },
];

export const TRADING_SESSIONS = [
  { id: 'PRE_MARKET', label: 'Pre-Market', hours: '04:00 - 09:30 EST', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.15)' },
  { id: 'MARKET_OPEN', label: 'Market Open', hours: '09:30 - 11:30 EST', color: '#34d399', bg: 'rgba(52, 211, 153, 0.15)' },
  { id: 'MID_DAY', label: 'Mid-Day', hours: '11:30 - 14:00 EST', color: '#fbbf24', bg: 'rgba(251, 191, 36, 0.15)' },
  { id: 'POWER_HOUR', label: 'Power Hour', hours: '14:00 - 16:00 EST', color: '#f87171', bg: 'rgba(248, 113, 113, 0.15)' },
  { id: 'AFTER_HOURS', label: 'After-Hours', hours: '16:00 - 20:00 EST', color: '#818cf8', bg: 'rgba(129, 140, 248, 0.15)' },
];

export function getDefaultCurrentTimeStr() {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, '0');
  const m = String(now.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}

export function getDefaultCurrentDateStr() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/**
 * Converts a given Local (e.g. Cairo) Date and Time to US Eastern Time (EST/EDT)
 */
export function convertLocalToEst(dateStr, timeStr) {
  if (!dateStr || !timeStr) {
    dateStr = dateStr || getDefaultCurrentDateStr();
    timeStr = timeStr || getDefaultCurrentTimeStr();
  }
  const [year, month, day] = String(dateStr).split('-').map(Number);
  const [hour, minute] = String(timeStr).split(':').map(Number);
  const localDate = new Date(year, (month || 1) - 1, day || 1, hour || 0, minute || 0, 0);

  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });

  const parts = formatter.formatToParts(localDate);
  const partMap = {};
  parts.forEach((p) => { partMap[p.type] = p.value; });

  let estH = parseInt(partMap.hour, 10);
  if (estH === 24) estH = 0;
  const estHourStr = String(estH).padStart(2, '0');
  const estMinStr = String(partMap.minute).padStart(2, '0');
  const estDateStr = `${partMap.year}-${partMap.month}-${partMap.day}`;
  const estTimeStr = `${estHourStr}:${estMinStr}`;
  const period = estH >= 12 ? 'PM' : 'AM';
  const h12 = estH % 12 || 12;
  const estDisplay = `${String(h12).padStart(2, '0')}:${estMinStr} ${period} EST`;
  const totalMinutes = estH * 60 + parseInt(estMinStr, 10);

  return {
    estDateStr,
    estTimeStr,
    estDisplay,
    estHour: estH,
    estMinute: parseInt(estMinStr, 10),
    totalMinutes,
  };
}

/**
 * Detects the US Market Session from a given local time/date by converting to EST
 */
export function detectSessionFromTime(timeStr, dateStr = null) {
  if (!timeStr) return 'MARKET_OPEN';
  const est = convertLocalToEst(dateStr || getDefaultCurrentDateStr(), timeStr);
  const totalMinutes = est.totalMinutes;

  // 04:00 to 09:30 EST (240 to 570) -> PRE_MARKET
  if (totalMinutes >= 240 && totalMinutes < 570) return 'PRE_MARKET';
  // 09:30 to 11:30 EST (570 to 690) -> MARKET_OPEN
  if (totalMinutes >= 570 && totalMinutes < 690) return 'MARKET_OPEN';
  // 11:30 to 14:00 EST (690 to 840) -> MID_DAY
  if (totalMinutes >= 690 && totalMinutes < 840) return 'MID_DAY';
  // 14:00 to 16:00 EST (840 to 960) -> POWER_HOUR
  if (totalMinutes >= 840 && totalMinutes < 960) return 'POWER_HOUR';
  // 16:00 to 20:00 EST (960 to 1200) -> AFTER_HOURS
  if (totalMinutes >= 960 && totalMinutes <= 1200) return 'AFTER_HOURS';

  // Outside 04:00 - 20:00 EST
  return 'PRE_MARKET';
}

/**
 * Evaluates a single trade against all mistake definitions.
 * Returns an array of detected mistake objects.
 * Missing / unanswered fields do NOT trigger mistakes.
 */
export function evaluateTradeMistakes(trade) {
  if (!trade) return [];
  const mistakes = [];

  // 1. NOT_FRONTSIDE: Frontside setup was explicitly answered 'No' (false)
  if (trade.frontsideSetup === false) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.NOT_FRONTSIDE,
      userNote: trade.frontsideReason || '',
    });
  }

  // 2. OVERTRADING_SYMBOL: Trade sequence on this stock >= 3
  const seq = Number(trade.tradeSequence);
  if (Number.isFinite(seq) && seq >= 3) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.OVERTRADING_SYMBOL,
      details: `Trade #${seq} on ${trade.symbol || 'ticker'}`,
      userNote: '',
    });
  }

  // 3. NO_PREDEFINED_ENTRY: Predefined entry price was explicitly answered 'No' (false)
  if (trade.predefinedEntry === false) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.NO_PREDEFINED_ENTRY,
      userNote: trade.predefinedEntryReason || '',
    });
  }

  // 4. CHASED_ENTRY: Planned entry was Yes, but entered above planned price
  if (
    trade.predefinedEntry === true &&
    trade.enteredAtPredefinedPrice === false &&
    trade.entryDeviationDirection === 'ABOVE'
  ) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.CHASED_ENTRY,
      details: trade.entryDeviationReason || 'Entered above planned price',
      userNote: trade.entryDeviationReason || '',
    });
  }

  // 5. FAILED_TO_REDUCE_BAD_ENTRY: Entered above planned price AND held full position
  if (
    trade.entryDeviationDirection === 'ABOVE' &&
    trade.enteredAboveAction === 'HELD_FULL'
  ) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.FAILED_TO_REDUCE_BAD_ENTRY,
      details: trade.enteredAboveReason || 'Held full size despite bad entry',
      userNote: trade.enteredAboveReason || '',
    });
  }

  // 6. NO_PREDEFINED_STOP: Predefined stop loss was explicitly answered 'No' (false)
  if (trade.predefinedStopLoss === false) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.NO_PREDEFINED_STOP,
      userNote: trade.predefinedStopReason || '',
    });
  }

  // 7. AVERAGED_DOWN: Averaged down was explicitly answered 'Yes' (true)
  if (trade.averagedDown === true) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.AVERAGED_DOWN,
      details: trade.averagedDownReason || '',
      userNote: trade.averagedDownReason || '',
    });
  }

  // 8. FROZE_ON_LOSS: Froze during losing trade was explicitly answered 'Yes' (true)
  if (trade.frozeOnLoss === true) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.FROZE_ON_LOSS,
      details: trade.frozeReason || '',
      userNote: trade.frozeReason || '',
    });
  }

  // 9. FEAR_BASED_EXIT: Exited last remaining size out of fear rather than setup
  if (trade.finalExitType === 'FEAR') {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.FEAR_BASED_EXIT,
      details: trade.finalExitFearReason || 'Exited final size out of fear',
      userNote: trade.finalExitFearReason || '',
    });
  }

  // 10. FLUSH_OCCURRED: Flush happened against the trade
  if (trade.flushOccurred === true) {
    mistakes.push({
      ...MISTAKE_DEFINITIONS.FLUSH_OCCURRED,
      details: trade.flushReason || 'Caught in a Flush',
      userNote: trade.flushReason || '',
    });
  }

  return mistakes;
}

/**
 * Calculates overall behavioral stats across an array of trades
 */
export function calculateOverallStats(trades) {
  const totalTrades = trades.length;
  if (totalTrades === 0) {
    return {
      totalTrades: 0,
      totalMistakes: 0,
      tradesWithMistakes: 0,
      cleanTrades: 0,
      mistakePercentage: 0,
      cleanPercentage: 0,
      mostFrequentMistake: null,
      mistakesPerFlawedTrade: 0,
    };
  }

  let totalMistakes = 0;
  let tradesWithMistakes = 0;
  const mistakeCounts = {};

  Object.keys(MISTAKE_DEFINITIONS).forEach((k) => {
    mistakeCounts[k] = 0;
  });

  trades.forEach((trade) => {
    const tradeMistakes = trade.mistakes || evaluateTradeMistakes(trade);
    if (tradeMistakes.length > 0) {
      tradesWithMistakes++;
      totalMistakes += tradeMistakes.length;
      tradeMistakes.forEach((m) => {
        if (mistakeCounts[m.id] !== undefined) {
          mistakeCounts[m.id]++;
        }
      });
    }
  });

  const cleanTrades = totalTrades - tradesWithMistakes;
  const mistakePercentage = Number(((tradesWithMistakes / totalTrades) * 100).toFixed(1));
  const cleanPercentage = Number(((cleanTrades / totalTrades) * 100).toFixed(1));
  const mistakesPerFlawedTrade = tradesWithMistakes > 0 ? Number((totalMistakes / tradesWithMistakes).toFixed(1)) : 0;

  // Find most frequent mistake
  let mostFrequentMistake = null;
  let maxCount = 0;
  Object.entries(mistakeCounts).forEach(([id, count]) => {
    if (count > maxCount) {
      maxCount = count;
      mostFrequentMistake = {
        ...MISTAKE_DEFINITIONS[id],
        count,
        percentage: Number(((count / totalTrades) * 100).toFixed(1)),
      };
    }
  });

  return {
    totalTrades,
    totalMistakes,
    tradesWithMistakes,
    cleanTrades,
    mistakePercentage,
    cleanPercentage,
    mostFrequentMistake,
    mistakesPerFlawedTrade,
    mistakeCounts,
  };
}

/**
 * Returns date range for ISO week (Monday to Sunday)
 */
export function getWeekDateRange(dateObj = new Date()) {
  const d = new Date(dateObj);
  const day = d.getDay(); // 0 is Sun, 1 is Mon...
  const diffToMon = day === 0 ? -6 : 1 - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diffToMon);
  monday.setHours(0, 0, 0, 0);

  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  sunday.setHours(23, 59, 59, 999);

  return {
    start: monday,
    end: sunday,
    startStr: monday.toISOString().split('T')[0],
    endStr: sunday.toISOString().split('T')[0],
  };
}

/**
 * Returns ISO week key string "YYYY-Www"
 */
export function getIsoWeekKey(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  const thursday = new Date(d);
  thursday.setDate(d.getDate() + (4 - (d.getDay() || 7)));
  const yearStart = new Date(thursday.getFullYear(), 0, 1);
  const weekNo = Math.ceil(((thursday - yearStart) / 86400000 + 1) / 7);
  return `${thursday.getFullYear()}-W${String(weekNo).padStart(2, '0')}`;
}

/**
 * Builds comparative frequency analysis for each mistake type
 * including trend direction (increasing, decreasing, stable)
 */
export function calculateMistakeFrequencyAnalysis(allTrades, recentWindow = 14) {
  const totalTrades = allTrades.length;
  if (totalTrades === 0) {
    return Object.values(MISTAKE_DEFINITIONS).map((def) => ({
      ...def,
      count: 0,
      percentage: 0,
      trend: 'stable',
      trendDelta: 0,
      recentCount: 0,
      priorCount: 0,
    }));
  }

  // Sort trades chronologically
  const sorted = [...allTrades].sort((a, b) => {
    const dtA = `${a.tradeDate || ''} ${a.tradeTime || ''}`;
    const dtB = `${b.tradeDate || ''} ${b.tradeTime || ''}`;
    return dtA.localeCompare(dtB);
  });

  // Split into recent half and prior half for trend calculation
  const half = Math.max(1, Math.floor(sorted.length / 2));
  const priorTrades = sorted.slice(0, sorted.length - half);
  const recentTrades = sorted.slice(sorted.length - half);

  const countsAll = {};
  const countsRecent = {};
  const countsPrior = {};

  Object.keys(MISTAKE_DEFINITIONS).forEach((k) => {
    countsAll[k] = 0;
    countsRecent[k] = 0;
    countsPrior[k] = 0;
  });

  sorted.forEach((t) => {
    const ms = t.mistakes || evaluateTradeMistakes(t);
    ms.forEach((m) => {
      if (countsAll[m.id] !== undefined) countsAll[m.id]++;
    });
  });

  recentTrades.forEach((t) => {
    const ms = t.mistakes || evaluateTradeMistakes(t);
    ms.forEach((m) => {
      if (countsRecent[m.id] !== undefined) countsRecent[m.id]++;
    });
  });

  priorTrades.forEach((t) => {
    const ms = t.mistakes || evaluateTradeMistakes(t);
    ms.forEach((m) => {
      if (countsPrior[m.id] !== undefined) countsPrior[m.id]++;
    });
  });

  return Object.values(MISTAKE_DEFINITIONS).map((def) => {
    const count = countsAll[def.id] || 0;
    const percentage = Number(((count / totalTrades) * 100).toFixed(1));

    const recentRate = recentTrades.length > 0 ? countsRecent[def.id] / recentTrades.length : 0;
    const priorRate = priorTrades.length > 0 ? countsPrior[def.id] / priorTrades.length : 0;
    const rateDiff = recentRate - priorRate;

    let trend = 'stable';
    if (rateDiff > 0.05) trend = 'increasing';
    else if (rateDiff < -0.05) trend = 'decreasing';

    return {
      ...def,
      count,
      percentage,
      trend, // 'increasing' | 'decreasing' | 'stable'
      trendDelta: Number((rateDiff * 100).toFixed(1)),
      recentCount: countsRecent[def.id] || 0,
      priorCount: countsPrior[def.id] || 0,
    };
  }).sort((a, b) => b.count - a.count);
}

/**
 * Calculates weekly performance review comparing a target week with its prior week
 */
export function calculateWeeklyReview(allTrades, targetMondayDate = null) {
  const currentWeekRange = getWeekDateRange(targetMondayDate || new Date());
  
  // Prior week range
  const priorMonDate = new Date(currentWeekRange.start);
  priorMonDate.setDate(priorMonDate.getDate() - 7);
  const priorWeekRange = getWeekDateRange(priorMonDate);

  const filterByRange = (trades, range) => {
    return trades.filter((t) => {
      if (!t.tradeDate) return false;
      return t.tradeDate >= range.startStr && t.tradeDate <= range.endStr;
    });
  };

  const currentWeekTrades = filterByRange(allTrades, currentWeekRange);
  const priorWeekTrades = filterByRange(allTrades, priorWeekRange);

  const currentStats = calculateOverallStats(currentWeekTrades);
  const priorStats = calculateOverallStats(priorWeekTrades);

  // Breakdown of mistakes for current week vs prior week
  const comparison = Object.values(MISTAKE_DEFINITIONS).map((def) => {
    const currCount = currentStats.mistakeCounts?.[def.id] || 0;
    const prevCount = priorStats.mistakeCounts?.[def.id] || 0;
    const delta = currCount - prevCount;
    let status = 'unchanged';
    if (delta < 0) status = 'improved'; // Less mistakes = improvement
    else if (delta > 0) status = 'worsened'; // More mistakes = worsened

    return {
      ...def,
      currCount,
      prevCount,
      delta,
      status, // 'improved' | 'worsened' | 'unchanged'
    };
  });

  const improvedMistakes = comparison.filter((c) => c.status === 'improved');
  const worsenedMistakes = comparison.filter((c) => c.status === 'worsened');

  const mistakesDelta = currentStats.totalMistakes - priorStats.totalMistakes;
  const tradesDelta = currentStats.totalTrades - priorStats.totalTrades;

  return {
    weekLabel: `${currentWeekRange.startStr} to ${currentWeekRange.endStr}`,
    currentWeekRange,
    priorWeekRange,
    currentWeekTrades,
    priorWeekTrades,
    currentStats,
    priorStats,
    mistakesDelta,
    tradesDelta,
    comparison,
    improvedMistakes,
    worsenedMistakes,
  };
}

/**
 * Generate sensible demo trades for testing the analytics
 */
export function getSensibleSampleJournalTrades() {
  const today = new Date();
  const formatDay = (daysAgo) => {
    const d = new Date(today);
    d.setDate(d.getDate() - daysAgo);
    return d.toISOString().split('T')[0];
  };

  return [
    {
      id: 'demo-1',
      tradeDate: formatDay(0),
      tradeTime: '09:35',
      symbol: 'TSLA',
      entryPrice: 182.4,
      tradeSequence: 1,
      frontsideSetup: true,
      direction: 'LONG',
      shares: 100,
      exitPrice: 184.1,
      pnl: 170,
      status: 'WIN',
      ema9Value: 181.9,
      vwapValue: 182.1,
      nearestResistance: 185.0,
      predefinedEntry: true,
      plannedEntryPrice: 182.4,
      enteredAtPredefinedPrice: true,
      entryDeviationDirection: null,
      entryDeviationReason: '',
      enteredAboveAction: null,
      enteredAboveReason: '',
      predefinedStopLoss: true,
      stopLossPrice: 181.8,
      averagedDown: false,
      averagedDownReason: '',
      frozeOnLoss: false,
      frozeReason: '',
      notes: 'Clean 9 EMA frontside bounce at the open. Executed at exact trigger level.',
    },
    {
      id: 'demo-2',
      tradeDate: formatDay(0),
      tradeTime: '10:15',
      symbol: 'TSLA',
      entryPrice: 185.2,
      tradeSequence: 2,
      frontsideSetup: true,
      direction: 'LONG',
      shares: 100,
      exitPrice: 183.8,
      pnl: -140,
      status: 'LOSS',
      ema9Value: 184.2,
      vwapValue: 183.9,
      nearestResistance: 185.0,
      predefinedEntry: true,
      plannedEntryPrice: 184.6,
      enteredAtPredefinedPrice: false,
      entryDeviationDirection: 'ABOVE',
      entryDeviationReason: 'Chased the breakout over 185 resistance when tape sped up',
      enteredAboveAction: 'HELD_FULL',
      enteredAboveReason: 'Hoped momentum would carry through to 186',
      predefinedStopLoss: true,
      stopLossPrice: 184.0,
      averagedDown: false,
      averagedDownReason: '',
      frozeOnLoss: false,
      frozeReason: '',
      notes: 'Chased entry above planned price and failed to reduce size. Cut at stop.',
    },
    {
      id: 'demo-3',
      tradeDate: formatDay(1),
      tradeTime: '09:42',
      symbol: 'NVDA',
      entryPrice: 124.5,
      tradeSequence: 1,
      frontsideSetup: true,
      direction: 'LONG',
      shares: 150,
      exitPrice: 126.2,
      pnl: 255,
      status: 'WIN',
      ema9Value: 124.1,
      vwapValue: 123.8,
      nearestResistance: 127.0,
      predefinedEntry: true,
      plannedEntryPrice: 124.5,
      enteredAtPredefinedPrice: true,
      entryDeviationDirection: null,
      entryDeviationReason: '',
      enteredAboveAction: null,
      enteredAboveReason: '',
      predefinedStopLoss: true,
      stopLossPrice: 123.9,
      averagedDown: false,
      averagedDownReason: '',
      frozeOnLoss: false,
      frozeReason: '',
      notes: 'Frontside VWAP hold. Perfect disciplined entry and clean profit taking.',
    },
    {
      id: 'demo-4',
      tradeDate: formatDay(2),
      tradeTime: '11:05',
      symbol: 'AMD',
      entryPrice: 156.8,
      tradeSequence: 3,
      frontsideSetup: false,
      direction: 'LONG',
      shares: 100,
      exitPrice: 153.2,
      pnl: -360,
      status: 'LOSS',
      ema9Value: 157.9,
      vwapValue: 158.4,
      nearestResistance: 160.0,
      predefinedEntry: false,
      plannedEntryPrice: null,
      enteredAtPredefinedPrice: null,
      entryDeviationDirection: null,
      entryDeviationReason: '',
      enteredAboveAction: null,
      enteredAboveReason: '',
      predefinedStopLoss: false,
      stopLossPrice: null,
      averagedDown: true,
      averagedDownReason: 'Added 50 more shares at 155.0 to lower cost average after missing exit',
      frozeOnLoss: true,
      frozeReason: 'Froze in denial when it broke under 154 support. Prayed for quick recovery.',
      notes: 'Terrible backside trade. 3rd trade on AMD. No predefined entry or stop, averaged down and froze.',
    },
    {
      id: 'demo-5',
      tradeDate: formatDay(3),
      tradeTime: '09:50',
      symbol: 'AAPL',
      entryPrice: 226.0,
      tradeSequence: 1,
      frontsideSetup: true,
      direction: 'LONG',
      shares: 100,
      exitPrice: 227.4,
      pnl: 140,
      status: 'WIN',
      ema9Value: 225.5,
      vwapValue: 225.2,
      nearestResistance: 228.0,
      predefinedEntry: true,
      plannedEntryPrice: 226.0,
      enteredAtPredefinedPrice: true,
      entryDeviationDirection: null,
      entryDeviationReason: '',
      enteredAboveAction: null,
      enteredAboveReason: '',
      predefinedStopLoss: true,
      stopLossPrice: 225.3,
      averagedDown: false,
      averagedDownReason: '',
      frozeOnLoss: false,
      frozeReason: '',
      notes: 'Standard 9 EMA pullback entry, predefined stop honored, clean 1.4 point move.',
    },
    {
      id: 'demo-6',
      tradeDate: formatDay(4),
      tradeTime: '10:30',
      symbol: 'META',
      entryPrice: 580.5,
      tradeSequence: 2,
      frontsideSetup: true,
      direction: 'LONG',
      shares: 50,
      exitPrice: 578.0,
      pnl: -125,
      status: 'LOSS',
      ema9Value: 579.8,
      vwapValue: 578.9,
      nearestResistance: 583.0,
      predefinedEntry: true,
      plannedEntryPrice: 579.5,
      enteredAtPredefinedPrice: false,
      entryDeviationDirection: 'ABOVE',
      entryDeviationReason: 'Chased entry 1 dollar above plan',
      enteredAboveAction: 'SOLD_HALF',
      enteredAboveReason: 'Sold half immediately to reduce risk when I recognized bad entry',
      predefinedStopLoss: true,
      stopLossPrice: 578.0,
      averagedDown: false,
      averagedDownReason: '',
      frozeOnLoss: false,
      frozeReason: '',
      notes: 'Chased entry but followed discipline by cutting half immediately. Honorable loss.',
    },
  ];
}

