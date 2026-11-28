"""Independent seven-line research and comparison controls."""
from datetime import date, timedelta
import re

import pandas as pd
import streamlit as st

from seven_line import BANDS, calculate_seven_lines, performance, run_position_backtest


@st.cache_data(ttl=900, show_spinner=False)
def _lines(candles):
    return calculate_seven_lines(candles)


def render_seven_line_backtest(default_symbol, load_history, lao_wang_backtest):
    st.subheader("📊 七線標準差位置回測與比較")
    st.caption("沿用 Stock PER/PBR Trend 的 182 週回歸與偏差分位線。3.5Y regression 是回歸預測線；882 日均線另外顯示。")
    with st.expander("計算方式與回測判斷標準"):
        st.markdown(
            "每個交易日只用當時已知的週收盤（本週截至當日），以最近 182 週作線性回歸，"
            "延伸一週作為中線。最近 182 週回歸偏差的樣本標準差，搭配常態分位數產生六條界線。"
            "這與原 App 的算法一致，並以逐日重播避免使用尚未發生的週末資料。"
            "需完整暖機，不用短期資料冒稱 3.5 年。"
        )
        st.write("七條界線由低至高分成位置 0–7；等於界線時歸入較高位置。")
        st.write("位置0：低於CI .002；1：.002–.025；2：.025–.125；3：.125–回歸線；4：回歸線–.875；5：.875–.975；6：.975–.999；7：不低於.999。空白週不補造交易資料。")
        st.write("本區是可自訂水位的位置配置模型，尚未包含排程的 CI 四批、Guard、景氣燈號、SHY 或神龍條件。")
        st.write("每日收盤決定下一段收盤到收盤的目標水位；採理想化收盤再平衡、可零股、現金零利息，未計交易費稅與滑價。")
        st.write("資料採 yfinance 還原權值日 K；累積報酬＝期末資產／起始資金−1；年化報酬依實際日數複利換算。")
        st.write("老王比較列沿用既有優先序：天量低點失守／假突破／四線或六線跌破→15%；三聲無奈→25%；跌破10MA但守20MA→30%；跌破5MA但守10MA→50%；六線偏多且短均線上彎或突破前高→85%；三陽開泰→75%或55%；其餘整理→40%。未封閉缺口屬狀態資訊，不直接改變該模型水位。")
        st.markdown("[原始算法來源](https://github.com/NedKu/STOCK_PER_PBR_Trend/blob/c1af2867db4573fca7ae136ce2f007fbee92a810/src/stock_per_pbr_trend/analysis.py)")
    with st.form("seven_line_form"):
        left, middle, right = st.columns(3)
        symbol = left.text_input("七線回測股票代號", value=default_symbol).strip().upper()
        start = middle.date_input("七線開始日", value=date.today() - timedelta(days=365))
        end = right.date_input("七線結束日", value=date.today(), max_value=date.today())
        capital = st.number_input("七線起始資金", min_value=1000, value=100000, step=10000)
        st.write("各位置目標持股比例（%）：以下為可修改的研究範例，並非排程已確認的 CI 四批規則。")
        defaults = [100, 90, 80, 60, 40, 20, 10, 0]
        weights = []
        cols = st.columns(4)
        for zone, default in enumerate(defaults):
            weights.append(cols[zone % 4].number_input(f"位置 {zone} 持股%", min_value=0, max_value=100,
                                                       value=default, step=5))
        run = st.form_submit_button("執行七線回測並比較", type="primary")
    if run:
        try:
            if start >= end:
                raise ValueError("開始日需早於結束日。")
            if not re.fullmatch(r"[A-Z0-9^.-]{1,20}", symbol):
                raise ValueError("請輸入有效股票代號。")
            with st.spinner("下載歷史資料、逐日重建七線並比較策略…"):
                payload = load_history(symbol, "max")
                lines = _lines(payload["candles"])
                result = run_position_backtest(lines, start, end, capital, weights)
                lao = lao_wang_backtest(payload["candles"], start, end, capital)
                selected = lines.loc[str(start):str(end)]
                benchmark = [{"date": day.date().isoformat(), "value": capital * price / selected["收盤價"].iloc[0]}
                             for day, price in selected["收盤價"].items()]
                metrics = pd.DataFrame([
                    {"策略": "七線自訂水位", **performance(result["curve"], capital)},
                    {"策略": "老王既有回測", **performance(lao["curve"], capital)},
                    {"策略": "買入持有", **performance(benchmark, capital)},
                ]).set_index("策略")
                returns = pd.DataFrame({name: pd.Series({p["date"]: (p["value"] / capital - 1) * 100 for p in curve})
                                        for name, curve in [("七線", result["curve"]), ("老王", lao["curve"]), ("買入持有", benchmark)]})
                st.session_state.seven_line_result = dict(symbol=payload["ticker"], result=result,
                    metrics=metrics, returns=returns, lines=selected, weights=weights,
                    start=selected.index[0].date(), end=selected.index[-1].date(), capital=capital)
        except (ValueError, OverflowError) as exc:
            st.error(str(exc))
    saved = st.session_state.get("seven_line_result")
    if not saved:
        st.info("選股票、日期及各位置水位，按「執行七線回測並比較」後顯示結果。")
        return
    st.write(f"已執行：{saved['symbol']}｜{saved['start']}–{saved['end']}｜起始資金 {saved['capital']:,.0f}")
    st.write("本次規則：" + "、".join(f"位置{zone}={weight}%" for zone, weight in enumerate(saved["weights"])))
    st.caption("下方為上次成功執行的結果；修改表單後需重新執行。各策略使用相同日期、資金及行情。老王採現有引擎（首段使用起始日前訊號），七線逐段用前一收盤訊號。")
    st.table(saved["metrics"].style.format("{:,.2f}"))
    st.write("累積報酬率（%）")
    st.line_chart(saved["returns"])
    st.write("收盤價、七線及 3.5 年日均線")
    st.line_chart(saved["lines"][["收盤價", *BANDS, "3.5Y 日均線（882日）"]])
    latest = saved["lines"].iloc[-1]
    st.write(f"期末收盤 {latest['收盤價']:.2f}｜位置 {int(latest['位置'])}｜自訂目標水位 {saved['weights'][int(latest['位置'])]}%")
    with st.expander("查看七線每日位置、加減碼原因與累積報酬"):
        log = saved["result"]["log"]
        st.table(log.style.format(precision=3).set_properties(**{"white-space": "normal", "overflow-wrap": "anywhere"}))
    st.download_button("下載七線回測紀錄 CSV", data=saved["result"]["log"].to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"seven_line_{saved['symbol']}_{saved['start']}_{saved['end']}.csv", mime="text/csv")
