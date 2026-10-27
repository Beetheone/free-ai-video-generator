# 驗證紀錄

執行日期：2026-10-28（台灣）。起始版本：`14c153c48fcaab392fe616cbddff52e5c54bf264`。開發機：Linux、Python 3.12.14、FFmpeg／FFprobe、Noto CJK，5 個可見 CPU，32 GiB 可用記憶體。Actions 設定為 Python 3.11、CPU 兩執行緒，**尚未在 GitHub Actions runner 實跑**。

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
