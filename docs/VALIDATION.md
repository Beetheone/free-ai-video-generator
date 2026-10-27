# 驗證紀錄

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

完成驗證後已將 `config/topics.json` 恢復 `[]`，避免每日反覆執行測試題材。PR API 仍受這台 Codex 環境尚未套用的網路政策阻擋；完整 PR 描述已保存在 [PR_DESCRIPTION.md](PR_DESCRIPTION.md)。
