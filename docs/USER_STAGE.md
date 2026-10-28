# 現在輸入一個題目，可以做到哪裡？

這一階段已用真實寶可夢題目驗收「研究與證據包」：12 篇本文、6 篇選出相關引句、5 項主張通過本次自動審核，約 2 分鐘完成。輸入一段中文遊戲題目，程式自行產生中英文查詢、搜尋與讀取文章、選取原文證據並比對不同出版者。證據不足會再補查一輪；仍不足就停止並解釋缺口。腳本入口也已接上，但尚未通過真實題目的完整長稿驗收，不能把已找到文章當成內容已證實。

## 可下載的內容

| 檔案 | 白話用途 |
| --- | --- |
| `PROGRESS.md` | 這次實際做到哪裡、在哪一步停止、現在拿得到什麼 |
| `RESEARCH.md` | 通過本次自動審核的白話研究筆記、時間與來源連結；不等於人工查證 |
| `SCRIPT.md` | 通過腳本審核才會出現的原創繁體中文稿，含逐段主張引用 |
| `evidence.json` | 通過自動審核的主張、逐字引句、來源與可支持的時間線 |
| `research.json` | 真正讀到的文章、擷取日期與雜湊；不代表每篇都相關或正確 |
| `research_excerpts.json` | 模型選取並由程式核對的相關逐字引句 |
| `research_gap_plan.json` | 需要補查時，自動生成的新查詢 |
| `FOOTAGE_GAPS.md` | 研究／腳本階段的 Commons 授權候選檢查與尚缺的畫面條件 |
| `qa_report.json` | 程式可讀的成功階段、失敗原因與用量 |

找到授權中繼資料候選，不等於已取得正確遊戲畫面；還要下載、辨識影格並覆蓋整段旁白。研究與腳本成功也不等於影片完成。

腳本篇幅目前以字數估算，研究階段沒有驗證完整旁白是否真正在 10–15 分鐘內；正式產片必須配音後量測片長。來源本文有下載／保留長度上限，報告保留雜湊與截斷標記，不能聲稱讀過未擷取的內容。

## 怎麼輸入

目前功能在 `feat/topic-documentary-pipeline` 分支。

1. 開啟 [One Topic Game Documentary](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/one-topic-documentary.yml)，按 Run workflow，選上述分支。
2. 輸入中文題目。`goal=research` 只到證據包；`script` 繼續嘗試成稿，通過審核才提供腳本；`movie` 嘗試完整影片，缺素材或不過品質門檻會停止。
3. 執行結束後下載 Artifacts，先讀 `PROGRESS.md`。

另有輕量的 [One Topic Research and Script](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/one-topic-research.yml)，預設 `research` 先驗收研究包，也可選 `script` 繼續嘗試成稿；不安裝配音模型、不渲染影片。新 workflow 合併至預設分支後可手動執行；合併前推送 `config/research-topics.json` 可觸發驗證。使用者不用撰寫搜尋詞、腳本或分鏡。

## 需要什麼

- GitHub Actions 上可用的 Gemini 金鑰；此專案已實測使用者設定的 `gemini-3.5-flash-lite`，不需要重新提供金鑰。
- 足以支持故事的可讀來源，以及當期 API／Actions 額度。免費資格與額度由帳戶及服務決定。
- 若要 MP4，還需要權利清楚、與故事相符且時間足夠的遊戲影片，以及旁白與成品品質檢查。Commons 未找到候選時會列出缺口，不會假裝全網都沒有素材。

GitHub 的開源工具已補上多引擎搜尋、長文段落檢索、鏡頭分析、旁白與渲染。程式碼授權與遊戲錄影的使用權需分別確認；下載一個 GitHub 專案無法自動取得商業遊戲畫面的權利。

## 已有實測與未完成項目

[寶可夢研究包真實成功紀錄](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40678067902) 的 Artifacts 提供 `topic-research-40678067902`，保留 7 天。這次沒有完整腳本或 MP4；畫面 API 的 8 個條目均非支援影片格式，未取得可用遊戲錄影。來源權威性與轉載溯源仍需加強，不能把自動審核當人工查證。

Gemini 真實文字／圖片推論、搜尋與 Commons API、Kokoro CPU 的 9.625 秒普通話音訊與字幕已通過個別服務測試。真正的 10–15 分鐘遊戲紀錄片、自然度與台灣口音仍未驗收。最新研究／腳本實跑結果與限制記在 [VALIDATION.md](VALIDATION.md)，不能把合成測試或研究階段成功當成完整成片。
