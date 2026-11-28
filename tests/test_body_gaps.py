import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from gap_logic import detect_body_gaps
from streamlit_app import summarize_lao_wang

CASES = json.loads(Path(__file__).with_name('body_gap_cases.json').read_text())


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['name'])
def test_body_gap_boundaries_and_fill_ignore_shadows(case):
    bull, bear = detect_body_gaps(case['candles'])
    assert bull == case['bull']
    assert bear == case['bear']


def test_summary_and_backtest_status_keep_shadow_only_gap_open():
    candles = [dict(date=str(date(2026, 1, 1) + timedelta(days=i)), open=98,
                    close=100, high=108, low=95, volume=1000) for i in range(30)]
    candles += [dict(bar, volume=1000) for bar in CASES[0]['candles']]
    summary = summarize_lao_wang(candles)
    assert '最新多方缺口 2026-02-03 未封閉（100.00–104.00）' in summary['持續中狀態']
    assert any(level['價格'] == 100 for level in summary['_防守候選價']
               if '多方缺口' in level['名稱'])


def test_backtest_log_uses_body_gap_status():
    from streamlit_app import backtest_lao_wang
    candles = [dict(date=str(date(2026, 1, 1) + timedelta(days=i)), open=98,
                    close=100, high=108, low=95, volume=1000) for i in range(30)]
    candles += [dict(bar, volume=1000) for bar in CASES[0]['candles']]
    candles.append(dict(date='2026-02-05', open=103, close=106, high=109, low=95, volume=1000))
    result = backtest_lao_wang(candles, date(2026, 2, 2), date(2026, 2, 5))
    logs = [dict(zip(result['log_columns'], row)) for row in result['log_rows']]
    signal = next(row for row in logs if row['訊號日期'] == '2026-02-04')
    assert '2026-02-03 未封閉（100.00–104.00）' in signal['持續中訊號（含未封閉缺口）']
