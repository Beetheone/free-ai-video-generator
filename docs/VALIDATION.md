# 驗證紀錄

## 本次驗收：中文題目到研究包

2026-10-28，版本 `014c582`，題目：「寶可夢紅綠版，推卡車抓夢幻的都市傳說」。

[真實 GitHub Actions 執行](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40678067902) **Success，2 分 5 秒**，結果為 `RESEARCH_READY`。這是研究階段成功，並非完整腳本、人工查證或影片完成。

| 項目 | 真實結果 |
| --- | --- |
| 中英文查詢 | 由 Gemini 依題目生成，未要求使用者寫搜尋詞 |
| 來源本文 | 12 篇擷取成功，其中 6 篇選出相關逐字引句；其餘未當成支持證據 |
| 候選／保留主張 | 5 項候選，5 項通過本次引用、兩個出版者、日期及模型語義審核；本次排除 0 項 |
| 補查 | 本次首輪已過門檻，未啟用第二輪；補查路徑在較早真實執行及明示合成測試驗證 |
| 模型使用量 | 14 次呼叫，38,877 輸入 tokens、1,459 輸出 tokens；沒有缺失 usage 的呼叫 |
| 遊戲畫面 | 真實 Commons API 檢查 8 個條目，0 個符合目前支援條件；8 個都是 `UNSUPPORTED_VIDEO_FORMAT`，未下載或確認畫面相關性 |
| 成果 | `topic-research-40678067902` artifact，114 KB；包含研究、證據、進度與素材缺口報告，保留 7 天 |
| 未執行 | 原創長腳本、完整配音、實際遊戲影格匹配、紀錄片 MP4 與正式長片 QA |

研究包提供 `PROGRESS.md`、`RESEARCH.md`、`research.json`、`research_excerpts.json`、`evidence.json`、`qa_report.json` 及獨立的 `FOOTAGE_GAPS.md`。原文字元位置及引用由程式核對；模型不能自己抄寫或改造引句。`SCRIPT.md` 只在腳本全數審核完成時產生，此次沒有該檔案。

公開 Actions 註記已核對上述狀態、數量、來源標題及用量；這台 Codex 的 GitHub API 網路仍受限制，沒有下載需登入的 artifact，也沒有冒充人工逐篇核讀或聆聽驗收。自動審核並不保證事實正確；本次讀到百科、部落格、第三方影片摘要與重複存檔頁面，來源權威性及轉載溯源仍需加強，不能將不同網域直接等同獨立採訪。原文雜湊、出版者正規化及第二次模型審核可拒絕部分重複／依賴來源，尚不能保證辨認所有轉載。

Commons 回傳條目的授權標示包括 CC0、CC BY、Public Domain 與 CC BY-SA，但本次直接排除原因是非支援影片格式，不能據此宣稱都是非法授權或全網沒有合法畫面。當前只支援明確 CC BY、CC0、Public Domain；其他合法條款未整合，也可能因大小、作者或來源欄位而未採用。素材中繼資料候選不等於取得遊戲內容全部權利。

## 程式與相依套件驗證

- 本機 Python 3.12.14：**115 passed in 17.00s**；`pip check` 無相依衝突。
- [同版本 Python 3.11 GitHub CI](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40678067612)：**Success，1 分 2 秒**。
- Actionlint v1.7.12 與 `git diff --check` 通過；Actionlint 取自官方 release，已核對官方 SHA256。
- DDGS 9.16.1、rank-bm25 0.2.2、Wikipedia-API 0.8.1、pySBD 0.3.4 已安裝、核對 GitHub 授權與依賴。Wikipedia-API 最新版的 Click 約束與影片工具衝突，因此採用只依賴 requests 的成熟版本。詳見 [第三方評估](THIRD_PARTY.md)。
- Kokoro／Misaki 中文前端、spaCy 與 pySBD 可共同載入；這項依賴檢查不是再次合成語音。

測試使用真正 FFmpeg／PySceneDetect 處理合成影像與音訊，驗證 1080p 編碼、繁中字幕、封面、切鏡、完整解碼、黑畫面／靜音拒絕，以及 12 段交替音頻的逐切點音畫同步。曾發現逐段 AAC 串接造成解碼補樣累積，已改成 PCM 先串接、整片只編碼一次 AAC；逐切點 FFT 檢查通過。另驗證真正子行程 SIGTERM 保存中斷狀態、無正式 MP4。

研究測試涵蓋晚於原先截斷位置的 BM25 檢索、中英文逐字 offset、未知引句 ID、格式修復、排除個別不合格主張後仍需保留至少 4 項且逐項通過全部原有門檻、日期正規化、偏題腳本拒絕，以及研究階段不呼叫配音／渲染。資料不足或缺素材仍必須阻擋。來源與模型 fixture 明確標成合成，測試圖樣不是遊戲畫面，音頻標記不是 AI 旁白；這 115 項測試不等於長片驗收。

## 已驗證的模型與短句旁白

| 真實服務執行 | 結果 |
| --- | --- |
| [Gemini 文字＋圖片](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40609620530) | 使用者覆寫的 `gemini-3.5-flash-lite` 正確辨識紅／藍測試圖並回覆繁中輸入；1,171 輸入／35 輸出 tokens。搜尋回傳 10 筆真實 RSS，Commons API 亦可讀。不是實際遊戲辨識驗收 |
| [Kokoro CPU 真正合成](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40611170577) | 2 分 12 秒，`hexgrad/Kokoro-82M-v1.1-zh`、`zf_094` 產出 9.625 秒 WAV 與 2 段繁中字幕；完整解碼、時間與讀速檢查通過。458 KB artifact 可聆聽；自然度、台灣口音與長稿節奏尚未驗收 |
| Edge TTS 7.3.1 | 升級官方新握手支援後仍 `NoAudioReceived`，不宣稱可用；Actions 正式預設改用已實測的 Kokoro CPU，保留 Edge 選項 |

本機 CPU 語音套件真正安裝成功：torch 2.14.1+cpu、kokoro／misaki 0.9.4、transformers 4.57.6、spaCy 3.8.18、spacy-curated-transformers 0.3.1；無 CUDA 執行依賴。GHA 安裝 espeak-ng 後真實合成成功；本機僅驗證依賴及中文前端載入，沒有在網路被擋的環境假稱再次下載模型／配音。

## 先前真實失敗與修正依據

| 版本／執行 | 觀察與修正 |
| --- | --- |
| [0ac78d2](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40660659670) | 寶可夢 12 篇本文、0 篇相關引句、0 項候選。混入棒球、超市、芝加哥頁面，原先只依序讀 Bing 結果不可靠 |
| [b46981a](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40662875993) | 加入多引擎／BM25 後仍不足；寶可夢 15 篇／1 篇相關，DOOM 18 篇／2 篇相關，各 0 候選。免費搜尋不保證可靠 |
| [db91d09](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40665571792) | 沿真實百科引用找到更相關來源，但模型抄錄原文出現逐字／長度問題；之後改為由程式依原文 offset 取引句、模型只選 ID |
| [c85200e](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40668739720) | 寶可夢 18 篇／9 篇相關、2 項候選；DOOM 有無效選取。新增有界格式修復與未審閱來源狀態 |
| [4814982](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40671454778) | 寶可夢 18 篇／12 篇相關、DOOM 15 篇／13 篇相關，均只 3 項候選；仍停止，沒有強迫湊故事 |
| [0ed257f](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40673316910) | 要求分開有證據的原子事實後，寶可夢產生 6 候選，但 C5 缺第二出版者；DOOM 仍僅 3 候選。改為個別排除不合格項，保留項仍須全數審核且至少 4 項 |

這些失敗都沒有當成合格腳本或影片。最新研究成功僅對上列單一真實題目及該次服務回應成立，尚未證明任意遊戲題材都會成功。

## 操作與尚未驗收

見 [白話使用說明](USER_STAGE.md)。`goal=research` 到來源／證據包；`goal=script` 接著嘗試原創長稿；`goal=movie` 嘗試完整影片。只有完整成片 QA 通過才會標示 `COMPLETE_AUTOMATED_CHECKS`。腳本／研究成功皆不等於 MP4。

仍缺少真實長稿與 10–15 分鐘配音實測、可用且相關的授權遊戲錄影、實際遊戲 VLM 影格匹配與長片品質驗收。腳本長度目前按字數估算，正式流程必須配音後量測片長，超出 600–900 秒／目標容差即停止，不能靠拉長、重播或文字卡補足。來源有下載與本文保留上限、雜湊與截斷標記；不得宣稱看過未擷取內容。

Gemini Actions 金鑰已可用，不要求重填。免費帳戶資格、API／Actions 額度及素材權利各有條件；本次使用量可供估算，但沒有宣稱每天長片零成本。較早 OpenAI 測試的 insufficient_quota 已被使用者改用 Gemini，並非目前要再次充值或更換金鑰的理由。

測試後清空 `config/topics.json` 與 `config/research-topics.json`，避免定時或推送重複消耗額度；空清單的綠燈只代表略過，不算真實題目驗收。排程合併後為台灣 09:20，最多三題批次。既有 render.py、Kokoro、Piper、Pixabay、Wikimedia 保留。

## 雲端設定與 PR

目前 Codex runtime 仍是 revision 1、`allowed_hosts=[]`、無本機模型金鑰；GitHub Actions 是另一環境。Git HTTPS 推送正常，但 GitHub API 被現行網路政策拒絕，不能下載需登入的 artifact 或建立 PR。沒有要求新 token，也沒有以工作流程代理 API 繞過政策。

已保存可重用的安裝／啟動與 Gemini 網域設定草稿。保存草稿不代表套用、發布或填入憑證；若要這台 Codex 直接呼叫相關服務，需要在環境設定檢閱、儲存並發布，再重測實際權限。準備好的 [PR 描述](PR_DESCRIPTION.md) 和 [建立 PR 入口](https://github.com/Beetheone/free-ai-video-generator/pull/new/feat/topic-documentary-pipeline) 可供審閱；尚未建立 PR。
