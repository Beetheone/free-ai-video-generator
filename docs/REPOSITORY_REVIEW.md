# 既有程式盤點

本次從原 HEAD `14c153c48fcaab392fe616cbddff52e5c54bf264` 的所有 Python 模組、JSON、README 與四個 Actions workflow 檢查。沒有原有自動測試套件、Python 工具版本鎖定或統一的題材到渲染資料契約；工作樹開始時乾淨。

| 原有模組 | 已有功能 | 問題／本次處理 |
| --- | --- | --- |
| `topic_pipeline.py` | 繁中／英文 Google News RSS、固定寶可夢等 alias、JSON 規劃 | 沒有讀原文、查證、腳本或渲染；正常退出容易被誤認已產片。改為新的完整控制器入口；阻擋退出 2 |
| `agent_factory.py` | 人工 scenes、手動權利 manifest、FFprobe、文字詞重疊 | 人工 `source_verified` 布林不代表查證；詞重疊不代表看過影片；預設 scenes 是考古題材。保留手動規劃器，移除其每日排程，文件標示舊流程 |
| `render.py` | Kokoro／Piper 配音、Pixabay／Pexels／Commons、FFmpeg 1080p、SRT | 固定 `scenes.json` 與考古標題；15 秒場景、缺片回退圖片／文字卡；沒有語義畫面驗證；與題材研究未相連。保留不改動，新增流程完全不引用其文字卡 fallback |
| `generate_video.py` | 手寫腳本、Edge 配音、AI 圖片、角色嘴形／閃眼、FFmpeg | 是圖片／角色動畫路線，不能當真實遊戲紀錄片。保留 |
| `media_assets.py`、`open_video.py`、`pixabay_video.py` | Commons 圖片／影片、Pixabay API 與署名 | 查詢映射與fallback偏考古；舊 Commons 授權 substring 比對不是精確許可清單，可能接受不適用授權。新流程用獨立精確授權門檻，不沿用舊寬鬆判斷；舊功能保留但不代表其權利檢查已合格 |
| `kokoro_voice.py`、`piper_voice.py` | CPU 中文配音、OpenCC 轉簡體 | 可保留；Kokoro 為普通話且需下載模型，無詞對齊。新流程採實測短句時間，明確標記非詞級對齊 |

原有三條路線都有 subprocess/FFprobe/配音與場景處理，重複但輸入／用途不同。沒有強行合併而破壞既有操作；新流程統一自己使用的 bounded IO、媒體 probe、資料保存與階段錯誤。舊 workflow 的其他既有問題留在後續獨立修改，避免把未測過的既有功能宣稱一起修好。
