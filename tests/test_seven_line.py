from statistics import NormalDist

import numpy as np
import pandas as pd
import pytest

from seven_line import BANDS, calculate_seven_lines, run_position_backtest


def sample():
    days = pd.bdate_range('2019-01-01', periods=1050)
    prices = 100 + np.arange(len(days)) * .04 + 9 * np.sin(np.arange(len(days)) / 19)
    return [{'date': day.date().isoformat(), 'close': float(price)} for day, price in zip(days, prices)]


def test_replay_matches_original_weekly_formula_and_no_future_leak():
    candles = sample()
    result = calculate_seven_lines(candles)
    closes = pd.Series([c['close'] for c in candles], index=pd.to_datetime([c['date'] for c in candles]))
    weekly = closes.resample('W').last()
    errors, predictions = [], []
    for j in range(len(weekly)):
        y = weekly.iloc[max(0, j - 181):j + 1].to_numpy()
        if len(y) < 2:
            predictions.append(np.nan)
            errors.append(np.nan)
            continue
        slope, intercept = np.linalg.lstsq(np.vstack([np.arange(len(y)), np.ones(len(y))]).T, y, rcond=None)[0]
        forecast = slope * len(y) + intercept
        predictions.append(forecast)
        errors.append(y[-1] - forecast)
    for i, day in enumerate(result.index):
        if day.weekday() == 4 and result.iloc[i]['位置'] == result.iloc[i]['位置']:
            j = weekly.index.get_loc(day.to_period('W').end_time.normalize())
            std = pd.Series(errors[max(0, j - 181):j + 1]).std()
            assert result.iloc[i]['3.5Y regression'] == pytest.approx(predictions[j])
            assert result.iloc[i]['CI 0.002'] == pytest.approx(predictions[j] + NormalDist().inv_cdf(.002) * std)
    prefix = calculate_seven_lines(candles[:1003])
    pd.testing.assert_frame_equal(result.iloc[:1003], prefix)


def test_full_and_zero_exposure_returns_and_warmup_rejection():
    lines = calculate_seven_lines(sample())
    selected = lines.iloc[-30:]
    start, end = selected.index[0].date(), selected.index[-1].date()
    full = run_position_backtest(lines, start, end, 100000, [100] * 8)
    expected = 100000 * selected['收盤價'].iloc[-1] / selected['收盤價'].iloc[0]
    assert full['期末資產'] == pytest.approx(expected)
    flat = run_position_backtest(lines, start, end, 100000, [0] * 8)
    assert flat['期末資產'] == 100000
    assert full['log'].iloc[0]['訊號日期'] == start.isoformat()
    with pytest.raises(ValueError, match='暖機'):
        run_position_backtest(lines, lines.index[0].date(), end, 100000, [100] * 8)


def test_seven_line_form_submits_and_keeps_results(tmp_path):
    from streamlit.testing.v1 import AppTest
    app = tmp_path / 'seven_ui.py'
    app.write_text('''
from datetime import date, timedelta
import numpy as np
import pandas as pd
from seven_line_ui import render_strategy_comparison

def history(symbol, period):
    days = pd.bdate_range(end=date.today(), periods=1400)
    candles = [{'date': day.date().isoformat(), 'close': 100 + i * .04 + 9 * np.sin(i / 19)} for i, day in enumerate(days)]
    return {'ticker': symbol, 'candles': candles}

def lao(candles, start, end, capital):
    curve = [{'date': c['date'], 'value': capital} for c in candles if str(start) <= c['date'] <= str(end)]
    return {'curve': curve, 'log_rows': [[str(start), str(end), capital]], 'log_columns': ['start', 'end', 'capital'], 'log_csv': 'start,end,capital'}

render_strategy_comparison('0050.TW', history, lao)
''')
    at = AppTest.from_file(str(app)).run()
    assert not at.exception
    assert len(at.date_input) == 2
    assert len(at.button) == 1
    assert at.date_input[0].label == '回測開始日'
    assert at.date_input[1].label == '回測結束日'
    from datetime import date, timedelta
    requested_start = date.today() - timedelta(days=180)
    requested_end = date.today() - timedelta(days=5)
    at.date_input[0].set_value(requested_start)
    at.date_input[1].set_value(requested_end)
    next(widget for widget in at.number_input if widget.label == '共同起始資金').set_value(200000)
    at.button[0].click().run(timeout=60)
    assert not at.exception
    assert len(at.table) == 3
    assert at.session_state['strategy_comparison_result_0050.TW_body-v1']['symbol'] == '0050.TW'
    saved = at.session_state['strategy_comparison_result_0050.TW_body-v1']
    assert saved['capital'] == 200000
    assert saved['lao_result']['log_rows'][0] == [str(requested_start), str(requested_end), 200000]
    assert saved['lao_result']['curve'][0]['date'] == saved['result']['curve'][0]['date']
    assert saved['lao_result']['curve'][-1]['date'] == saved['result']['curve'][-1]['date']
    assert saved['lao_result']['curve'][0]['value'] == saved['result']['curve'][0]['value']
    assert saved['metrics'].shape[0] == 3
    at.run(timeout=60)
    assert not at.exception
    assert len(at.table) == 3
