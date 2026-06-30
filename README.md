# 🏛️ 東方森煌 A.A.D 智能文物健檢 LINE Bot

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/framework-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![LINE Bot](https://img.shields.io/badge/LINE-Messaging%20API-green.svg)](https://developers.line.biz/)
[![AI Engine](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-orange.svg)](https://deepmind.google/technologies/gemini/)

「東方森煌 A.A.D 智能文物健檢」是一款專為古玩與文物愛好者設計的 LINE 智慧客服機器人。結合 **Google Gemini 2.5 Flash** 的強大視覺與文本分析能力，使用者只需上傳文物照片，即可獲得即時的初步特徵分析、真品機率估算、市場價值預估，並能自動生成極具未來科技感的 **Cyberpunk 風格診斷圖卡**。

此外，系統無縫整合了**藍新金流 (NewebPay)** 的單筆購買與定期定額訂閱功能（以及**綠界科技 ECPay** 備用金流），並搭配 **PostgreSQL** 進行完整的會員方案配額控管與跨月重置邏輯。

---

## 🌟 核心功能

1. **🤖 A.A.D 智能文物健檢 (AI 模式)**
   - **範疇識別**：支援古玉器（清中期以前）、古佛牌（佛曆2525以前）、古陶瓷、古青銅器與金屬器物。非範疇內物件（如現代珠寶、人像、字畫）會自動攔截。
   - **多角度分析**：引導用戶上傳同一物件的多張細節照片（皮殼、釉色、紋飾、工藝特徵），進行不超過 300 字的客觀分析。
   - **機率性結論**：嚴格遵守不直接判定絕對真偽的原則，輸出 **25% ~ 95%** 的真品機率評估。
   - **市場估值**：在「假設為真品」的前提下，給出客觀的台幣（TWD）市場價值區間。
   - **送檢建議**：依機率高低給予不同的實體送檢建議（高機率引導送檢，低機率建議作工藝品欣賞）。

2. **🖼️ Cyberpunk 科技感診斷圖卡生成**
   - 健檢完成後，系統會自動調用 `ig_card_generator.py`（基於 Pillow 圖像處理庫），將使用者上傳的文物照片剪裁為圓形、嵌入發光外框，並結合網格、HUD 科幻面板、真品機率與估值，生成一張專屬的分享圖卡（適合分享至 Instagram/LINE）。

3. **💳 藍新金流 (NewebPay) 與 綠界金流 (ECPay) 整合**
   - **定期定額訂閱 (NPA-B05)**：支援年約月繳方案，包含「小資玩家」、「進階藏家」、「商務旗艦」，實現每月自動扣款與額度開通。
   - **單筆儲值**：提供「單筆儲值 10 次」點數包，無使用期限。
   - **安全加密**：嚴格按照藍新/綠界官方手冊進行 AES-256-CBC 加密、SHA256 雜湊與 CheckMacValue 計算，確保交易安全。
   - **金流回傳處理**：透過 Webhook 接收付款成功通知，自動加值或更新資料庫中的會員等級。

4. **👥 雙模切換 (AI / 真人)**
   - 使用者可隨時透過選單或輸入關鍵字切換為「人工預約」模式，系統會提供專人預約引導，並暫停 AI 自動回覆，直至切換回「AI 模式」。

5. **📊 額度與會員系統**
   - **方案配額**：
     - `FREE` (免費體驗)：當月 3 次額度。
     - `BASIC` (小資玩家)：月費 NT$ 88，當月 8 次額度，實體送檢折抵 100 元/件。
     - `ADVANCED` (進階藏家)：月費 NT$ 399，當月 50 次額度，實體送檢折抵 300 元/件。
     - `BUSINESS` (商務旗艦)：月費 NT$ 860，當月 150 次額度，實體送檢折抵 500 元/件。
   - **額度扣除優先級**：系統會優先扣除「當月免費/訂閱配額」，配額用罄後才扣除「終身可用儲值點數」。
   - **跨月自動重置**：當用戶在新的月份首次發話時，系統會自動重置其當月已用次數。

---

## 🛠️ 技術棧

- **後端框架**：Python / Flask
- **LINE 整合**：LINE Bot SDK (v1)
- **AI 核心**：Google Generative AI (Gemini 2.5 Flash / `gemini-2.5-flash`)
- **資料庫**：PostgreSQL (使用 `psycopg2-binary` 進行連線)
- **影像處理**：Pillow (PIL) — 用於科技感圖卡繪製與字體渲染
- **加密演算法**：PyCryptodome (AES 加密)
- **部署環境**：Railway (支援 Procfile / Gunicorn)

---

## 📁 專案目錄結構

```plaintext
Senhuang_linebot/
├── app.py                     # 專案主入口，包含 Flask 路由、LINE Webhook 與核心業務邏輯
├── database.py                # PostgreSQL 資料庫連接、表初始化、使用者狀態更新與額度扣減邏輯
├── newebpay_integration.py    # 藍新金流（單筆 MPG / 定期定額 Period）加密、解密與表單 HTML 生成
├── ecpay_integration.py       # 綠界金流（備用）CheckMacValue 計算與 Webhook 驗證
├── ig_card_generator.py       # 使用 Pillow 繪製 Cyberpunk 科技感 A.A.D 診斷圖卡
├── update_webhook.py          # 自動更新 LINE Webhook 網址的輔助指令碼
├── intro.html                 # A.A.D 智能文物健檢介紹網頁 (LIFF / Webview)
├── success.html               # 支付成功後的科幻風格跳轉提示頁面
├── Procfile                   # 適用於 Railway/Heroku 的生產環境啟動設定
├── requirements.txt           # 專案 Python 依賴套件列表
├── static/                    # 靜態資源資料夾（存放 LOGO、背景等）
├── cards/                     # 生成的診斷圖卡存放路徑（對外提供靜態路由）
├── autostart.command          # 本地自動啟動 Cloudflare 隧道與服務的腳本 (Mac/Linux)
├── sync.ps1 / push.ps1        # Windows PowerShell 程式碼同步與推送指令碼
└── .env                       # 環境變數設定檔（需自行建立，切勿上傳至 Git）
```

---

## 💾 資料庫設計 (Database Schema)

本專案使用兩個主要資料表：

### 1. `users` (使用者狀態與額度表)
| 欄位名稱 | 型態 | 預設值 | 說明 |
| :--- | :--- | :--- | :--- |
| `user_id` | `TEXT` | - | **主鍵**。LINE 使用者唯一識別碼。 |
| `current_mode` | `TEXT` | `'HUMAN'` | 當前模式 (`'AI'` 或 `'HUMAN'`)。 |
| `usage_month` | `TEXT` | - | 當前計算額度的月份，格式如 `'2026-06'`。 |
| `usage_count` | `INTEGER` | `0` | 該月份已使用的免費/訂閱健檢次數。 |
| `purchased_quota` | `INTEGER` | `0` | 使用者終身可用的儲值點數。 |
| `subscription_tier`| `TEXT` | `'FREE'` | 會員方案等級 (`'FREE'`, `'BASIC'`, `'ADVANCED'`, `'BUSINESS'`)。 |
| `subscription_expiry`| `TEXT` | - | 訂閱到期日時間字串 (格式 `'YYYY-MM-DD HH:MM:SS'`)。 |

### 2. `payment_orders` (支付訂單對照表)
用於在藍新 Webhook 幕後通知（NotifyURL）未攜帶網址參數時，根據唯一的商店訂單號反查付款的 LINE 使用者與購買方案。
| 欄位名稱 | 型態 | 預設值 | 說明 |
| :--- | :--- | :--- | :--- |
| `order_id` | `TEXT` | - | **主鍵**。唯一訂單編號（藍新 MerchantOrderNo，限30字元內）。 |
| `user_id` | `TEXT` | - | 付款的 LINE 使用者 ID。 |
| `plan_id` | `TEXT` | - | 購買的方案代號（如 `point10`, `basic_single` 等）。 |
| `created_at` | `TIMESTAMP`| `CURRENT_TIMESTAMP` | 訂單建立時間。 |

---

## ⚙️ 本地開發與部署步驟

### 1. 本地環境建置

1. **複製專案並安裝依賴**
   ```bash
   git clone <your-repo-url>
   cd Senhuang_linebot
   python -m venv venv
   # Windows 啟用虛擬環境
   venv\Scripts\activate
   # Mac/Linux 啟用虛擬環境
   source venv/bin/activate
   
   pip install -r requirements.txt
   ```

2. **設定環境變數 (`.env`)**
   在專案根目錄下建立 `.env` 檔案，填入以下資訊：
   ```env
   # LINE Bot 設定
   LINE_CHANNEL_ACCESS_TOKEN=你的_LINE_ACCESS_TOKEN
   LINE_CHANNEL_SECRET=你的_LINE_CHANNEL_SECRET
   
   # Gemini API 設定
   GEMINI_API_KEY=你的_GEMINI_API_KEY
   
   # PostgreSQL 連線字串 (本地測試可填入本地 DB 或是 Railway 外部連線網址)
   DATABASE_URL=postgresql://postgres:密碼@主機:埠號/資料庫名稱
   
   # 藍新金流金鑰 (正式環境/測試環境)
   MERCHANT_ID=你的_藍新商店代號_MerchantID
   HASH_KEY=你的_藍新_HashKey
   HASH_IV=你的_藍新_HashIV
   
   # 部署域名 (選填，本地開發會自動抓取 request.host_url)
   RAILWAY_PUBLIC_DOMAIN=你的網域.railway.app
   ```

3. **啟動 Flask 服務**
   ```bash
   python app.py
   ```
   預設會在 `http://127.0.0.1:8080` 啟動服務。

### 2. 外部通道與 LINE Webhook 設定

由於 LINE 官方需要 HTTPS 協定的 Webhook，本地測試時推薦使用 Ngrok 或 Cloudflare Tunnel (Quick Tunnels)：

1. **開啟通道（以 Cloudflare Tunnel 為例）**
   ```bash
   cloudflared tunnel --url http://localhost:8080
   ```
   這會產生一個隨機的 HTTPS 網址，例如：`https://example.trycloudflare.com`。

2. **自動更新 LINE Webhook 網址**
   專案內提供 `update_webhook.py` 輔助工具。在通道開啟後，另開一個終端機執行：
   ```bash
   python update_webhook.py https://example.trycloudflare.com
   ```
   系統將自動讀取 `.env` 中的 Token 並向 LINE 伺服器註冊新網址：`https://example.trycloudflare.com/callback`。

---

## 🚀 Railway 雲端部署指南

本專案已完全適配 **Railway** 平台：

1. **建立專案**：在 Railway 上建立新專案，並選擇「Deploy from GitHub repo」。
2. **新增 PostgreSQL 服務**：
   - 在同一個專案中新增一個 PostgreSQL 數據庫。
   - Railway 會自動為 Flask 服務與 PostgreSQL 建立關聯，並自動注入 `${{DATABASE_URL}}` 環境變數。
3. **設定環境變數 (Variables)**：
   - 將 `.env` 中的所有 Key（除了 `DATABASE_URL` 由 Railway 自動託管外）手動填入 Railway 的 Variables 面板中。
   - `RAILWAY_PUBLIC_DOMAIN` 可以填寫 Railway 自動分配的域名（不含 `https://`）。
4. **自動啟動**：
   - Railway 會自動偵測根目錄下的 `Procfile`：
     ```procfile
     web: gunicorn app:app
     ```
   - 部署成功後，資料庫將於首次連線時自動執行 `database.init_db()` 初始化資料表。

---

## ⚠️ 聲明與注意事項

1. **AI 健檢侷限性**：A.A.D. 服務是基於 Gemini 大型語言模型及預設提示詞（System Prompt）進行的表面圖像比對，不具備光譜儀、熱釋光或碳14等科學儀器檢測效力，健檢結果**僅供參考**。
2. **文字格式規範**：Gemini 在回覆健檢結果時，最後一行必須嚴格輸出 JSON 格式的標籤：
   `###DATA:{"title": "古物名稱", "prob": "85%", "valuation": "TWD 區間"}###`
   這是系統繪製科幻圖卡時的關鍵資料來源，請勿隨意修改 `app.py` 中的 `SYSTEM_PROMPT` 結構。
3. **金鑰安全性**：請妥善保管藍新與綠界的 `HASH_KEY` 與 `HASH_IV`，切勿將其提交至公開的 Git 倉庫。

---

*Made with ❤️ by 東方森煌開發團隊*
