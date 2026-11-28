const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('v0/gemini-code-1795528199482.html', 'utf8');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
function context() {
  const ctx = vm.createContext({window: {addEventListener() {}}, localStorage: {getItem() { return null; }}});
  vm.runInContext(script, ctx);
  return ctx;
}
test('calendar range boundaries handle month ends and leap years', () => {
  const ctx = context();
  assert.equal(vm.runInContext("chartRangeStart('2024-03-31','1m')", ctx), '2024-02-29');
  assert.equal(vm.runInContext("chartRangeStart('2024-02-29','1y')", ctx), '2023-02-28');
  assert.equal(vm.runInContext("chartRangeStart('2026-11-27','5y')", ctx), '2021-11-27');
});
test('six buttons select different windows without changing diagnosis or full history', () => {
  const ctx = context();
  vm.runInContext(`
    chartCandles = Array.from({length: 2200}, (_, i) => ({date: new Date(Date.UTC(2020, 0, i+1)).toISOString().slice(0,10)}));
    currentCandles = chartCandles.slice(-252);
    currentAnalysis = {symbol: 'TEST'};
    const originalAnalysis = currentAnalysis;
    const originalCandles = currentCandles;
    var selected = [];
    drawKlineChart = (candles) => { selected = selectChartCandles(candles, chartRange); };
  `, ctx);
  const counts = [];
  for (const range of ['1m','3m','6m','1y','3y','5y']) {
    assert.ok(html.includes(`data-chart-range="${range}"`));
    vm.runInContext(`setChartRange('${range}')`, ctx);
    counts.push(vm.runInContext('selected.length', ctx));
    assert.equal(vm.runInContext('currentRange', ctx), '1y');
    assert.equal(vm.runInContext('currentAnalysis === originalAnalysis && currentCandles === originalCandles', ctx), true);
    assert.equal(vm.runInContext('chartCandles.length', ctx), 2200);
  }
  assert.ok(counts.every((n,i) => i===0 || n > counts[i-1]));
});
test('short available history never invents candles for 5Y', () => {
  const ctx = context();
  assert.equal(vm.runInContext("selectChartCandles([{date:'2026-10-01'}, {date:'2026-11-27'}], '5y').length",ctx), 2);
});
test('slider shifts a calendar window without including later candles', () => {
  const ctx = context();
  vm.runInContext(`var history = Array.from({length: 800}, (_, i) => ({date: new Date(Date.UTC(2022, 0, i+1)).toISOString().slice(0,10)}));`, ctx);
  const earlyEnd = vm.runInContext('history[400].date',ctx);
  assert.equal(vm.runInContext("selectChartCandles(history, '1m', 400).at(-1).date", ctx), earlyEnd);
  assert.ok(vm.runInContext("selectChartCandles(history, '1m', 400).every(bar => bar.date <= history[400].date)", ctx));
  assert.ok(vm.runInContext("selectChartCandles(history, '3m', 400).length > selectChartCandles(history, '1m', 400).length", ctx));
  assert.equal(vm.runInContext("chartWindowMinimum(history, '1m')", ctx), 31);
});
test('pan state can return to latest and does not change strategy state', () => {
  const ctx = context();
  vm.runInContext(`
    chartCandles = Array.from({length: 800}, (_, i) => ({date: new Date(Date.UTC(2022, 0, i+1)).toISOString().slice(0,10)}));
    currentCandles = chartCandles.slice(-252);
    currentAnalysis = {symbol:'TEST'};
    drawKlineChart = () => {};
    setChartWindow(400);
  `,ctx);
  assert.equal(vm.runInContext('chartWindowEndIndex',ctx),400);
  assert.equal(vm.runInContext('currentRange',ctx),'1y');
  vm.runInContext("setChartWindow('latest')",ctx);
  assert.equal(vm.runInContext('chartWindowEndIndex',ctx),null);
});
test('historical overlays use no prices after selected endpoint', () => {
  const ctx = context();
  vm.runInContext(`var bars = [
    {date:'2026-01-01', open:99,close:100,high:101,low:98,volume:100},
    {date:'2026-01-02', open:105,close:106,high:107,low:104,volume:100},
    {date:'2026-01-05', open:102,close:100,high:103,low:99,volume:100}
  ];`,ctx);
  assert.equal(vm.runInContext('historicalChartInfo(bars.slice(0,2)).openBullGaps.length',ctx),1);
  assert.equal(vm.runInContext('historicalChartInfo(bars).openBullGaps.length',ctx),0);
  assert.equal(vm.runInContext('historicalChartInfo(bars.slice(0,2)).last.date',ctx),'2026-01-02');
});
const bodyCases = JSON.parse(fs.readFileSync('tests/body_gap_cases.json','utf8'));
for (const c of bodyCases) {
 test(`body gap parity: ${c.name}`, () => {
  const ctx = context();
  ctx.candles = c.candles;
  const result = JSON.parse(vm.runInContext('JSON.stringify(detectBodyGaps(candles))',ctx));
  assert.deepEqual(result.openBullGaps,c.bull);
  assert.deepEqual(result.openBearGaps,c.bear);
  const info = JSON.parse(vm.runInContext('JSON.stringify(historicalChartInfo(candles))',ctx));
  assert.deepEqual(info.openBullGaps,c.bull);
  assert.deepEqual(info.openBearGaps,c.bear);
 });
}
test('bear gap closed signal ignores shadow touches',()=>{
 const ctx=context();ctx.candles=bodyCases[2].candles;
 assert.equal(vm.runInContext('detectBodyGaps(candles).justClosedBearGap',ctx),false);
 ctx.candles=bodyCases[3].candles;
 assert.equal(vm.runInContext('detectBodyGaps(candles).justClosedBearGap',ctx),true);
});
