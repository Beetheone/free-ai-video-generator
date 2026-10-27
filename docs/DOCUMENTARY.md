# 中文題材紀錄片使用與驗收

這是可執行的第一階段整合，不是「任意題材皆可免費產出讀檔中等級影片」的承諾。參考創作者的品質目標，不重製其聲音、腳本或畫面。本次提供的參考影片超過工具 32 MiB 傳輸上限，未能實際分析其鏡頭、聲音或故事內容。

## GitHub 網頁操作

1. 進入 [One Topic Game Documentary](https://github.com/Beetheone/free-ai-video-generator/actions/workflows/one-topic-documentary.yml)，選 **Run workflow**。合併前選分支 `feat/topic-documentary-pipeline`，合併後選 `main`。
2. 輸入「寶可夢紅綠版，推卡車抓夢幻的都市傳說」等題材，選分鐘與旁白。無須自己寫腳本、分鏡、搜尋詞。
3. 先在 repository **Settings → Secrets and variables → Actions** 安全設定 Secret `LLM_API_KEY`。目前 [config/model.json](../config/model.json) 已依使用者選擇設定 `https://api.openai.com/v1` 與 `gpt-4.1-mini`，不必再手填兩個非機密欄位。GPT API 與 ChatGPT 會員分開計費，專案不會替帳戶充值或開通付費服務。若要換提供者／模型，可用 `LLM_BASE_URL`、`LLM_MODEL` 的 Actions Variables 或 Secrets 覆寫；優先序為 Variables、Secrets、專案設定。每次產片只輸入題材，金鑰永遠不寫入設定 JSON、議題、程式碼或聊天。
4. 可選 Gemini 免費額度方案：在 [Google AI Studio](https://aistudio.google.com/apikey) 取得適用的 API key，`LLM_BASE_URL` 設 `https://generativelanguage.googleapis.com/v1beta/openai`，`LLM_MODEL` 可選官方 SDK 目前示例的 `gemini-flash-latest`。需依帳戶／區域確認模型支援、免費資格及當期配額；alias 的實際模型可能改變，本次尚未取得金鑰實測 Gemini。也可選另一相容提供者並設定其端點、模型與金鑰；程式要求明確指定提供者，避免將既有通用 key 自動傳給另一服務。
5. Actions 成功後，Artifacts 內有 `documentary.mp4`、`documentary.srt`、`thumbnail.jpg`、`ATTRIBUTION.md`、`sources.json` 與審核報告。將素材署名與授權連結放入 YouTube 說明。系統不會自動上傳 YouTube。
6. 失敗時仍上傳 JSON。先看 `qa_report.json` 的 `failed_stage`、`blocker.code`、`blocker.detail`，再查看該階段報告。`work/`、原始素材與未通過的 `candidate.mp4` 不會當成成品上傳。

此 repository 的預設分支已有同名 workflow，手動執行時可選功能分支使用新實作；直接選尚未合併的 `main` 仍是舊研究器。功能分支也能透過推送 `config/topics.json` 變更觸發批次。本次已實際在 GitHub Actions 執行測試與寶可夢題材，結果詳見 [VALIDATION.md](VALIDATION.md)，不可把測試工作流程成功當成影片製作成功。

**GitHub Models 已退役。** [GitHub 官方文件](https://github.com/github/docs/blob/main/content/github-models/index.md) 說明，自 **2026-07-30** 起推論 API、模型目錄與 BYOK 已完全停止。程式會拒絕舊端點，回傳 `MODEL_PROVIDER_RETIRED`；新增 GitHub token 或 `models: read` 無法修復。GitHub Actions 執行平台仍可使用，與已退役的模型服務不同。

## 每日與批次

將 `config/topics.json` 設成 1–3 個題材字串，例如：

```json
["寶可夢紅綠版，推卡車抓夢幻的都市傳說", "風之旅人，陌生玩家之間的合作設計"]
```

每天 01:20 UTC（台灣 09:20）循序處理清單；推送 `config/topics.json` 的變更也會觸發一次批次，不限預設分支。GitHub 排程可能延遲，私人 repository 亦受 Actions 分鐘額度限制。清單會每天重新執行，不是自動刪除的佇列；避免重複產片請更新清單。預設 `[]` 會明確略過產製。任一題被阻擋，整批退出碼為 2，但其餘題仍會執行並保留各自報告。收到取消訊號則退出 130，不再繼續下一題。Concurrency 避免同分支同時消耗多個批次資源。

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
/workspace/.venvs/game-doc/bin/python -m documentary.doctor --out output/environment-diagnosis.json
/workspace/.venvs/game-doc/bin/python -m pytest -q
/workspace/.venvs/game-doc/bin/python topic_pipeline.py --topic '寶可夢紅綠版，推卡車抓夢幻的都市傳說' --minutes 12
```

系統套件：`ffmpeg`、`ffprobe`、`fonts-noto-cjk`。選 Kokoro 需另外安裝 CPU PyTorch、`kokoro>=0.9.4,<1`、`misaki[zh]>=0.8.2,<1`、soundfile、espeak-ng，並允許 Hugging Face 模型下載。既有 Kokoro 將繁體轉簡體供模型發音，字幕仍用原繁體；它是普通話，不保證台灣口音。逐短句配音可能影響自然度，未實際聆聽驗收前不得稱自然旁白已通過。

每次執行建立新目錄，拒絕沿用既存成品。測試合成影片只是編碼與字幕驗證，不可當遊戲畫面。未通過的素材留在開發機供診斷，不會成為 Actions 的 MP4 成品。

`doctor` 不發送網路請求、不輸出金鑰值，只檢查套件、工具、字型、憑證變數是否存在，以及可用的啟動網路政策快照。它不證明目前網路政策、模型權限或外部服務已就緒；實際執行仍是必要驗收。缺前置條件退出 2，通過也只代表 `PRECHECKS_PASS_SERVICE_TESTS_REQUIRED`。Actions 會保存診斷 JSON，並在 run summary 顯示實際製作結果。

如推論出現模糊的 HTTP 429／權限錯誤，額外診斷只會讀取模型目錄 `GET /models`，不生成內容、不更改帳務。模型目錄可讀或模型存在都不能證明有可用推論額度。明確的 `insufficient_quota`、`invalid_api_key` 等錯誤不會觸發更多探測或盲目重試。HTTP 錯誤只保留允許清單中的錯誤碼、參數及 media type，不輸出 API key 或服務商原始錯誤訊息。

`qa_report.json` 在每個階段與逐段配音／匹配後寫入 `current_stage`、`completed_stages`、`progress`、`updated_at`。失敗時附 `next_actions`。SIGTERM／Ctrl-C 會保存 `CANCELLED`；無法攔截的強制 SIGKILL 只能留下最後一次 checkpoint。未經重新審核的半成品不會自動恢復或當成成片。

Edge 配音先解碼為 PCM 再測量片長，避免 MP3 容器補樣影響時間線。各場景只編碼畫面，全部 PCM 旁白串接後才統一編碼一次 AAC；字幕依同一實測時間線排列。QA 也比較各影音 stream 長度及完整解碼的音訊樣本長度，避免容器片長正常卻實際旁白提前結束或逐段偏移。

## 實際驗證與目前阻礙

詳見 [VALIDATION.md](VALIDATION.md)。Codex 開發機的真實中文入口曾停在 `MODEL_NETWORK`；搜尋、Commons 與 Edge TTS 分別得到代理拒絕。另在 GitHub runner 實跑後，確認模型回應不是有效 JSON API envelope，並查到官方服務退役資訊，已移除該預設。沒有真正完成寶可夢研究、腳本、配音或合法遊戲素材下載，也沒有 10–15 分鐘成品。新提供者仍需安全設定金鑰、端點與模型，模型／授權／自然旁白與語義匹配的真實品質尚未驗收。

雲端網域草稿已保存，需在環境設定檢閱並儲存、發布後重新測試。搜尋回傳的文章可能需要額外逐一開放其原站網域；錯誤清單會保留 URL。GitHub Actions runner 的連線條件與這台開發機不同，仍須實跑驗證。不要為通過測試而關閉 TLS／憑證驗證。

## 免費與資源限制

- FFmpeg、PySceneDetect、文章擷取、字幕與封面不需付費 API。下載最多 12 支、600 MB，單支 100 MB、20 分鐘、4K 以內；搜尋最多 18 詞，每段最多評估 24 個候選，影片不重用。
- 預設一題最多 180 次模型呼叫，每次最多 4,000 輸出 tokens，預設至少間隔 7 秒。額度／頻率／輸入上限仍由模型和帳戶決定，可能在完成前就耗盡。每次報告記錄實際 usage；若提供者未回傳完整用量，另記 `model_usage_unavailable_calls`，不把未知用量當作零成本。
- 免費額度不是每天足量的商用影片服務，GitHub Models 更已退役，不能作為免費替代。Gemini 等方案需金鑰及帳戶資格；HTTP 429／模型額度不足時明確停止，可等額度重置或選另一可用模型。不能保證更換免費模型仍達標。程式不會為追求成功而自動開啟付費方案。
- Edge TTS 是免費服務存取方案，沒有本專案能保證的 SLA／無限配額。失效可選已保留的 Kokoro CPU；首次需下載模型，普通話自然度與地域口音仍需驗收。
- 完全開源的文字模型與 Qwen 視覺模型可由有 GPU 的遠端服務提供相容 HTTPS 端點，不需使用者本機安裝；一般免費 Actions CPU 不適合即時載入多個 7B／9B 視覺與文字模型。程式目前沒有內建自動部署免費 GPU 服務。
- 最難免費解決的是特定遊戲／事件合法畫面。可行方向是權利清楚的開源遊戲、權利人明確允許的錄製素材或取得正式授權；本版尚未實作自動遊玩錄製與權利人素材庫接入。寶可夢題材不可因為有影片可看就假設可以下載重製。
- 若改用付費模型，實際成本 = 報告中的輸入／輸出用量 × 提供者當期費率，另加任何素材授權與超額 Actions 費用。沒有保證「零成本且每天 15 分鐘」的方案；本次沒有購買任何 API 或素材。

## 後續驗收

先解除網路阻擋並驗證模型權限，再對真實題材執行，逐階段檢視證據與素材。合法素材不足應看到 `LICENSED_GAMEPLAY_MISSING` 或 `LICENSED_RELEVANT_FOOTAGE_MISSING`，而不是低品質影片。只有真實研究、授權素材、自然旁白、畫面匹配及完整 10–15 分鐘輸出皆經驗收後，才能宣稱達到使用者最終目標。
