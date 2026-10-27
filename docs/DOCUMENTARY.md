# 中文題材紀錄片使用與驗收

這是可執行的第一階段整合，不是「任意題材皆可免費產出讀檔中等級影片」的承諾。參考創作者的品質目標，不重製其聲音、腳本或畫面。本次提供的參考影片超過工具 32 MiB 傳輸上限，未能實際分析其鏡頭、聲音或故事內容。

## GitHub 網頁操作

1. 合併 PR 後進入 [One Topic Game Documentary](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/one-topic-documentary.yml)，選 **Run workflow**。
2. 輸入「寶可夢紅綠版，推卡車抓夢幻的都市傳說」等題材，選分鐘與旁白。無須自己寫腳本、分鏡、搜尋詞。
3. 預設 `models: read`、`github.token` 呼叫 GitHub Models `openai/gpt-4.1`。帳戶或組織需已開放對應模型。這不是保證每個 repository 的 token 都能使用模型。
4. 如模型權限不足，在 repository **Settings → Secrets and variables → Actions** 安全設定 `LLM_API_KEY`；在 Variables 設定 `LLM_BASE_URL`（HTTPS、含相容 API 基底路徑）與 `LLM_MODEL`。模型必須同時支援圖片輸入、JSON object 與 chat completions。勿在議題、程式碼或聊天貼金鑰。
5. Actions 成功後，Artifacts 內有 `documentary.mp4`、`documentary.srt`、`thumbnail.jpg`、`ATTRIBUTION.md`、`sources.json` 與審核報告。將素材署名與授權連結放入 YouTube 說明。系統不會自動上傳 YouTube。
6. 失敗時仍上傳 JSON。先看 `qa_report.json` 的 `failed_stage`、`blocker.code`、`blocker.detail`，再查看該階段報告。`work/`、原始素材與未通過的 `candidate.mp4` 不會當成成品上傳。

新 workflow 在 PR 分支可能尚不出現在預設分支的 Actions 清單；合併後才可從此入口正常手動執行。此開發機的測試不代表 Actions 已實際執行過。

## 每日與批次

將 `config/topics.json` 設成 1–3 個題材字串，例如：

```json
["寶可夢紅綠版，推卡車抓夢幻的都市傳說", "風之旅人，陌生玩家之間的合作設計"]
```

每天 01:20 UTC（台灣 09:20）循序處理清單；GitHub 排程可能延遲，私人 repository 亦受 Actions 分鐘額度限制。清單會每天重新執行，不是自動刪除的佇列；避免重複產片請更新清單。預設 `[]` 會明確略過產製。任一題被阻擋，整批退出碼為 2，但其餘題仍會執行並保留各自報告。Concurrency 避免同分支同時消耗多個批次資源。

## 流程及具體門檻

| 階段 | 行為與可檢視證據 | 阻擋情形 |
| --- | --- | --- |
| 題材理解 | 模型動態產生繁中／英文題材與查詢，不使用固定翻譯字典 | 模型不可用、格式不合格 |
| 研究 | Bing RSS 只當線索；trafilatura 取至少 3 篇原文，保存 URL、擷取時間、SHA256 | 只有標題、空白頁、來源不可讀 |
| 證據 | 每來源選最多 3 個逐字引句；每項主張至少 2 個不同出版網域，再由另一輪模型檢查支持關係、轉載與矛盾 | 假引句、單一來源、矛盾、無法支持的日期 |
| 原創腳本 | 六章繁體中文、每段 20–180 字、逐段主張 ID；分批支持關係與原創性審核，全篇結構審核 | 無引用、長度不足、重複灌水、敘事不連貫 |
| 素材 | Commons 原始檔與授權中繼資料；明確 CC BY、CC0、Public Domain，保留作者、授權 URL、雜湊 | NC、ND、SA、未知授權、限制註記、缺作者、檔案過大 |
| 旁白 | Edge `zh-TW-YunJheNeural` 詞時間事件；或既有 Kokoro CPU 逐短句實測音長 | 服務／模型不可用、實測不在 600–900 秒或偏離目標 ±15% |
| 畫面 | PySceneDetect 偵測切點，拆成 2–8 秒；每段抽 3 幀，視覺模型檢查遊戲、事件與觀察 | 任一秒缺素材、信心低於 0.9、遊戲／事件不符；不重複已選區間 |
| 渲染 | FFmpeg 兩執行緒、1080p 24fps H.264/AAC、原片靜音、響度處理、繁中 ASS 燒錄、淡入引用框 | 不循環／凍結素材延長片長，不以圖片卡或通用庫存片補位 |
| QA | 完整解碼；尺寸、編碼、片長、字幕時間與讀速；黑畫面、12 秒凍結、3 秒靜音及音量檢查 | 明確原因失敗；僅全部通過後發布 `documentary.mp4` 到成品目錄 |
| 封面 | 從已通過的影片擷取畫面，加中文題材標題，1280×720 | 缺 CJK 字型、影片無法擷取 |

「不同出版網域」本身不證明來源獨立；轉載判斷仍由模型審核，可能誤判。相同模型的第二輪審核不是獨立專家。原文引句存在也不等於主張必然為真。報告明確標記 `automated_quote_and_model_audit; not human_verified`，不得宣稱人工查證。來源最多 12 篇，每篇最多保留 12,000 字元；模型擷取只評估前 6,000 字元，可能漏掉後段更正。主張不足就停止，不假造完整時間線。

視覺模型的 0.9 是自報信心門檻，未校準成實際準確率。三幀抽樣可能漏掉中間錯誤；這不是逐幀證明。Commons 的授權欄位亦可能錯誤，不能代替權利人授權。許多商業遊戲的原始影像／錄影另有權利問題；禁止把公開觀看、YouTube 標準授權、標示「fair use」或素材作者一句話當成任意再利用許可。本版本只自動使用嚴格篩選的 Commons 影片；SA 的衍生授權處理尚未實作，故先排除。Pixabay、Wikimedia 圖片與舊手動素材庫保留在舊流程，不拿它們的通用素材填補遊戲畫面。

## 雲端開發命令

不需在自己的電腦安裝。若使用 Codex 開發機，沿用既有 checkout，不建立 worktree：

```bash
cd /workspace/free-ai-video-generator
python -m venv /workspace/.venvs/game-doc
/workspace/.venvs/game-doc/bin/pip install -r requirements-documentary.txt
/workspace/.venvs/game-doc/bin/python -m pytest -q
/workspace/.venvs/game-doc/bin/python topic_pipeline.py --topic '寶可夢紅綠版，推卡車抓夢幻的都市傳說' --minutes 12
```

系統套件：`ffmpeg`、`ffprobe`、`fonts-noto-cjk`。選 Kokoro 需另外安裝 CPU PyTorch、`kokoro>=0.9.4,<1`、`misaki[zh]>=0.8.2,<1`、soundfile、espeak-ng，並允許 Hugging Face 模型下載。既有 Kokoro 將繁體轉簡體供模型發音，字幕仍用原繁體；它是普通話，不保證台灣口音。逐短句配音可能影響自然度，未實際聆聽驗收前不得稱自然旁白已通過。

每次執行建立新目錄，拒絕沿用既存成品。測試合成影片只是編碼與字幕驗證，不可當遊戲畫面。未通過的素材留在開發機供診斷，不會成為 Actions 的 MP4 成品。

## 實際驗證與目前阻礙

詳見 [VALIDATION.md](VALIDATION.md)。本次真實中文入口停在 `MODEL_NETWORK`；搜尋、Commons 與 Edge TTS 分別得到代理拒絕。沒有真正完成寶可夢研究、腳本、配音或合法遊戲素材下載，也沒有 10–15 分鐘成品。模型／授權／自然旁白與語義匹配的真實品質尚未驗收。

雲端網域草稿已保存，需在環境設定檢閱並儲存、發布後重新測試。搜尋回傳的文章可能需要額外逐一開放其原站網域；錯誤清單會保留 URL。GitHub Actions runner 的連線條件與這台開發機不同，仍須實跑驗證。不要為通過測試而關閉 TLS／憑證驗證。

## 免費與資源限制

- FFmpeg、PySceneDetect、文章擷取、字幕與封面不需付費 API。下載最多 12 支、600 MB，單支 100 MB、20 分鐘、4K 以內；搜尋最多 18 詞，每段最多評估 24 個候選，影片不重用。
- 預設一題最多 180 次模型呼叫，每次最多 4,000 輸出 tokens；GitHub Models 預設至少間隔 7 秒。額度／頻率／輸入上限仍由模型和帳戶決定，可能在完成前就耗盡。每次報告記錄實際 usage，不虛構固定產片成本。
- GitHub Models 免費額度不是每天足量的商用影片服務。HTTP 429／模型額度不足時明確停止；可等額度重置、縮小研究範圍或選較便宜且支援視覺的相容模型。不能保證換個免費模型仍達標。
- Edge TTS 是免費服務存取方案，沒有本專案能保證的 SLA／無限配額。失效可選已保留的 Kokoro CPU；首次需下載模型，普通話自然度與地域口音仍需驗收。
- 完全開源的文字模型與 Qwen 視覺模型可由有 GPU 的遠端服務提供相容 HTTPS 端點，不需使用者本機安裝；一般免費 Actions CPU 不適合即時載入多個 7B／9B 視覺與文字模型。程式目前沒有內建自動部署免費 GPU 服務。
- 最難免費解決的是特定遊戲／事件合法畫面。可行方向是權利清楚的開源遊戲、權利人明確允許的錄製素材或取得正式授權；本版尚未實作自動遊玩錄製與權利人素材庫接入。寶可夢題材不可因為有影片可看就假設可以下載重製。
- 若改用付費模型，實際成本 = 報告中的輸入／輸出用量 × 提供者當期費率，另加任何素材授權與超額 Actions 費用。沒有保證「零成本且每天 15 分鐘」的方案；本次沒有購買任何 API 或素材。

## 後續驗收

先解除網路阻擋並驗證模型權限，再對真實題材執行，逐階段檢視證據與素材。合法素材不足應看到 `LICENSED_GAMEPLAY_MISSING` 或 `LICENSED_RELEVANT_FOOTAGE_MISSING`，而不是低品質影片。只有真實研究、授權素材、自然旁白、畫面匹配及完整 10–15 分鐘輸出皆經驗收後，才能宣稱達到使用者最終目標。
