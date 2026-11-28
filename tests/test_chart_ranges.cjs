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
