# 驗證紀錄

## 改用 Gemini 後的環境實測（2026-10-28）

已依使用者最新選擇，將專案預設改成 Gemini 官方 OpenAI 相容端點與 `gemini-flash-latest`，並新增獨立服務檢查；不消耗 10–15 分鐘產片所需的大量推論。

[首次真實服務檢查，f3029bc](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40609328086)，44 秒，結果：

| 檢查 | 實際結果 |
| --- | --- |
| 模型 | `MODEL_CREDENTIAL_REQUIRED`；GitHub runner 沒有讀到 `LLM_API_KEY`，未發送推論 |
| 搜尋 | **PASS**，真實 Bing RSS 回傳 10 筆；沒有把搜尋摘要當已查證證據 |
| Commons | **PASS**，真實 API 站台中繼資料可讀；未宣稱取得合法遊戲素材 |
| 台灣中文配音 | `TTS_UNAVAILABLE`、`WSServerHandshakeError`；沒有產生可驗收旁白 |

後續修正接受常見 Gemini Secret 名稱：`LLM_API_KEY` → `GEMINI_API_KEY` → `GOOGLE_API_KEY`。亦查閱 [Edge TTS 官方 releases](https://github.com/rany2/edge-tts/releases)，確認 7.3.0 新增 Sec-MS-GEC v2、7.3.1 修正日期解析；將原來固定的 7.2.7 升級為 **7.3.1**，再實測，不使用停用 TLS 或自製憑證繞過方式。升級後本機 **88 passed in 15.05s**、`pip check`、Actionlint 與 `git diff --check` 通過。新增測試使用明示 fake API，驗證錯誤提供者在送出金鑰前停止、實際 JPEG 的編碼與回應門檻、逐服務獨立保存阻礙；這些測試不代表真實模型通過。

Codex 雲端仍是舊 runtime：無模型金鑰、沒有 Gemini／研究／配音網域權限。已保存 Gemini 非機密設定建議與新版啟動說明；既有金鑰需求的目的地本來就是 Gemini，不必另加重複項目。草稿保存不是套用或發布，也與 GitHub repository Secrets 分開。

執行日期：2026-10-28（台灣）。起始版本：`14c153c48fcaab392fe616cbddff52e5c54bf264`。開發機：Linux、Python 3.12.14、FFmpeg／FFprobe、Noto CJK，5 個可見 CPU，32 GiB 可用記憶體。Actions 設定為 Python 3.11、CPU 兩執行緒。以下保留第一階段紀錄，後續 GitHub runner 實跑結果見文末。

## 已通過

```text
/workspace/.venvs/game-doc/bin/pip install -r requirements-documentary.txt
  安裝成功；重跑已滿足現有版本，沒有改動原 requirements.txt。
/workspace/.venvs/game-doc/bin/python -m pytest -q
  40 passed in 4.79s
/workspace/.venvs/game-doc/bin/python -m pip check
  No broken requirements found.
/tmp/actionlint/actionlint .github/workflows/one-topic-documentary.yml .github/workflows/test-documentary.yml .github/workflows/game-agent-factory.yml
  exit 0
git diff --check
  exit 0
```

Actionlint v1.7.12 來自官方 GitHub release，下載 archive 與官方 checksums，核對 SHA256 後才執行；沒有關閉 TLS 或忽略驗證。

測試具體覆蓋：

- 實際由 FFmpeg 產生紅／藍切換測試影片，PySceneDetect 找到約第 4 秒切點。
- 實際擷取三張候選影格；**視覺模型用明示 fake** 測試接受／拒絕與素材區間不可重複，不代表模型已正確辨識真實遊戲。
- 實際 FFmpeg 渲染約 3 秒 **testsrc 合成動態圖樣＋440 Hz 測試音**，不是 AI 配音，也不是遊戲素材。輸出 1920×1080 H.264/AAC，燒錄繁體中文 ASS、來源框淡入，寫出 SRT，生成 1280×720 封面；完整解碼、字幕與音量門檻通過。封面亦實際開啟檢查中文字形。
- 同一短片仍無法通過正式 600–900 秒門檻，防止拿短測試片假冒長片。
- 實際黑畫面＋靜音影片未通過品質門檻。
- 精確引句、不同出版網域、語言子站不算獨立來源、轉載審核拒絕、缺研究原文、無腳本引句、重複腳本、NC／ND／SA／不明授權、授權文字與 URL 矛盾、無關畫面、時間戳不合法、缺模型金鑰、批次阻擋、既存成品不可沿用等測試通過。
- 研究與腳本門檻測試使用明確標示的合成原文／模型回應；沒有把 fixture 敘事寫成實際研究報告。控制器缺合法素材時，證明不會呼叫配音或渲染。

## 真實服務結果

實際執行：

```bash
/workspace/.venvs/game-doc/bin/python topic_pipeline.py \
  --topic '寶可夢紅綠版，推卡車抓夢幻的都市傳說' --minutes 12
```

退出 2。報告 `status=BLOCKED`、`failed_stage=bilingual_topic_expansion`、`blocker.code=MODEL_NETWORK`、`Model endpoint unavailable (ProxyError)`，沒有輸出紀錄片 MP4。當次所有下游真實階段均 **未執行**，不能宣稱遊戲研究／旁白／語義匹配通過。

另外執行實際服務連線與配音測試：

| 服務 | 觀測 |
| --- | --- |
| Bing RSS 搜尋 | `www.bing.com: ProxyError` |
| Commons API | `commons.wikimedia.org: ProxyError` |
| GitHub Models | `MODEL_NETWORK`；憑證是否有模型權限尚無法判定 |
| Edge 台灣中文配音 | `TTS_UNAVAILABLE`、`ClientHttpProxyError` |
| Git repository HTTPS read | `git ls-remote origin HEAD` 成功，與起始 HEAD 相符 |
| GitHub API | `gh api user` 與 repo API 都 `Forbidden`；不能據此推論要新增 GitHub token |

執行時 runtime 的 `allowed_hosts=[]`、package-manager preset、`state=enforced`；新增網域僅存入 editable draft，未套用／發布。具體阻礙是目前網路政策，不是假定沒有金鑰；沒有印出或搬移任何憑證。

## 未驗證與限制

真實 10–15 分鐘影片、自然度與台灣口音、實際遊戲視覺辨識、可信的寶可夢故事、合法寶可夢畫面及成本尚未驗收。沒有測試 Kokoro 模型下載／合成，也沒有將一般股票片、文字卡、合成測試片或參考影片當成製作成果。

先檢閱／儲存並發布雲端網域設定，重新測試各服務；再確認現有模型認證權限或安全配置另一相容提供者。若後續找不到合法且相符的素材，正確驗收結果應是明確阻擋與缺口報告，不是 MP4。

## 追加驗證：同步、中斷與真正的 GitHub runner

新增具體測試後，本機 **65 tests passed in 15.23s**。其中包含：

- 12 段交替 440／880 Hz、每段 1.113 秒的實際音訊渲染；解碼波形做 FFT，逐一確認每個預期切點前後 100 ms 的聲音頻率。這是同步標記，不是 AI 配音。
- 測試曾發現逐段 AAC 串接的補樣累積：容器顯示約 13.389 秒，實際解碼 PCM 約 13.824 秒，而預期為 13.356 秒。修正為 PCM 先串接、整片只編碼一次 AAC 後，逐切點測試通過；修正後容器約 13.368 秒，完整解碼與影音長度 QA 通過。
- 旁白僅 1 秒、畫面 4 秒的實際影片，現在會被 QA 拒絕，避免容器總長正常卻無完整旁白。
- 真正啟動子行程並送出 SIGTERM，驗證退出 130、保存 `CANCELLED` 和當下階段，且無成品 MP4；另驗證配音中斷時保留已完成段數。
- 原文標點與中英混合空格保留；相同全文的不同網域轉載不計兩份證據；不存在的日期被拒絕。
- 模型 fixture 測試驗證缺失／null usage 計數不會誤拒合法內容，只有完整 JSON fence 可剝除，任意文字中的 JSON 不會被當成有效回應。這些 fixture 不代表真實模型內容已成功。

已在 GitHub runner 實際執行：

| 執行 | 已觀察結果 |
| --- | --- |
| [Documentary tests，17476a8](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40596644343) | **Success**，Python 3.11，56 項測試所在的工作流程完成，總時間約 1 分 16 秒 |
| [寶可夢題材，17476a8](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40596644284) | **Failure**、退出 2，保留診斷 artifact；公開頁面無詳細日誌 |
| [寶可夢題材，d04dd95](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40597089629) | 公開註記確認 `bilingual_topic_expansion: MODEL_SCHEMA`，沒有 MP4；這是 GitHub runner 的模型回應問題，與 Codex 開發機的代理阻擋不同 |

這些結果證明實際 Actions 安裝／測試可運作，以及真實題材會明確阻擋；尚未證明研究、配音或成品完成。新增診斷與解析修正後會針對已發現的原因重試，不把 HTTP 200 當作有效內容。開發機的 GitHub PR API 仍受既有網路政策阻擋。

## 確認模型服務退役與移除錯誤預設

- [Documentary tests，2e8a8f8](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40597510462)：**Success**，65 項測試所在工作流程完成，約 56 秒。
- [寶可夢題材，2e8a8f8](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40597510479)：公開註記明確顯示 `Model HTTP 200 response is not a JSON envelope`，並非有效內容。沒有 MP4。
- 接著讀取 [GitHub 官方 github/docs 原始文件](https://github.com/github/docs/blob/main/content/github-models/index.md)，確認其原文：`As of July 30, 2026 ... fully ... retired`，且 `inference API ... no longer available to any customer`。原先選用該服務作為預設是錯誤設定，已移除。
- 現在必須明確設定 `LLM_BASE_URL`、`LLM_MODEL` 及對應提供者的 `LLM_API_KEY`；不再把 GitHub token 當作其他提供者的金鑰，也不會向退役服務反覆索取新 token。官方 Google SDK README 的現行示例包含 `gemini-flash-latest`，可作為評估免費額度方案的起點，但尚未取得金鑰或實測其完整流程。

HTTP 200、有效 JSON、模型輸出 schema、主張證據、合法素材及影片品質是不同的驗收門檻，沒有任何一項可代替其他項目。更新金鑰需求並不代表金鑰已配置，保存環境草稿也不代表它已套用或發布。

移除退役預設與新增提供者安全設定檢查後，本機最終檢查為 **70 passed in 15.02s**，Actionlint 與 `git diff --check` 亦通過。新增測試證明即使只有 GitHub token，也不會自動向另一家模型服務傳送它；設定缺少端點／模型名稱時亦不會傳送通用 API key。

[最終題材前置檢查，106d42e](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40598629461) 的公開註記實際確認三項設定都缺少：`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。退出 2，沒有發送推論請求或製作影片。這個結果是設定不足的明確阻擋，不是成功產片；也不是要求新增 GitHub token。

[最終 Documentary tests，106d42e](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40598629632)：**Success**，Python 3.11，70 項測試所在工作流程完成，約 56 秒。這與本機 70 項測試結果一致，仍不代表真實研究、模型或影片產製完成。

完成驗證後已將 `config/topics.json` 恢復 `[]`，避免每日反覆執行測試題材。PR API 仍受這台 Codex 環境尚未套用的網路政策阻擋；完整 PR 描述已保存在 [PR_DESCRIPTION.md](PR_DESCRIPTION.md)。

## 使用者設定 GPT 金鑰後的實跑

| 執行 | 真實結果 |
| --- | --- |
| [bf62acb：首次檢查使用者設定](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40602841674) | `LLM_API_KEY` 已被讀取，仍缺端點／模型值；沒有要求重新提供金鑰 |
| [ade8bcd：使用專案 GPT 設定](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40603830048) | 已通過前置檢查，第一個實際 API 請求回傳 HTTP 429 |
| [4f5654a：安全解析 429](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40604393457) | 公開註記明確確認 `MODEL_UNAVAILABLE`、`HTTP 429`、`code=insufficient_quota`、`media_type=application/json`。已停止推論，未進入研究／腳本／素材／配音／渲染 |
| [4f5654a：82 項測試](https://github.com/Beetheone/free-ai-video-generator/actions/runs/40604393511) | 真正 Python 3.11 GitHub runner **Success**，約 54 秒；本機 **82 passed in 15.55s** |

`config/model.json` 明確選用 OpenAI `gpt-4.1-mini`，讓使用者只需設定金鑰；Variables／Secrets 仍可覆寫非機密端點及模型。新增安全錯誤分類區分 API 額度、頻率、金鑰和參數，原始錯誤訊息及金鑰不會寫入報告。已知 `insufficient_quota` 不觸發額外模型目錄探測或生成重試。

目前需使用者在 OpenAI API 帳務頁確認金鑰所屬帳戶／專案有可用 API 餘額及額度。ChatGPT 訂閱與 API 帳務分開；程式不能替使用者充值或變更帳務。付費並非唯一選項，也可改用有實際可用免費額度的相容提供者，但此處沒有宣稱替代方案已通過完整影片驗收。此次驗證後再次清空題材清單，避免明知額度不足仍持續每日執行。

雲端草稿已增加 `api.openai.com` 網域及更新非機密設定建議。既有個人 `LLM_API_KEY` 需求仍綁定較早的 Gemini 目的地；設定工具拒絕直接改變已有綁定，因此該金鑰目的地沒有被自動改寫或複製，若要在 Codex 本機使用 OpenAI，需於環境設定編輯既有需求為 `api.openai.com`。這與已成功讀到金鑰的 GitHub Actions 設定不同，不會修復目前的 API 額度問題。
