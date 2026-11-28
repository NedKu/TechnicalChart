"""Causal replay of NedKu/STOCK_PER_PBR_Trend price CI formula.

Reference: analysis.py at c1af2867db4573fca7ae136ce2f007fbee92a810.
The source uses a one-step regression forecast (x=n) and sample standard
 deviation of rolling forecast errors; these are not regression confidence
intervals or integer sigma bands. Each day here rebuilds only its partial week.
"""
from bisect import bisect_right
from statistics import NormalDist

import numpy as np
import pandas as pd

QUANTILES = (0.002, 0.025, 0.125, 0.875, 0.975, 0.999)
BANDS = ("CI 0.002", "CI 0.025", "CI 0.125", "3.5Y regression",
         "CI 0.875", "CI 0.975", "CI 0.999")


def _forecast(values):
    x = np.arange(len(values), dtype=float)
    slope, intercept = np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), values, rcond=None)[0]
    return float(slope * len(values) + intercept)


def calculate_seven_lines(candles):
    frame = pd.DataFrame(candles).copy()
    frame.index = pd.to_datetime(frame.pop("date"))
    frame = frame.sort_index()
    if frame.index.has_duplicates or (frame["close"] <= 0).any():
        raise ValueError("日 K 日期重複或收盤價無效。")
    closes = frame["close"].astype(float)
    if not np.isfinite(closes).all():
        raise ValueError("收盤價包含無效數值。")
    # W-SUN matches the source's resample('W').last(); no fabricated empty weeks.
    weeks = closes.index.to_period("W-SUN")
    weekly = closes.groupby(weeks).last()
    week_list = list(weekly.index)
    errors = []
    for j in range(len(weekly)):
        tail = weekly.iloc[max(0, j - 181):j + 1].to_numpy()
        errors.append(float(tail[-1] - _forecast(tail)) if len(tail) >= 2 else np.nan)
    records = []
    for day, price, week in zip(closes.index, closes, weeks):
        j = week_list.index(week)
        past = weekly.iloc[max(0, j - 181):j].to_numpy()
        values = np.append(past, price)
        if len(values) < 182:
            records.append([np.nan] * 9)
            continue
        regression = _forecast(values)
        residuals = np.append(errors[max(0, j - 181):j], price - regression)
        if not np.isfinite(residuals).all():
            records.append([np.nan] * 9)
            continue
        deviation = float(np.std(residuals, ddof=1))
        if deviation <= 0:
            records.append([np.nan] * 9)
            continue
        quantiles = [regression + NormalDist().inv_cdf(q) * deviation for q in QUANTILES]
        bands = quantiles[:3] + [regression] + quantiles[3:]
        records.append(bands + [bisect_right(bands, price), deviation])
    result = pd.DataFrame(records, index=frame.index, columns=[*BANDS, "位置", "偏差標準差"])
    result.insert(0, "收盤價", closes)
    result["3.5Y 日均線（882日）"] = closes.rolling(882, min_periods=882).mean()
    return result


def run_position_backtest(lines, start, end, capital, weights):
    if len(weights) != 8 or any(not 0 <= w <= 100 for w in weights):
        raise ValueError("位置 0–7 的水位必須介於 0–100%。")
    selected = lines.loc[str(start):str(end)].copy()
    if len(selected) < 2:
        raise ValueError("區間至少需要兩個交易日。")
    if selected[list(BANDS)].isna().any().any():
        raise ValueError("區間缺少完整 182 週回歸／偏差暖機資料，請延後開始日。")
    value = float(capital)
    rows = []
    curve = [{"date": selected.index[0].date().isoformat(), "value": value}]
    previous_weight = 0.0
    for i in range(1, len(selected)):
        signal, current = selected.iloc[i - 1], selected.iloc[i]
        zone = int(signal["位置"])
        weight = weights[zone] / 100
        action = "加碼" if weight > previous_weight else "減碼" if weight < previous_weight else "維持"
        daily_return = weight * (current["收盤價"] / signal["收盤價"] - 1)
        value *= 1 + daily_return
        rows.append({"訊號日期": selected.index[i - 1].date().isoformat(),
                     "報酬日期": selected.index[i].date().isoformat(), "位置": zone,
                     "配置動作": action, "前一目標水位": f"{previous_weight:.0%}",
                     "本次目標水位": f"{weight:.0%}",
                     "判斷原因": f"收盤 {signal['收盤價']:.2f} 位於位置 {zone}，依自訂表配置 {weight:.0%}",
                     **{name: signal[name] for name in BANDS},
                     "策略日報酬%": daily_return * 100, "累積報酬%": (value / capital - 1) * 100,
                     "資產": value})
        curve.append({"date": selected.index[i].date().isoformat(), "value": value})
        previous_weight = weight
    return {"curve": curve, "log": pd.DataFrame(rows), **performance(curve, capital)}


def performance(curve, capital):
    values = pd.Series([r["value"] for r in curve], dtype=float)
    days = (pd.Timestamp(curve[-1]["date"]) - pd.Timestamp(curve[0]["date"])).days
    ratio = values.iloc[-1] / capital
    return {"期末資產": values.iloc[-1], "累積報酬率%": (ratio - 1) * 100,
            "年化複合報酬率%": (ratio ** (365.25 / days) - 1) * 100,
            "最大回撤%": (values / values.cummax() - 1).min() * 100}
