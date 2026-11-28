import pandas as pd
import pytest

import streamlit_app as app


def test_loader_filters_invalid_ohlc_preserves_tiny_prices_and_backtest(monkeypatch):
    days = pd.bdate_range('2020-01-01', periods=45)
    raw = pd.DataFrame({'Open': .003, 'High': .004, 'Low': .002,
                        'Close': .0035, 'Volume': 1000}, index=days)
    raw.loc[days[0], 'Open'] = 0
    raw.loc[days[1], 'Close'] = 0
    raw.loc[days[2], 'Low'] = -1
    raw.loc[days[3], 'High'] = float('inf')
    raw.loc[days[4], 'Open'] = float('nan')
    class Ticker:
        def history(self, **kwargs):
            return raw.copy()
    monkeypatch.setattr(app.yf, 'Ticker', lambda symbol: Ticker())
    app.load_history.clear()
    try:
        payload = app.load_history('VALIDATION', 'max')
        assert payload['discarded_rows'] == 5
        assert len(payload['candles']) == 40
        assert payload['candles'][0]['open'] == .003
        assert payload['candles'][0]['close'] == .0035
        candles = payload['candles']
        start = pd.Timestamp(candles[31]['date']).date()
        end = pd.Timestamp(candles[-1]['date']).date()
        result = app.backtest_lao_wang(candles, start, end, 100000)
        assert result['final_value'] == pytest.approx(100000)
        assert result['sessions'] == 8
    finally:
        app.load_history.clear()


def test_summary_rejects_invalid_open_with_clear_error():
    candles = [{'date': f'2020-01-{i + 1:02d}', 'open': 100, 'high': 101,
                'low': 99, 'close': 100, 'volume': 1000} for i in range(30)]
    candles[25]['open'] = 0
    with pytest.raises(ValueError, match='無效價格'):
        app.summarize_lao_wang(candles)
