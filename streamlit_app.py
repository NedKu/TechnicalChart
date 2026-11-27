"""Streamlit entry point for the Lao Wang technical-analysis dashboard."""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf


PAGE = Path(__file__).parent / "v0" / "gemini-code-1795528199482.html"
MARKER = "const STREAMLIT_PAYLOAD = null;"
PROMPT_MARKER = "const STREAMLIT_REVIEW_PROMPT = null;"
WATCHLIST = {
    "0050.TW": "元大台灣50",
    "2330.TW": "台積電",
    "6285.TW": "啟碁",
    "2327.TW": "國巨",
    "2317.TW": "鴻海",
    "6488.TWO": "環球晶",
    "8299.TWO": "群聯",
    "VT": "Vanguard 全世界",
    "VWRA": "Vanguard FTSE All-World UCITS ETF",
    "QQQ": "Invesco QQQ",
    "VOO": "Vanguard S&P 500",
    "MU": "Micron Technology",
    "DRAM": "DRAM",
    "NVDA": "NVIDIA",
}


def ticker_candidates(symbol: str) -> list[str]:
    if symbol == "VWRA":
        return ["VWRA.L"]
    if re.fullmatch(r"\d{4,6}[A-Z]?", symbol):
        return [f"{symbol}.TW", f"{symbol}.TWO"]
    return [symbol]


@st.cache_data(ttl=900, show_spinner=False)
def load_history(symbol: str, period: str = "1y") -> dict:
    errors = []
    for ticker in ticker_candidates(symbol):
        try:
            frame = yf.Ticker(ticker).history(
                period=period, interval="1d", auto_adjust=True, timeout=15
            )
            if frame is None or frame.empty:
                errors.append(f"{ticker}: 無歷史資料")
                continue
            candles = []
            for date, row in frame.iterrows():
                values = [row[col] for col in ("Open", "High", "Low", "Close", "Volume")]
                if not all(math.isfinite(float(value)) for value in values):
                    continue
                candles.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "open": round(float(row["Open"]), 2),
                        "high": round(float(row["High"]), 2),
                        "low": round(float(row["Low"]), 2),
                        "close": round(float(row["Close"]), 2),
                        "volume": max(0, int(row["Volume"])),
                    }
                )
            if len(candles) >= 30:
                return {
                    "symbol": re.sub(r"\.(TW|TWO)$", "", symbol),
                    "ticker": ticker,
                    "name": WATCHLIST.get(symbol, ticker),
                    "candles": candles,
                }
            errors.append(f"{ticker}: 可用日 K 不足 30 筆")
        except Exception as exc:
            errors.append(f"{ticker}: {exc}")
    raise ValueError("；".join(errors))


def summarize_lao_wang(candles: list[dict]) -> dict:
    """Summarize the dashboard's primary moving-average and volume rules."""
    import pandas as pd

    frame = pd.DataFrame(candles)
    for period in (5, 10, 20, 60, 120, 240):
        frame[f"ma{period}"] = frame["close"].rolling(period).mean()
    last = frame.iloc[-1]
    prev = frame.iloc[-2]
    close = float(last["close"])
    above = {p: close >= float(last[f"ma{p}"]) for p in (5, 10, 20, 60, 120, 240)}
    recent20 = frame.tail(20)
    max_volume = recent20.loc[recent20["volume"].idxmax()]
    bearish_volume_break = close < float(max_volume["low"]) and max_volume["date"] != last["date"]
    recent65 = frame.tail(65).iloc[:-5]
    prior_high = float(recent65["high"].max()) if not recent65.empty else float(last["high"])
    false_breakout = float(prev["high"]) > prior_high and close < prior_high and not above[5]
    three_below = not above[5] and not above[10] and not above[20]
    four_below = three_below and not above[60]
    six_below = four_below and not above[120] and not above[240]
    three_above = above[5] and above[10] and above[20]
    four_above = three_above and above[60]
    six_above = four_above and above[120] and above[240]
    streak20 = 0
    for row in frame.iloc[::-1].itertuples():
        ma20_value = getattr(row, "ma20")
        if math.isfinite(float(ma20_value)) and float(row.close) >= float(ma20_value):
            streak20 += 1
        else:
            break
    # Match the detail dashboard: retain the latest breakout until a close
    # falls below the low of its triggering high-volume candle.
    active_volume_swap = None
    volume_scan_start = max(20, len(frame) - 60)
    for i in range(volume_scan_start, len(frame)):
        bar = frame.iloc[i]
        if active_volume_swap and float(bar["close"]) < active_volume_swap["low"]:
            active_volume_swap = None
        prior_bars = frame.iloc[max(0, i - 20):i]
        if len(prior_bars) < 20:
            continue
        trigger = prior_bars.loc[prior_bars["volume"].idxmax()]
        if float(bar["close"]) > float(trigger["high"]):
            active_volume_swap = {
                "date": bar["date"],
                "low": float(trigger["low"]),
            }
    open_bull_gaps = []
    open_bear_gaps = []
    for i in range(1, len(frame)):
        current, previous = frame.iloc[i], frame.iloc[i - 1]
        if float(current["low"]) > float(previous["high"]) * 1.001 and not (
            frame.iloc[i + 1:]["low"] <= float(previous["high"])
        ).any():
            open_bull_gaps.append({"date": current["date"], "idx": i,
                                   "bottom": float(previous["high"]), "top": float(current["low"])})
        if float(current["high"]) < float(previous["low"]) * 0.999 and not (
            frame.iloc[i + 1:]["high"] >= float(previous["low"])
        ).any():
            open_bear_gaps.append({"date": current["date"], "idx": i,
                                   "bottom": float(current["high"]), "top": float(previous["low"])})
    frame["avg_volume_25"] = frame["volume"].rolling(25).mean()
    active_key_long_red = None
    for row in frame.iloc[24:].itertuples():
        if active_key_long_red and float(row.close) < active_key_long_red["low"]:
            active_key_long_red = None
        if ((float(row.close) - float(row.open)) / float(row.open) >= 0.025
                and float(row.volume) >= float(row.avg_volume_25) * 1.2):
            active_key_long_red = {"date": row.date, "low": float(row.low)}
    active_status = []
    if open_bull_gaps:
        active_status.append(f"多方缺口 {len(open_bull_gaps)} 個未封閉")
    if open_bear_gaps:
        active_status.append(f"空方缺口 {len(open_bear_gaps)} 個未封閉")
    island_bear = next((
        bear for bear in open_bear_gaps
        if any(bear["idx"] > bull["idx"] for bull in open_bull_gaps)
    ), None)
    if island_bear:
        active_status.append(f"孤島反轉訊號仍有效（空方缺口 {island_bear['date']}）")
    if active_key_long_red:
        active_status.append(f"關鍵長紅支撐有效（{active_key_long_red['date']}）")
    if active_volume_swap:
        active_status.append(f"天量成功換手仍有效（{active_volume_swap['date']}）")
    if bearish_volume_break or false_breakout or four_below or six_below:
        position, conclusion = 15, "🛑 避險／停損：等收復 10MA 再評估"
    elif three_below:
        position, conclusion = 25, "⚠️ 三聲無奈：先賣再買，等待站回月線"
    elif not above[10] and above[20]:
        position, conclusion = 30, "📤 跌破 10MA：減碼，守月線觀察"
    elif not above[5] and above[10]:
        position, conclusion = 50, "✂️ 跌破 5MA：減碼一半，守 10MA"
    elif (six_above and float(last["ma5"]) > float(frame.iloc[-4]["ma5"])
          and float(last["ma10"]) > float(frame.iloc[-4]["ma10"])) or (
              len(recent65) >= 60 and close > prior_high and above[5] and above[10] and above[20]
          ):
        position, conclusion = 85, "🚀 海闊天空：沿 10MA 抱牢，避免追高"
    elif three_above:
        position = 75 if close > prior_high else 55
        conclusion = "🟢 三陽開泰：分批布局" if position == 75 else "🟡 三陽開泰：缺口壓力下先建倉"
    else:
        position, conclusion = 40, "⚖️ 均線整理：觀察區間低點與關鍵長紅低點"
    if active_volume_swap:
        conclusion += f"；🔥 天量成功換手（訊號 {active_volume_swap['date']}，未跌破天量低點）"
    previous_close = float(prev["close"])
    daily_change_pct = (close / previous_close - 1) * 100 if previous_close else 0.0
    avg_volume_25 = float(frame["volume"].rolling(25).mean().iloc[-1])
    supports = [
        {"名稱": "10MA", "價格": float(last["ma10"])},
        {"名稱": "20MA", "價格": float(last["ma20"])},
    ]
    if active_volume_swap:
        supports.append({"名稱": f"天量成功換手低點（{active_volume_swap['date']}）",
                         "價格": active_volume_swap["low"]})
    if active_key_long_red:
        supports.append({"名稱": f"關鍵長紅低點（{active_key_long_red['date']}）",
                         "價格": active_key_long_red["low"]})
    supports.extend({"名稱": f"未封閉多方缺口下緣（{gap['date']}）", "價格": gap["bottom"]}
                    for gap in open_bull_gaps)
    valid_supports = [level for level in supports
                      if math.isfinite(level["價格"]) and level["價格"] <= close]
    primary_support = max(valid_supports, key=lambda level: level["價格"]) if valid_supports else {
        "名稱": "最近交易日低點（參考價）", "價格": float(last["low"])
    }


    slope_status = lambda period: (
        "上彎" if float(last[f"ma{period}"]) > float(frame.iloc[-4][f"ma{period}"])
        else "下彎或持平"
    ) if math.isfinite(float(last[f"ma{period}"])) and math.isfinite(float(frame.iloc[-4][f"ma{period}"])) else "資料不足"
    checks = [
        ("收盤站上 5MA／10MA／20MA（三陽開泰）", three_above),
        ("收盤站上 5MA／10MA／20MA／60MA（四線偏多）", four_above),
        ("連續站上月線至少 3 日", streak20 >= 3),
        ("收盤跌破 5MA／10MA／20MA（三聲無奈）", three_below),
        ("收盤跌破 5MA／10MA／20MA／60MA（四面楚歌）", four_below),
        ("收盤跌破六條均線", six_below),
        ("假突破訊號", false_breakout),
        ("跌破近 20 日天量 K 棒低點", bearish_volume_break),
        ("天量成功換手仍有效", active_volume_swap is not None),
        ("關鍵長紅支撐仍有效", active_key_long_red is not None),
        ("仍有未封閉多方缺口", bool(open_bull_gaps)),
        ("仍有未封閉空方缺口", bool(open_bear_gaps)),
        ("孤島反轉訊號仍有效", island_bear is not None),
    ]
    return {
        "操作結論": conclusion,
        "持續中狀態": "；".join(active_status) if active_status else "目前無未解除的結構訊號",
        "建議持股水位": f"{position}%",
        "保留現金": f"{100 - position}%",
        "收盤價": round(close, 2),
        "5MA / 10MA": f"{last['ma5']:.2f} / {last['ma10']:.2f}",
        "20MA / 60MA": f"{last['ma20']:.2f} / {last['ma60']:.2f}",
        "資料日期": last["date"],
        "_當日漲跌幅": daily_change_pct,
        "_成交量／25日均量": f"{int(last['volume']):,} / {avg_volume_25:,.0f}",
        "_六線": {period: float(last[f"ma{period}"]) if math.isfinite(float(last[f"ma{period}"])) else None
                  for period in (5, 10, 20, 60, 120, 240)},
        "_均線斜率": {period: slope_status(period) for period in (5, 10, 20, 60)},
        "_檢核清單": checks,
        "_防守候選價": supports,
        "_關鍵防守價": primary_support,
    }

def backtest_lao_wang(candles: list[dict], start: date, end: date,
                      initial_capital: float = 100_000) -> dict:
    """Apply each close's suggested exposure to the following session."""
    in_range = [bar for bar in candles if start.isoformat() <= bar["date"] <= end.isoformat()]
    if len(in_range) < 2:
        raise ValueError("所選區間至少需要兩個交易日。")
    indexed = {bar["date"]: i for i, bar in enumerate(candles)}
    first_index, last_index = indexed[in_range[0]["date"]], indexed[in_range[-1]["date"]]
    if first_index < 30:
        raise ValueError("所選開始日缺少足夠的前置日 K，至少需要 30 個交易日暖機。")

    value = float(initial_capital)
    curve = [{"date": in_range[0]["date"], "value": value}]
    previous_exposure = int(summarize_lao_wang(candles[:first_index])["建議持股水位"].rstrip("%")) / 100
    for i in range(first_index + 1, last_index + 1):
        prior_close = float(candles[i - 1]["close"])
        close = float(candles[i]["close"])
        value *= 1 + previous_exposure * (close / prior_close - 1)
        curve.append({"date": candles[i]["date"], "value": value})
        if i < last_index:
            previous_exposure = int(summarize_lao_wang(candles[:i + 1])["建議持股水位"].rstrip("%")) / 100

    elapsed_days = (date.fromisoformat(in_range[-1]["date"]) - date.fromisoformat(in_range[0]["date"])).days
    total_return = value / initial_capital - 1
    annualized_return = (value / initial_capital) ** (365.25 / elapsed_days) - 1 if elapsed_days > 0 else 0.0
    peak = initial_capital
    max_drawdown = 0.0
    for point in curve:
        peak = max(peak, point["value"])
        max_drawdown = min(max_drawdown, point["value"] / peak - 1)
    return {"curve": curve, "final_value": value, "total_return": total_return,
            "annualized_return": annualized_return, "max_drawdown": max_drawdown,
            "sessions": len(in_range) - 1}

def indicator_snapshot(candles: list[dict]) -> dict:
    closes = [float(bar["close"]) for bar in candles]
    highs = [float(bar["high"]) for bar in candles]
    lows = [float(bar["low"]) for bar in candles]
    volumes = [float(bar["volume"]) for bar in candles]
    vol_ma5 = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else None
    vol_ratio = volumes[-1] / vol_ma5 if vol_ma5 else None

    rsi = None
    if len(closes) > 14:
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [max(change, 0) for change in changes]
        losses = [max(-change, 0) for change in changes]
        avg_gain = sum(gains[:14]) / 14
        avg_loss = sum(losses[:14]) / 14
        for i in range(14, len(gains)):
            avg_gain = (avg_gain * 13 + gains[i]) / 14
            avg_loss = (avg_loss * 13 + losses[i]) / 14
        rsi = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)

    k = d = 50.0
    for i in range(len(closes)):
        start = max(0, i - 8)
        high_n, low_n = max(highs[start:i + 1]), min(lows[start:i + 1])
        rsv = 50.0 if high_n == low_n else (closes[i] - low_n) / (high_n - low_n) * 100
        k = (2 / 3) * k + (1 / 3) * rsv
        d = (2 / 3) * d + (1 / 3) * k

    def ema(values: list[float], period: int) -> list[float | None]:
        output: list[float | None] = [None] * len(values)
        if len(values) < period:
            return output
        current = sum(values[:period]) / period
        output[period - 1] = current
        alpha = 2 / (period + 1)
        for i in range(period, len(values)):
            current = values[i] * alpha + current * (1 - alpha)
            output[i] = current
        return output

    fast, slow = ema(closes, 12), ema(closes, 26)
    macd = [None if fast[i] is None or slow[i] is None else fast[i] - slow[i]
            for i in range(len(closes))]
    first = next((i for i, value in enumerate(macd) if value is not None), None)
    macd_hist = None
    if first is not None:
        signal_tail = ema([value or 0.0 for value in macd[first:]], 9)
        if signal_tail and signal_tail[-1] is not None and macd[-1] is not None:
            macd_hist = macd[-1] - signal_tail[-1]
    return {"vol_ma5": vol_ma5, "vol_ratio": vol_ratio, "rsi": rsi,
            "k": k, "d": d, "macd_hist": macd_hist,
            "three_day_low": min(lows[-3:]) if len(lows) >= 3 else None}


def market_status_for(symbol: str, period: str, review_date: str) -> str:
    is_taiwan = bool(re.fullmatch(r"\d{4,6}[A-Z]?", symbol))
    benchmark = "^TWII" if is_taiwan else "SPY"
    benchmark_name = "加權指數" if is_taiwan else "S&P 500 ETF（SPY）"
    try:
        benchmark_period = "1y" if period == "1mo" else period
        history = load_history(benchmark, benchmark_period)["candles"]
        history = [bar for bar in history if bar["date"] <= review_date]
        if len(history) < 20:
            return f"{benchmark_name}資料不足，無法判定月線趨勢"
        closes = [float(bar["close"]) for bar in history]
        close = closes[-1]
        ma20 = sum(closes[-20:]) / 20
        above20 = close >= ma20
        if len(closes) < 60:
            return f"{benchmark_name}收盤 {close:.2f}，{'站上' if above20 else '跌破'}月線 {ma20:.2f}；季線資料不足"
        ma60 = sum(closes[-60:]) / 60
        above60 = close >= ma60
        status = "多頭排列" if ma20 >= ma60 else "未呈多頭排列"
        return (f"{benchmark_name}收盤 {close:.2f}，{'站上' if above20 else '跌破'}月線 {ma20:.2f}、"
                f"{'站上' if above60 else '跌破'}季線 {ma60:.2f}，{status}")
    except Exception:
        return f"{benchmark_name}資料無法取得；請勿推測大盤狀態"


def build_ai_review_prompt(
    symbol: str, name: str, review_date: str, summary: dict,
    candles: list[dict], market_status: str,
) -> str:
    """Build a copy-ready, evidence-bound next-session review prompt."""
    checks = "\n".join(
        f"- [{'x' if passed else ' '}] {label}：{'成立' if passed else '未成立'}"
        for label, passed in summary["_檢核清單"]
    )
    slopes = "、".join(f"{period}MA {slope}" for period, slope in summary["_均線斜率"].items())
    support_levels = "；".join(
        f"{level['名稱']} {level['價格']:.2f}" for level in summary["_防守候選價"]
    )
    defense = summary["_關鍵防守價"]
    indicators = indicator_snapshot(candles)

    def fmt(value, digits=2):
        return f"{value:.{digits}f}" if value is not None else "資料不足"

    vol_ratio = f"{indicators['vol_ratio']:.2f}x" if indicators["vol_ratio"] is not None else "資料不足"
    return f"""你是一位嚴格執行「老王技術分析戰法」的台股／美股操盤教練。請根據以下【真實盤後數據】進行無情且客觀的紀律覆盤，嚴禁憑感覺猜測、補造數據或把推論說成事實。資料不足時請明確標示「資料不足」。

【標的資訊】
- 股票代號與名稱：{symbol}（{name}）
- 大盤基準狀態：{market_status}
- 最新收盤價：{summary['收盤價']:.2f}（漲跌幅：{summary['_當日漲跌幅']:+.2f}%）
- 盤後資料日：{summary['資料日期']}（回顧日期：{review_date}）

【關鍵技術指標與六線數據】
- 均線系統：5MA={fmt(summary['_六線'][5])} | 10MA={fmt(summary['_六線'][10])} | 20MA(月線)={fmt(summary['_六線'][20])} | 60MA(季線)={fmt(summary['_六線'][60])}
- 半年線／年線：120MA={fmt(summary['_六線'][120])} | 240MA={fmt(summary['_六線'][240])}；均線斜率：{slopes}
- 量能狀態：今日成交量={int(candles[-1]['volume']):,}（5日均量={fmt(indicators['vol_ma5'], 0)}，量比={vol_ratio}）
- 指標狀態：RSI(14)={fmt(indicators['rsi'])} | KD(9,3,3)（K={indicators['k']:.2f}, D={indicators['d']:.2f}） | MACD柱狀體={fmt(indicators['macd_hist'])}
- 系統操作結論：{summary['操作結論']}
- 系統建議持股水位：{summary['建議持股水位']}；保留現金：{summary['保留現金']}
- 持續中的結構訊號：{summary['持續中狀態']}

【老王戰法診斷清單】
1. 趨勢位階：收盤是否站穩月線／季線？均線是否呈多頭排列？實際檢核：
{checks}
   均線斜率：{slopes}
2. 型態與支撐壓力：是否突破前高頸線，或跌破關鍵防守價？不得推定未提供的頸線或型態。
3. 量價配合：上漲是否有量（大於5日均量），下跌是否量縮？量比以今日成交量除以5日均量計算。

【下一交易日關鍵防守價（停損點）】
- 系統參考價：{defense['價格']:.2f}（{defense['名稱']}）。請依據上方結構判斷是否合適，不得把支撐描述成保證有效。
- 其他候選支撐：{support_levels or '目前沒有可用的結構支撐資料'}。
- 近三日最低價參考：{fmt(indicators['three_day_low'])}；請區分盤中跌破與收盤確認，勿因短暫刺穿就斷言趨勢反轉。
- 若候選支撐皆已失守，明確指出目前沒有可靠支撐，不要虛構替代價位。

【下一交易日觀察重點】
1. 價格相對關鍵防守價、10MA、20MA 的位置；仍在均線下方時，觀察能否收復，不以盤中反彈直接判定轉強。
2. 收盤是否守住關鍵防守價及三日低點，是否站回 5MA／10MA／20MA。
3. 漲跌時成交量相對 5 日均量的變化，分辨價漲量增、價跌量縮。
4. 未封閉缺口、天量成功換手低點與關鍵長紅低點是否被觸及或有效跌破。
5. KD／MACD 是否轉強或轉弱，只作輔助訊號，不單獨取代價格與均線紀律。

【輸出要求】
1. 給予明確的【操作建議燈號】：綠燈買進／續抱、黃燈觀望、紅燈減碼／停損；說明燈號依據，若多空訊號衝突要指出。
2. 條列指出「符合的買進條件」與「風險警訊」，逐項引用數據，不得只給結論。
3. 明確給出下一交易日的【關鍵防守價（停損點）】與【觀察重點】，分別說明盤中觸及和收盤確認時的應對。
4. 嚴格遵守既有老王紀律，不因單一指標過熱追高，不攤平破線部位；不得預測尚未發生的行情。"""


def add_to_watchlist() -> None:
    symbol = st.session_state.new_symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9^.-]{1,20}", symbol):
        st.session_state.watchlist_message = "請輸入有效的台股、美股或 ETF 代號。"
        return
    if symbol not in st.session_state.watchlist:
        st.session_state.watchlist.append(symbol)
    st.session_state.watch_selected = symbol
    st.session_state.new_symbol = ""
    st.session_state.watchlist_message = ""


def remove_from_watchlist() -> None:
    if len(st.session_state.watchlist) == 1:
        st.session_state.watchlist_message = "觀察名單至少保留一個標的。"
        return
    st.session_state.watchlist.remove(st.session_state.watch_selected)
    st.session_state.watch_selected = st.session_state.watchlist[0]
    st.session_state.watchlist_message = ""


def reset_watchlist() -> None:
    st.session_state.watchlist = list(WATCHLIST)
    st.session_state.watch_selected = st.session_state.watchlist[0]
    st.session_state.watchlist_message = ""


def main() -> None:
    st.set_page_config(page_title="老王技術分析戰法診斷器", layout="wide")
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = list(WATCHLIST)
    if st.session_state.get("watch_selected") not in st.session_state.watchlist:
        st.session_state.watch_selected = st.session_state.watchlist[0]
    st.sidebar.title("行情查詢")
    selected = st.sidebar.selectbox(
        "觀察名單",
        st.session_state.watchlist,
        format_func=lambda item: f"{item} · {WATCHLIST[item]}" if item in WATCHLIST else item,
        key="watch_selected",
    )
    st.sidebar.text_input("新增代號", placeholder="例如 0050.TW、NVDA", key="new_symbol")
    st.sidebar.button("＋ 加入觀察名單", on_click=add_to_watchlist)
    left, right = st.sidebar.columns(2)
    left.button("移除選取", on_click=remove_from_watchlist)
    right.button("重設預設", on_click=reset_watchlist)
    if st.session_state.get("watchlist_message"):
        st.sidebar.warning(st.session_state.watchlist_message)
    raw_symbol = selected
    symbol = re.sub(r"\.(TW|TWO)$", "", raw_symbol)
    data_period = st.sidebar.selectbox("行情下載期間", ["1mo", "3mo", "6mo", "1y", "2y", "3y", "5y"], index=3,
                                        format_func=lambda p: {"1mo":"1 個月", "3mo":"3 個月", "6mo":"6 個月", "1y":"1 年", "2y":"2 年", "3y":"3 年", "5y":"5 年"}[p])
    st.sidebar.caption("預設下載 1 年日 K；選擇較長區間時才下載更多歷史資料。行情快取 15 分鐘。")
    try:
        with st.spinner(f"讀取 {symbol} 的 {data_period} 日 K…"):
            payload = load_history(raw_symbol, data_period)
    except ValueError as exc:
        st.error(f"無法載入 {symbol} 的有效行情：{exc}")
        st.info("請確認代號與網路連線後重試；不會使用模擬價格。")
        return

    first_day = date.fromisoformat(payload["candles"][0]["date"])
    last_day = date.fromisoformat(payload["candles"][-1]["date"])
    as_of = st.sidebar.date_input(
        "回顧日期",
        value=last_day,
        min_value=first_day,
        max_value=last_day,
        help="儀表板及觀察名單總覽只使用所選日期當天及之前的行情。",
        key=f"review_date_{raw_symbol}_{data_period}",
    )
    as_of_text = as_of.isoformat()
    historical_candles = [bar for bar in payload["candles"] if bar["date"] <= as_of_text]
    if len(historical_candles) < 30:
        st.warning("所選日期之前的有效日 K 不足 30 筆，無法產生完整診斷。")
        return
    payload["candles"] = historical_candles
    payload["as_of"] = as_of_text
    selected_summary = summarize_lao_wang(historical_candles)
    market_status = market_status_for(symbol, data_period, as_of_text)
    review_prompt = build_ai_review_prompt(
        symbol=symbol,
        name=payload["name"],
        review_date=as_of_text,
        summary=selected_summary,
        candles=historical_candles,
        market_status=market_status,
    )

    html = PAGE.read_text(encoding="utf-8")
    if html.count(MARKER) != 1 or html.count(PROMPT_MARKER) != 1:
        st.error("HTML 資料接口不存在或重複，無法安全載入儀表板。")
        return
    # Escape closing tags and HTML specials before embedding JSON in a script.
    payload["range"] = {"1mo":"1m", "3mo":"3m", "6mo":"6m"}.get(data_period, data_period)
    data = json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c")
    html = html.replace(MARKER, f"const STREAMLIT_PAYLOAD = {data};", 1)
    prompt_data = json.dumps(review_prompt, ensure_ascii=True).replace("<", "\\u003c")
    html = html.replace(PROMPT_MARKER, f"const STREAMLIT_REVIEW_PROMPT = {prompt_data};", 1)
    components.html(html, height=1300, scrolling=True)

    st.subheader("📈 老王戰法歷史回測")
    st.caption("收盤訊號從下一交易日生效；使用還原權值日 K，未計手續費、稅費、滑價與股息稅。")
    earliest_backtest = max(30, 0)
    backtest_min = date.fromisoformat(payload["candles"][min(earliest_backtest, len(payload["candles"]) - 1)]["date"])
    range_col1, range_col2, capital_col = st.columns(3)
    backtest_start = range_col1.date_input("回測開始日", value=max(backtest_min, last_day - timedelta(days=365)),
                                           min_value=backtest_min, max_value=last_day, key=f"bt_start_{raw_symbol}_{data_period}")
    backtest_end = range_col2.date_input("回測結束日", value=last_day, min_value=backtest_min, max_value=last_day,
                                         key=f"bt_end_{raw_symbol}_{data_period}")
    capital = capital_col.number_input("起始資金", min_value=1_000, value=100_000, step=10_000,
                                       key=f"bt_capital_{raw_symbol}")
    if backtest_start > backtest_end:
        st.warning("回測開始日必須早於或等於結束日。")
    else:
        try:
            result = backtest_lao_wang(payload["candles"], backtest_start, backtest_end, capital)
            metric1, metric2, metric3, metric4 = st.columns(4)
            metric1.metric("期末資產", f"{result['final_value']:,.0f}")
            metric2.metric("區間報酬", f"{result['total_return']:+.2%}")
            metric3.metric("年均複合報酬", f"{result['annualized_return']:+.2%}")
            metric4.metric("最大回撤", f"{result['max_drawdown']:.2%}")
            st.caption(f"期間 {backtest_start} 至 {backtest_end}；計入 {result['sessions']} 個交易日報酬。年均回報以複合年化公式計算。")
            st.line_chart({"策略資產": {point["date"]: point["value"] for point in result["curve"]}}, x_label="日期", y_label="資產")
        except ValueError as exc:
            st.info(str(exc))

    st.subheader("📋 觀察名單總覽")
    st.caption(f"依 {as_of_text} 當天及之前的日 K 計算；價格為還原權值資料。")
    if st.button("🔄 更新全部行情", key="refresh_all_watchlist"):
        load_history.clear()
    summary_rows = []
    taipei_today = datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
    comparison_key = f"{taipei_today}|{as_of_text}"
    comparisons = st.session_state.setdefault("position_baselines", {})
    # Keep only today's review-date baselines in the current browser session.
    comparisons = {
        key: value for key, value in comparisons.items()
        if key.startswith(f"{taipei_today}|")
    }
    st.session_state.position_baselines = comparisons
    daily_baseline = comparisons.setdefault(comparison_key, {})
    for item in st.session_state.watchlist:
        name = WATCHLIST.get(item, item)
        try:
            result = load_history(item, data_period)
            historical = [bar for bar in result["candles"] if bar["date"] <= as_of_text]
            if len(historical) < 30:
                raise ValueError(f"{as_of_text} 前有效日 K 不足 30 筆")
            summary = summarize_lao_wang(historical)
            position = int(summary["建議持股水位"].rstrip("%"))
            baseline = daily_baseline.setdefault(item, position)
            change = ""
            if position != baseline:
                delta = position - baseline
                change = f"{baseline}% → {position}% ({delta:+d} 個百分點)"
            summary_rows.append({"代號": item, "名稱": result["name"] or name,
                                 **summary, "水位變化": change})
        except Exception as exc:
            summary_rows.append({"代號": item, "名稱": name, "操作結論": f"行情載入失敗：{exc}",
                                 "持續中狀態": "—",
                                 "建議持股水位": "—", "保留現金": "—", "收盤價": "—",
                                 "5MA / 10MA": "—", "20MA / 60MA": "—", "資料日期": "—",
                                 "水位變化": "—"})
    import pandas as pd

    summary_frame = pd.DataFrame(summary_rows)
    summary_frame = summary_frame[[
        "代號", "名稱", "操作結論", "持續中狀態", "建議持股水位", "水位變化",
        "保留現金", "收盤價", "5MA / 10MA", "20MA / 60MA", "資料日期",
    ]]

    def highlight_position_change(row):
        change = row.get("水位變化", "")
        if not isinstance(change, str) or "→" not in change:
            return [""] * len(row)
        before, after = (int(value.strip().rstrip("%")) for value in change.split("(", 1)[0].split("→"))
        color = "#34d399" if after > before else "#fb7185"
        background = "rgba(52, 211, 153, 0.12)" if after > before else "rgba(251, 113, 133, 0.12)"
        css = f"color: {color}; background-color: {background}; font-weight: 700;"
        return [css if column in {"建議持股水位", "水位變化"} else "" for column in row.index]

    st.caption("水位變化以今天首次查詢為基準；上升標綠、下降標紅，變化會保留在目前瀏覽工作階段。")
    st.dataframe(
        summary_frame.style.apply(highlight_position_change, axis=1),
        use_container_width=True,
        hide_index=True,
    )

if __name__ == "__main__":
    main()
