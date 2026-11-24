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
