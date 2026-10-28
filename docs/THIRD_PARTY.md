# 第三方專案實查

2026-10-28（台灣）透過 GitHub 搜尋、HTTPS Git clone 和原始檔檢查。以下為實際檢查的 HEAD，不代表所有專案已安裝或完成效能實測。只引入有明確授權且符合本次範圍的成熟依賴，沒有複製候選專案原始碼。

| 專案與檢查版本 | 真實功能、依賴與授權 | Actions CPU 判斷與採用決定 |
| --- | --- | --- |
| [DDGS](https://github.com/deedy5/ddgs/tree/8e74959141106702645020dcb853c6453b5e5195)，採用 9.16.1 | MIT；Python ≥3.10、Click、Primp、lxml；整合多個公開搜尋入口，不提供事實查證或素材授權 | 已安裝、`pip check` 通過。採用 Brave／DuckDuckGo／Yahoo 後端作為 Bing RSS 以外的來源；沿用代理與 CA，不停用 TLS、不使用付費搜尋 API。不保證免費搜尋服務永遠可用，錯誤會列入報告 |
| [rank_bm25](https://github.com/dorianbrown/rank_bm25/tree/47aa3ddf8dc1ebeb7ef4e65f2b4536af44594099)，採用 0.2.2 | Apache-2.0；只需 NumPy，BM25 文件／段落排序 | 已以真正 BM25 選取測試文章 12,000 字之後的相關原文區間，核對每段 offset 與原文完全相符；CPU、無 embedding／GPU／API。排序分數只選閱讀段落，不代表主張已證實 |
| [Wikipedia-API](https://github.com/martin-majlis/Wikipedia-API/tree/5030820ec87e19d409504c497e84d72160931f9a)，檢查發布版 0.16.0 | MIT；Python ≥3.10、httpx、tenacity；百科擷取。PyPI 發布版固定 Click 8.5.0 | 與目前 PySceneDetect 的 Click <8.3 相衝突，未安裝、未複製原始碼；現階段以一般安全 HTTPS 擷取百科來源，採用 DDGS 補強搜尋，保留既有影片依賴 |
| [PySceneDetect](https://github.com/Breakthrough/PySceneDetect/tree/36ca0229a898d6a25965f5f0b94c109c674833df) | BSD-3-Clause；OpenCV、NumPy；偵測鏡頭切點，不辨識遊戲或取得素材權利 | 已安裝與實測 `scenedetect[opencv]==0.6.7.1` 的 `ContentDetector`；CPU 可用。評估 checkout 是較新的主線，執行版本則固定成熟 API，二者不可混稱同版本 |
| [SentrySearch](https://github.com/ssrajadh/sentrysearch/tree/3694dd0cb27cc57920b2b816996ce5a22662e45c) | Apache-2.0；Python 3.11/3.12、ChromaDB、google-genai；影片區塊 embedding、語義檢索與裁切。Gemini／DashScope 雲端或 Qwen3-VL 本地，後者需要 torch、transformers、torchcodec 等 | 需要既有影片庫，不會找合法遊戲影片、查證或寫紀錄片。上游明示純 CPU 速度／記憶體不實用；不作預設。若以後使用雲端 embedding 也需額度及素材權利，不能把開源程式等同免費服務 |
| [GhostCut AI（本地版本）](https://github.com/himuvai47/ghostcut-ai/tree/bfb3918c3015a40c3dc8076d5ea12e0c229631c3) | 實際有索引／影片生成 Python 模組與 PowerShell 啟動檔；Ollama Qwen2.5-VL 7B、Qwen3.5 9B、whisper.cpp、FFmpeg。完整 checkout 未找到 LICENSE／COPYING；README 只有第三方授權提示 | 不視為已取得程式碼再利用授權，不導入。偏向 Windows、本地大型模型與建議 NVIDIA GPU；未證明一般免費 Linux CPU runner 可達實用速度 |
| [GhostCut_Remake_Video（同名商業服務）](https://github.com/JollyToday/GhostCut_Remake_Video/tree/ff8b1b74af40b6e0702e65daa7f62333301ce351) | clone 內容只有 README 與英語說明，指向 Weydub／GhostCut API；去字幕、改寫／重新配音服務。未找到開源實作或 LICENSE；說明建議事先取得原作者權利 | 不是可免費自架的完整剪輯引擎，不導入。去字幕不會取得合法重製權 |
| [DirectorX](https://github.com/savebees/DirectorX/tree/2b2ae6c56e3ffa29c1ff771af57345430e9f8c9b) | Apache-2.0；真實有 directorx agents/indexing/rendering/services、LangGraph、PySceneDetect、CLIP、sentence-transformers、CLAP、torch，以及文字／視覺相容 API；從 local footage + brief 到配音剪輯及檢查 | 已有較完整剪輯架構，但不是中文題材的網路研究／授權下載器。真實跑需現成影片、音樂、LLM/VLM；模型下載與 CPU 負擔較重，NumPy/OpenCV 約束亦不同。本階段不把整個框架與本專案綁在一起；後續有較大合法素材庫時可另做受測 adapter |
| [footage-retrieval-automation](https://github.com/mthariqd/footage-retrieval-automation/tree/d2f407dcf093749dd5e15a07c84f5f11eefce790) | FastAPI、本地手寫腳本／WAV／SRT、Kokoro `af_heart`、stable-ts/Whisper、SentenceTransformer。`server/footage.py` 實際將資料夾與檔名文字 embedding，非影格內容理解；1080×1920 短片。requirements 是大型 UTF-16 環境匯出。未找到專案 LICENSE；模型授權列表不能代替程式碼授權 | CPU 可做部分文字匹配／FFmpeg，但不滿足自動研究、真實畫面辨識或來源權利。缺明確程式碼授權，不複製或安裝 |

本次直接重用 FFmpeg、PySceneDetect、trafilatura、Edge TTS、OpenCC 與既有 Kokoro adapter，新增的是研究與品質門檻的必要整合。沒有宣稱候選專案全部經效能測試，也不會把檔名／詞重疊稱作影片內容辨識。圖片語義檢查會傳送三張抽樣幀給設定的模型提供者；使用者應選擇可接受的服務與資料處理條件。
