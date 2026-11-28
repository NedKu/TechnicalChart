# 老王技術分析戰法診斷器

Streamlit 在 Python 端使用 `yfinance` 取得預設一年還原日 K（可選 1、2、3、5 年），原有 HTML/JavaScript
負責圖表、技術指標與 SOP 顯示。行情失敗時會顯示錯誤，不使用假資料。

## 本機執行

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

瀏覽器開啟 Streamlit 顯示的本機網址，從左側選擇觀察標的或輸入代號。

## Streamlit Community Cloud

將 `streamlit_app.py`、`requirements.txt` 與 `v0/` 一起提交至 GitHub repository。
在 Streamlit Community Cloud 建立 app，選擇該 repository、branch，並將入口檔設為
`streamlit_app.py`。主機須能連線 Yahoo Finance；若資料來源無回應，頁面會顯示錯誤。

## 七線回歸位置回測

原有老王判斷與回測保留，統一於「老王與七線策略回測比較」區塊。
回測標的沿用側邊欄，僅需輸入一組日期與共同起始資金，以及位置0–7的目標持股比例。按「同時回測老王與七線」後比較七線、老王既有回測與買入持有的累積報酬、年化報酬、最大回撤；兩套逐日紀錄均可展開或下載。

七線公式依據個人專案 `NedKu/STOCK_PER_PBR_Trend` 的
`src/stock_per_pbr_trend/analysis.py`（版本 `c1af2867db4573fca7ae136ce2f007fbee92a810`）：
182週線性回歸預測線，加上最近182週預測偏差樣本標準差的常態分位線
0.002、0.025、0.125、0.875、0.975、0.999。這不是固定±1/2/3σ，也不是均線；882日均線另外畫出。
每日用截至該日的部分週資料重建，僅使用當時已知資料，完整暖機後才開始回測。
價格等於界線時歸較高位置。每次執行以當次 yfinance 還原資料重播，並非當年保存的網站資料快照。

本模型是可調水位的研究範例，預設位置0–7水位為100/90/80/60/40/20/10/0%；
**不是排程文件的CI四批、Guard、景氣燈號或神龍策略完整重現**。
每日以前一收盤訊號按目標水位作理想化收盤再平衡，零股、現金零利息，未計費稅與滑價。
比較使用同一行情、日期、資金；老王保留既有首段採開始日前訊號的行為，七線使用開始日收盤訊號。
舊App的線值使用下載當時的歷史資料；早期不足182週時原App採縮短視窗，本回測則拒絕不足暖機的期間。

七線測試（開發環境需另外安裝pytest）：`python -m pytest -q tests/test_seven_line.py`。
