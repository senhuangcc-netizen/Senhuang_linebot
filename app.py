import os
import sys

# 修正中文路徑導致的 SSL 憑證抓取失敗問題
try:
    import certifi
    import ssl
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    # 強制重啟全域 SSL 環境，避免舊路徑快取
    ssl._create_default_https_context = ssl._create_unverified_context
except Exception:
    pass

from flask import Flask, request, abort, send_from_directory, session, redirect, url_for, render_template_string, jsonify, Response
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage,
    StickerMessage, ImageSendMessage
)
from linebot.models import FlexSendMessage, CarouselContainer, BubbleContainer, BoxComponent, TextComponent, SeparatorComponent
from google import genai
from google.genai import types
import uuid
import database
import newebpay_integration
import re
import json
import ig_card_generator
def get_price_flex():
    """產生價目表的 Flex Message 物件"""
    
    # --- 卡片 1: 佛牌與玉器 ---
    bubble_1 = BubbleContainer(
        header=BoxComponent(
            layout='vertical',
            background_color='#2c3e50', # 深藍色背景
            contents=[
                TextComponent(text='💎 佛牌與玉器', weight='bold', size='xl', color='#ffffff')
            ]
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                # 佛牌
                TextComponent(text='古佛牌', weight='bold', size='md', color='#1DB446'),
                BoxComponent(layout='baseline', contents=[
                    TextComponent(text='鑑定費', size='sm', color='#555555', flex=1),
                    TextComponent(text='NT$ 3,800', size='sm', color='#111111', align='end', flex=2)
                ]),
                TextComponent(text='(約 USD 128)', size='xs', color='#aaaaaa', align='end'),
                SeparatorComponent(margin='md'),
                
                # 玉器
                BoxComponent(layout='vertical', margin='md', contents=[
                    TextComponent(text='古玉器 (清中期前)', weight='bold', size='md', color='#1DB446'),
                    BoxComponent(layout='baseline', contents=[
                        TextComponent(text='鑑定費', size='sm', color='#555555', flex=1),
                        TextComponent(text='NT$ 4,800', size='sm', color='#111111', align='end', flex=2)
                    ]),
                    TextComponent(text='(約 USD 165)', size='xs', color='#aaaaaa', align='end'),
                ])
            ]
        )
    )

    # --- 卡片 2: 古銅器 ---
    bubble_2 = BubbleContainer(
        header=BoxComponent(
            layout='vertical',
            background_color='#8e44ad', # 紫色背景
            contents=[
                TextComponent(text='⚱️ 古銅器', weight='bold', size='xl', color='#ffffff')
            ]
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(text='金屬器/青銅/佛像', weight='bold', size='md', color='#8e44ad'),
                SeparatorComponent(margin='md'),
                # 中小型
                BoxComponent(layout='baseline', margin='md', contents=[
                    TextComponent(text='中小型', size='sm', weight='bold', flex=1),
                    TextComponent(text='< 15cm', size='xs', color='#aaaaaa', align='end', flex=1)
                ]),
                TextComponent(text='NT$ 2,800', size='md', color='#111111', align='end'),
                
                # 大型
                BoxComponent(layout='baseline', margin='md', contents=[
                    TextComponent(text='大型', size='sm', weight='bold', flex=1),
                    TextComponent(text='> 16cm', size='xs', color='#aaaaaa', align='end', flex=1)
                ]),
                TextComponent(text='NT$ 4,800', size='md', color='#111111', align='end'),
            ]
        )
    )

    # --- 卡片 3: 古瓷器 (比較複雜) ---
    bubble_3 = BubbleContainer(
        header=BoxComponent(
            layout='vertical',
            background_color='#c0392b', # 紅色背景
            contents=[
                TextComponent(text='🏺 古瓷器特惠', weight='bold', size='xl', color='#ffffff')
            ]
        ),
        body=BoxComponent(
            layout='vertical',
            contents=[
                # 小型
                BoxComponent(layout='baseline', contents=[
                    TextComponent(text='小型 (<15cm)', size='xs', color='#555555', flex=4),
                    TextComponent(text='NT$ 5,700', size='sm', weight='bold', color='#c0392b', align='end', flex=3)
                ]),
                TextComponent(text='(原價 $9,600)', size='xxs', color='#aaaaaa', decoration='line-through', align='end'),
                SeparatorComponent(margin='sm'),

                # 中型
                BoxComponent(layout='baseline', margin='sm', contents=[
                    TextComponent(text='中型 (15-30cm)', size='xs', color='#555555', flex=4),
                    TextComponent(text='NT$ 7,500', size='sm', weight='bold', color='#c0392b', align='end', flex=3)
                ]),
                TextComponent(text='(原價 $12,000)', size='xxs', color='#aaaaaa', decoration='line-through', align='end'),
                SeparatorComponent(margin='sm'),

                # 中大型
                BoxComponent(layout='baseline', margin='sm', contents=[
                    TextComponent(text='中大型 (30-50cm)', size='xs', color='#555555', flex=4),
                    TextComponent(text='NT$ 9,600', size='sm', weight='bold', color='#c0392b', align='end', flex=3)
                ]),
                TextComponent(text='(原價 $16,000)', size='xxs', color='#aaaaaa', decoration='line-through', align='end'),
                
                TextComponent(text='* >51cm 暫不收檢', margin='md', size='xs', color='#aaaaaa', style='italic'),
            ]
        )
    )

    return FlexSendMessage(
        alt_text="東方森煌價目表",
        contents=CarouselContainer(contents=[bubble_1, bubble_2, bubble_3])
    )

def get_subscription_flex(host, user_id):
    """產生包含 ECPay 付款連結的多層級訂閱方案 Flex Message"""
    from linebot.models import URIAction, ButtonComponent
    
    def make_plan_bubble(color, title, desc1, desc2, price, price_desc, plan_id):
        payment_url = f"{host}/buy/{user_id}/{plan_id}"
        return BubbleContainer(
            header=BoxComponent(
                layout='vertical',
                background_color=color,
                contents=[TextComponent(text=title, weight='bold', size='xl', color='#ffffff')]
            ),
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(text=desc1, weight='bold', size='md', color=color),
                    TextComponent(text=desc2, size='sm', color='#555555', wrap=True),
                    SeparatorComponent(margin='md'),
                    BoxComponent(layout='baseline', margin='md', contents=[
                        TextComponent(text=price, size='lg', weight='bold', color='#111111', flex=1),
                        TextComponent(text=price_desc, size='xs', color='#aaaaaa', align='end', flex=1)
                    ]),
                ]
            ),
            footer=BoxComponent(
                layout='vertical',
                contents=[
                    ButtonComponent(
                        style='primary',
                        color=color,
                        action=URIAction(label='前往付款', uri=payment_url)
                    )
                ]
            )
        )

    b1 = make_plan_bubble('#7f8c8d', '🪙 單筆儲值', '10 次，永久有效', '無實體送檢折抵', 'NT$ 100', '單次購買', 'point10')
    b2 = make_plan_bubble('#27ae60', '🌱 小資玩家', '每月 8 件智能健檢', '實體送檢折抵100元/件(注意方案不能重複訂閱)', 'NT$ 88', '月費，自動續訂', 'basic_single')
    b3 = make_plan_bubble('#2980b9', '👑 進階藏家', '每月 50 件智能健檢', '實體送檢折抵300元/件(注意方案不能重複訂閱)', 'NT$ 399', '月費，自動續訂', 'advanced_single')
    b4 = make_plan_bubble('#8e44ad', '💎 商務旗艦', '每月 150 件智能健檢', '實體送檢折抵500元/件(注意方案不能重複訂閱)', 'NT$ 860', '月費，自動續訂', 'business_single')

    b_notice = BubbleContainer(
        body=BoxComponent(
            layout='vertical',
            contents=[
                TextComponent(text='⚠️ 訂閱與儲值須知', weight='bold', size='lg', color='#e74c3c'),
                SeparatorComponent(margin='md'),
                TextComponent(text='系統限制每位用戶只能訂閱「一個」包月方案。', size='sm', color='#2c3e50', weight='bold', wrap=True),
                TextComponent(text='若已訂閱方案而額度不足，請選購【單筆儲值】點數，或聯絡客服進行方案升級，請勿重複訂閱多個方案以免被重複扣款！', size='xs', color='#7f8c8d', margin='md', wrap=True),
            ]
        )
    )

    return FlexSendMessage(
        alt_text="東方森煌館 付費與訂閱方案",
        contents=CarouselContainer(contents=[b_notice, b2, b3, b4, b1])
    )
def get_booking_guide_flex():
    """產生引導至官方 LINE 的精美 Flex Message"""
    from linebot.models import (
        URIAction, ButtonComponent, BubbleContainer, BoxComponent, TextComponent, SeparatorComponent
    )
    bubble = BubbleContainer(
        size='giga',
        styles={
            'header': {'background_color': '#111111'},
            'body': {'background_color': '#1a1a1a'},
            'footer': {'background_color': '#111111'}
        },
        header=BoxComponent(
            layout='vertical',
            padding_all='lg',
            contents=[
                TextComponent(text='🏛️ 東方森煌官方', weight='bold', size='lg', color='#c5a880')
            ]
        ),
        body=BoxComponent(
            layout='vertical',
            padding_all='xl',
            contents=[
                TextComponent(text='專人預約送檢與客服', weight='bold', size='xl', color='#ffffff'),
                SeparatorComponent(margin='md', color='#333333'),
                
                TextComponent(
                    text='本鑑定所之「現場送檢」與「寄送送檢」預約流程，已全面整合至官方 LINE@ 客服帳號。',
                    size='sm',
                    color='#cccccc',
                    wrap=True,
                    margin='lg'
                ),
                
                BoxComponent(
                    layout='vertical',
                    margin='lg',
                    spacing='sm',
                    contents=[
                        BoxComponent(layout='baseline', contents=[
                            TextComponent(text='🔸', size='xs', color='#c5a880', flex=1),
                            TextComponent(text='預約現場送件 (親自到店)', size='sm', color='#aaaaaa', flex=12)
                        ]),
                        BoxComponent(layout='baseline', contents=[
                            TextComponent(text='🔸', size='xs', color='#c5a880', flex=1),
                            TextComponent(text='線上登記與寄送送檢', size='sm', color='#aaaaaa', flex=12)
                        ]),
                        BoxComponent(layout='baseline', contents=[
                            TextComponent(text='🔸', size='xs', color='#c5a880', flex=1),
                            TextComponent(text='各類常見問答自主查詢', size='sm', color='#aaaaaa', flex=12)
                        ])
                    ]
                ),
                
                TextComponent(
                    text='請點擊下方按鈕前往官方 LINE，並發送物件照片與預約需求，將有專人立即為您登記：',
                    size='sm',
                    color='#c5a880',
                    weight='bold',
                    wrap=True,
                    margin='lg'
                )
            ]
        ),
        footer=BoxComponent(
            layout='vertical',
            padding_all='lg',
            contents=[
                ButtonComponent(
                    style='primary',
                    color='#c5a880',
                    action=URIAction(
                        label='立即前往官方預約 ➔',
                        uri='https://line.me/R/ti/p/@640aodur'
                    )
                ),
                TextComponent(
                    text='或手動搜尋 LINE ID: @640aodur',
                    size='xs',
                    color='#666666',
                    align='center',
                    margin='md'
                )
            ]
        )
    )
    return FlexSendMessage(
        alt_text="東方森煌 - 官方預約送檢引導",
        contents=bubble
    )

def check_quota_and_notify(user_id, reply_token):
    from datetime import datetime
    now = datetime.now()
    month_str = f"{now.year}-{now.month:02d}"
    
    user_state = database.get_user_status_data(user_id, month_str)
    free_limit = int(user_state.get('free_limit', 3))
    usage = int(user_state.get('usage', 0))
    purchased = int(user_state.get('purchased', 0))
    
    if usage >= free_limit and purchased <= 0:
        railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        if railway_domain:
            host = f"https://{railway_domain}"
        else:
            from flask import request
            try:
                host = request.host_url.rstrip("/")
            except:
                host = ""
        flex_msg = get_subscription_flex(host, user_id)
        line_bot_api.reply_message(
            reply_token,
            [
                TextSendMessage(text="⚠️ 您的健檢額度已用盡，請參考以下方案擴充您的額度："),
                flex_msg
            ]
        )
        return True
    return False

def classify_category(title, text):
    combined = (title + " " + text).lower()
    if "佛牌" in combined:
        return "佛牌"
    elif "玉" in combined:
        return "玉器"
    elif any(k in combined for k in ["瓷", "陶", "釉", "罐", "瓶", "碗", "碟", "盞", "杯"]):
        return "陶瓷"
    elif any(k in combined for k in ["銅", "金屬", "法器", "法印", "鼎", "爐", "鐵"]):
        return "銅器"
    return "其他"

def parse_valuation_numeric(val_str):
    val_min = 0
    val_max = 0
    if not val_str:
        return val_min, val_max
    try:
        clean_str = val_str.replace("TWD", "").replace("USD", "").replace("$", "").replace(" ", "").replace(",", "").strip()
        if "~" in clean_str:
            parts = clean_str.split("~", 1)
            p1, p2 = parts[0], parts[1]
        else:
            p1 = p2 = clean_str
            
        def to_number(p):
            multiplier = 1
            if "萬" in p:
                multiplier = 10000
                p = p.replace("萬", "")
            nums = re.findall(r"[\d\.]+", p)
            if nums:
                val = float(nums[0])
                return int(val * multiplier)
            return 0
            
        val_min = to_number(p1)
        val_max = to_number(p2)
    except Exception as e:
        print(f"Error parsing numeric valuation: {e}")
    return val_min, val_max

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "senhuang_secret_key_129847192847")

from dotenv import load_dotenv
load_dotenv()

# ==========================================
# 1. 設定區 (請填入你的 Key)
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=55000)
)

# ==========================================
# 2. 記憶體與 PostgreSQL 資料庫
# ==========================================
import database
database.init_db()

# 記錄 Gemini 的對話歷史物件 (短暫對話暫存，維持在記憶體)
chat_sessions = {}
# 暫存用戶上傳的照片 (防呆機制，短暫資料)
user_images = {}
MONTHLY_LIMIT = 8

# ==========================================
# 3. Gemini 模型設定 (東方森煌專屬人設)
# ==========================================
SYSTEM_PROMPT = """
你現在是【東方森煌古文物鑑定中心】的智能客服。
語氣：專業、穩重、客觀、有禮貌。

【核心資訊】
1. 服務項目：古玉器、古佛牌、古陶瓷、青銅器、金銅器物的專業鑑定

2. 收費標準：
   - 古佛牌：TWD 3,800 / USD 128
   - 古玉器：TWD 4,800 / USD 165
   - 古銅器：中小型(<15cm) TWD 2,800；大型(>16cm) TWD 4,800
   - 古瓷器：小型(<15cm) 特惠 TWD 5,700（原 9,600）；中型(15-30cm) 特惠 TWD 7,500（原 12,000）；中大型(30-50cm) 特惠 TWD 9,600（原 16,000）；大型(>51cm) 暫不收檢

3. 流程：預約 → 攜帶/寄送物件 → 專家初判 → 鑑定（約7~14工作天）→ 結果通知 → 寄回（真品附鑑定卡）

4. 聯絡資訊：
   地址：236新北市土城區中央路二段191號7樓之4
   電話：02-8260-2664
   營業：週一至週五 10:00–18:00，週六日休息

5. 可受理佛牌（佛曆2525/A.D.1982以前）：
阿贊多：瓦拉康崇迪、給猜優崇迪、玉佛寺佛牌（全系列）
阿贊添：龍普托（全系列）
龍婆班：神獸崇迪（全系列）
龍婆銀：2460財佛小立尊、2460大鋤頭、2460小鋤頭
龍婆BOON：兆索佛（第一期）
龍婆添：2515~2517 帕坤平古曼大模/小模、自身像、必打
龍婆多：2520~2522 必打（全系列）
出土類五大古佛、南奔出塔老佛牌
其他品項歡迎來信洽詢。

6. 可受理玉器（清中期乾隆/A.D.1796以前）：
文化期、商周、春秋戰國、漢~六朝、隋唐、宋元、明清；其他歡迎洽詢。

7. 可受理古金屬器：漢代以前青銅器、清代以前西藏天鐵天銅、清代以前藏傳金屬法器/法印/金銅佛像；其他歡迎洽詢。

8. 可受理古陶瓷：彩陶文化期以後古陶器、漢唐彩釉古瓷、宋元明清各類古瓷器；其他歡迎洽詢。

【AI文物健檢規則與原則】
# Role
你是「東方森煌古物鑑定所」的專屬 LINE 客服機器人，執行「智能文物健檢 (A.A.D)」服務，透過照片與文字進行初步特徵分析與真偽過濾，給予市場估價，引導有潛力的物件進行實體預約送檢。

# 拒絕條款
若照片明顯不屬於可鑑定範疇（如人體照片、書畫字帖、現代珠寶鑽石、鑑定報告文件等），請直接回覆：
「您所上傳的照片不在檢測項目內，請重新上傳其他照片，或洽真人客服。」

# Core Rules
1. 【絕對禁語】：絕不直接下達「這是真品」或「這是贗品」的絕對性結論。
2. 【機率限制】：以「真品機率百分比」表達結論，範圍限制在 10%~95%。
3. 【單一物件原則】：提醒使用者單次上傳多張照片必須是同一件物品。請注意，使用者上傳多張照片通常是同一件物品的正面、背面、底足或不同局部細節。除非照片中出現了「截然不同的器物類別」（例如一張是玉珮，另一張是佛牌），否則 AI 必須預設所有照片皆屬於同一個物件的各個角度，並進行綜合分析。請不要因為照片角度、拍攝背景或光線差異大，就判定為「上傳了不同的物件」而拒絕回答。
4. 【市場估價原則】：必須提供市場價值估算，前提為「假設此件物品為真品」。

# Response Format（依序輸出，不可省略）
## 1. 提醒（固定輸出）
「歡迎使用智能文物健檢 (A.A.D)！
📌 提醒：請確認您上傳的一組照片，皆屬於同一件物件。」

## 2. 物件特徵初步分析
（客觀描述照片中的器形、紋飾、皮殼、釉色或工藝特徵，指出符合或不符合時代特徵的地方。限制不要超過300字）

## 3. A.A.D 健檢機率結論
格式：「綜合以上特徵比對，本件物件的真品機率評估為：[數字]%。」

## 4. 市場價值預估
格式：「若本件物品經實體儀器與專家確認為真品，從物件特徵初步分析為一件[器物名稱]其當前市場參考價值約落在TWD[金額區間]。」

## 5. 後續送檢建議
- 機率 > 65%：「此物件具備較高的時代特徵與研究價值。建議您點擊下方選單的『人工預約』，交由東方森煌古物鑑定所進行實體儀器檢測與專家判定，以獲取正式鑑定報告。」
- 機率 50%~65%：「此物件特徵好壞參半。若您對此物件有特殊情感或想進一步釐清，可考慮預約實體送檢。」
- 機率 < 50%：「此物件的現代工藝或仿製特徵較為明顯，目前不建議您花費成本進行實體送檢。建議作為一般工藝品欣賞即可。」

## 6. 系統警語（固定輸出，置於篇末）
「⚠️ 警語：A.D.D. 乃基於 Gemini 全球資料庫以及市場實戰調校，然僅以照片判斷仍有一定誤差。雖優於個人 AI 客觀性，但尚不具備完整鑑定效益，僅供過濾及輔助使用。」

請在回應的最後一行嚴格輸出以下 JSON 標籤供系統繪圖使用（不要加上 Markdown backticks 或其他文字）：
###DATA:{"title": "青花龍紋花瓶", "prob": "85%", "valuation": "TWD 10萬~15萬"}###
"""

gemini_model_name = "gemini-2.5-flash"
gemini_config = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    temperature=0.2,
    max_output_tokens=3000
)

# ==========================================
# 4. Webhook 入口
# ==========================================
@app.route("/intro", methods=["GET", "POST"])
def intro():
    try:
        with open("intro.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error loading intro.html: {e}", 404

@app.route("/payment/success", methods=["GET", "POST"])
def payment_success():
    # 判斷藍新回傳的交易狀態
    if request.method == "POST":
        status = request.form.get("Status")
        message = request.form.get("Message", "交易未能完成")
        
        # 如果不是 SUCCESS，顯示失敗或取消的畫面
        if status != "SUCCESS":
            return f"""
            <html>
            <head>
                <title>交易未完成</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-gray-900 text-white min-h-screen flex items-center justify-center p-4">
                <div class="max-w-md w-full bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl p-8 text-center">
                    <div class="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg class="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                    </div>
                    <h2 class="text-2xl font-bold text-white mb-2">交易未完成</h2>
                    <p class="text-gray-400 mb-8">{message}</p>
                    <a href="https://line.me/R/ti/p/@您的機器人ID" class="block w-full py-3 px-4 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors">返回 LINE 重新操作</a>
                </div>
            </body>
            </html>
            """
            
    # 如果是 GET 或是 Status == SUCCESS，則顯示科幻成功頁面
    try:
        with open("success.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error loading success.html: {e}", 404

@app.route("/cards/<filename>")
def serve_card(filename):
    return send_from_directory("cards", filename)

@app.route("/static/<filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


@app.route("/callback", methods=['POST'])
def callback():
    import threading
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 在背景執行緒處理事件，立刻回傳 200 給 LINE
    # 這樣 LINE 不會因為 Gemini API 耗時而重送 webhook
    def process():
        try:
            handler.handle(body, signature)
        except InvalidSignatureError:
            app.logger.error("Invalid webhook signature")
        except Exception as e:
            app.logger.error(f"Background handler error: {e}")

    threading.Thread(target=process, daemon=True).start()
    return 'OK'

@app.route("/buy/<user_id>/<plan_id>", methods=["GET", "POST", "OPTIONS"])
def buy(user_id, plan_id):
    plans = {
        "point10": {"amount": 100, "desc": "購買 10 次健檢額度點數"},
        "basic_single": {"amount": 88, "desc": "小資玩家 年約月繳定期定額 (8次/月)"},
        "advanced_single": {"amount": 399, "desc": "進階藏家 年約月繳定期定額 (50次/月)"},
        "business_single": {"amount": 860, "desc": "商務旗艦 年約月繳定期定額 (150次/月)"}
    }
    if plan_id not in plans:
        return "Invalid Plan", 400
        
    qty_str = request.args.get("qty")
    if plan_id == "point10" and not qty_str and request.method == "GET":
        return render_template_string("""
        <html>
        <head>
            <meta charset="utf-8">
            <title>選擇儲值數量</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: 'Helvetica Neue', Helvetica, Arial, '微軟正黑體', sans-serif; background-color: #f8f9fa; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; max-width: 90%; width: 400px; box-sizing: border-box; }
                h1 { color: #333; font-size: 24px; margin-bottom: 20px; }
                .price-desc { color: #666; font-size: 16px; margin-bottom: 20px; }
                .input-group { margin-bottom: 20px; display: flex; align-items: center; justify-content: center; gap: 10px; }
                input[type=number] { width: 80px; padding: 10px; font-size: 18px; text-align: center; border: 1px solid #ccc; border-radius: 8px; }
                .btn { display: inline-block; padding: 12px 24px; background-color: #00B900; color: white; text-decoration: none; border-radius: 30px; font-weight: bold; border: none; cursor: pointer; transition: background-color 0.3s; width: 100%; font-size: 18px; box-sizing: border-box; }
                .btn:hover { background-color: #009900; }
                .total { font-size: 20px; font-weight: bold; color: #e74c3c; margin-bottom: 20px; }
            </style>
            <script>
                function updateTotal() {
                    const qty = document.getElementById('qty').value;
                    const amount = qty * 100;
                    const quota = qty * 10;
                    document.getElementById('total-amount').innerText = amount;
                    document.getElementById('total-quota').innerText = quota;
                }
            </script>
        </head>
        <body>
            <div class="card">
                <h1>💰 購買單筆儲值點數</h1>
                <div class="price-desc">每單位包含 10 次健檢額度，價格 100 元</div>
                <form action="/buy/{{ user_id }}/{{ plan_id }}" method="GET">
                    <div class="input-group">
                        <label for="qty" style="font-size: 18px; font-weight: bold;">購買單位：</label>
                        <input type="number" id="qty" name="qty" min="1" max="100" value="1" onchange="updateTotal()" onkeyup="updateTotal()">
                    </div>
                    <div class="total">
                        總計獲得 <span id="total-quota">10</span> 次，共 <span id="total-amount">100</span> 元
                    </div>
                    <button type="submit" class="btn">確認付款</button>
                </form>
            </div>
        </body>
        </html>
        """, user_id=user_id, plan_id=plan_id)
        
    if plan_id != "point10":
        from datetime import datetime
        now = datetime.now()
        month_str = f"{now.year}-{now.month:02d}"
        user_state = database.get_user_status_data(user_id, month_str)
        tier = user_state.get('tier', 'FREE')
        if tier not in ["FREE", "ADMIN"]:
            return render_template_string("""
            <html>
            <head>
                <meta charset="utf-8">
                <title>無法重複訂閱 - 東方森煌</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
                <style>
                    body {
                        font-family: 'Outfit', 'Noto Sans TC', sans-serif;
                        background: radial-gradient(circle at center, #1e293b 0%, #0f172a 100%);
                        color: #f1f5f9;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        overflow: hidden;
                    }
                    .card {
                        background: rgba(30, 41, 59, 0.7);
                        backdrop-filter: blur(16px);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        padding: 40px 30px;
                        border-radius: 24px;
                        box-shadow: 0 20px 40px rgba(0,0,0,0.5);
                        text-align: center;
                        max-width: 90%;
                        width: 420px;
                        box-sizing: border-box;
                        animation: fadeInUp 0.6s ease-out;
                    }
                    @keyframes fadeInUp {
                        from { opacity: 0; transform: translateY(20px); }
                        to { opacity: 1; transform: translateY(0); }
                    }
                    .icon-container {
                        width: 80px;
                        height: 80px;
                        background: linear-gradient(135deg, #e11d48 0%, #be123c 100%);
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 0 auto 24px;
                        box-shadow: 0 8px 24px rgba(225, 29, 72, 0.4);
                    }
                    .icon {
                        font-size: 40px;
                        animation: pulse 2s infinite;
                    }
                    @keyframes pulse {
                        0% { transform: scale(1); }
                        50% { transform: scale(1.1); }
                        100% { transform: scale(1); }
                    }
                    h1 {
                        font-size: 24px;
                        font-weight: 800;
                        margin-bottom: 12px;
                        background: linear-gradient(to right, #ffedd5, #fde047);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                    }
                    p {
                        color: #94a3b8;
                        font-size: 15px;
                        line-height: 1.6;
                        margin-bottom: 30px;
                    }
                    p strong {
                        color: #fde047;
                    }
                    .btn-group {
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                    }
                    .btn {
                        display: block;
                        padding: 14px;
                        border-radius: 12px;
                        font-weight: 600;
                        text-decoration: none;
                        font-size: 16px;
                        cursor: pointer;
                        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                        box-sizing: border-box;
                    }
                    .btn-primary {
                        background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%);
                        color: #0f172a;
                        box-shadow: 0 4px 12px rgba(234, 179, 8, 0.3);
                        border: none;
                    }
                    .btn-primary:hover {
                        transform: translateY(-2px);
                        box-shadow: 0 6px 20px rgba(234, 179, 8, 0.5);
                    }
                    .btn-secondary {
                        background: transparent;
                        border: 1px solid rgba(255, 255, 255, 0.2);
                        color: #cbd5e1;
                    }
                    .btn-secondary:hover {
                        background: rgba(255, 255, 255, 0.05);
                        border-color: rgba(255, 255, 255, 0.4);
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon-container">
                        <div class="icon">⚠️</div>
                    </div>
                    <h1>您已有使用中的會員方案</h1>
                    <p>
                        為維護金流安全，系統限制每個帳號<strong>僅能訂閱一個</strong>包月方案。<br><br>
                        若您目前額度不足，建議加購<strong>「單筆儲值」點數</strong>，或聯絡客服為您手動升級方案，請勿重複付款訂閱。
                    </p>
                    <div class="btn-group">
                        <a href="/buy/{{ user_id }}/point10" class="btn btn-primary">🪙 前往購買單筆儲值點數</a>
                        <button onclick="window.close();" class="btn btn-secondary">❌ 關閉此視窗</button>
                    </div>
                </div>
            </body>
            </html>
            """, user_id=user_id), 400
            
    amount = plans[plan_id]["amount"]
    
    if plan_id == "point10":
        try:
            qty = int(qty_str) if qty_str else 1
        except:
            qty = 1
        qty = max(1, min(100, qty))
        amount = amount * qty
    
    # 產生唯一的訂單編號 (藍新 MerchantOrderNo 限 30 碼內)
    order_id = "A" + uuid.uuid4().hex[:20]
    
    # 將訂單資訊存入資料庫對照表，避免在網址帶參數導致 SHA 驗證失敗
    database.create_payment_order(order_id, user_id, plan_id, amount)
    
    # 動態取得伺服器域名作為 URL (必須是 HTTPS)
    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if railway_domain:
        host = f"https://{railway_domain}"
    else:
        host = request.host_url.rstrip("/")
        
    notify_url = f"{host}/newebpay/period_return" if plan_id != "point10" else f"{host}/newebpay/return"
    client_back_url = f"{host}/payment/success" 
    
    # 使用純英文描述避免編碼問題
    ascii_desc = "Antique_Appraisal_Service"
    email = ""
    
    if plan_id == "point10":
        html = newebpay_integration.generate_newebpay_form_html(
            order_id, amount, ascii_desc, email, notify_url, client_back_url
        )
    else:
        # 定期定額訂閱使用 NPA-B05 專用端點與加密
        html = newebpay_integration.generate_newebpay_period_form_html(
            order_id, amount, plans[plan_id]["desc"], email, notify_url, client_back_url
        )
    return html

@app.route("/newebpay/return", methods=["POST"])
def newebpay_return():
    trade_info_hex = request.form.get("TradeInfo") or request.args.get("TradeInfo") or request.values.get("TradeInfo")
    if not trade_info_hex:
        app.logger.error("[NewebPay Return] No TradeInfo found in form, args, or values")
        return "No TradeInfo", 400
        
    data = newebpay_integration.decrypt_newebpay_response(
        trade_info_hex, 
        newebpay_integration.HASH_KEY, 
        newebpay_integration.HASH_IV
    )
    
    if not data:
        app.logger.error(f"[NewebPay Return] Decryption failed for TradeInfo: {trade_info_hex[:50] if trade_info_hex else 'None'}...")
        return "Decrypt Error", 400
        
    # 加入日誌以利除錯
    app.logger.info(f"[NewebPay Return] Decrypted Data: {data}")
    status = data.get("Status")
    result = data.get("Result") or {}
    order_id = (
        result.get("MerchantOrderNo")
        or data.get("MerchantOrderNo")
        or result.get("MerOrderNo")
        or data.get("MerOrderNo")
    )
    if status == "SUCCESS":
        # 從資料庫抓回對應的 user_id 和 plan_id
        order_info = database.get_payment_order(order_id)
        
        user_id = None
        plan_id = None
        if order_info:
            user_id = order_info['user_id']
            plan_id = order_info['plan_id']
        
        if user_id and plan_id:
            if plan_id == "point10":
                paid_amount = int(result.get("Amt", 100))
                qty = paid_amount // 100
                added_quota = qty * 10
                database.add_purchased_quota(user_id, added_quota)
                msg_text = f"🎉 [藍新支付] 感謝購買！您的 {added_quota} 次額度已入帳 (永久有效)。"
            elif plan_id == "basic_single":
                database.update_subscription(user_id, "BASIC")
                msg_text = "🎉 [藍新支付] 感謝訂閱！升級為「小資玩家」年約定期定額方案，本月已開通 15 次智能健檢！"
            elif plan_id == "advanced_single":
                database.update_subscription(user_id, "ADVANCED")
                msg_text = "🎉 [藍新支付] 感謝訂閱！升級為「進階藏家」年約定期定額方案，本月已開通 100 次智能健檢！"
            elif plan_id == "business_single":
                database.update_subscription(user_id, "BUSINESS")
                msg_text = "🎉 [藍新支付] 感謝訂閱！升級為「商務旗艦」年約定期定額方案，本月已開通 1000 次智能健檢！"
            
            # 取得最新額度資訊
            from datetime import datetime, timezone, timedelta
            tz_tw = timezone(timedelta(hours=8))
            now = datetime.now(tz_tw)
            month_str = f"{now.year}-{now.month:02d}"
            user_state = database.get_user_status_data(user_id, month_str)
            free_limit = int(user_state.get('free_limit', 3))
            usage = int(user_state.get('usage', 0))
            purchased = int(user_state.get('purchased', 0))
            tier = user_state.get('tier', 'FREE')
            
            rem_free = max(0, free_limit - usage)
            msg_text += f"\n\n---\n📊 目前最新額度狀態：\n⭐ 會員方案：{tier}\n🎁 當月方案額度剩餘：{rem_free} 次\n🪙 終身可用儲值點數：{purchased} 點"
            
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=msg_text))
            except Exception as e:
                app.logger.error(f"Push message failed: {e}")
        
        # 標記訂單為支付成功，並記錄交易資訊
        database.update_payment_order_status(
            order_id, 
            'SUCCESS', 
            trade_no=result.get("TradeNo"), 
            pay_time=result.get("PayTime"), 
            amount=result.get("Amt")
        )
    else:
        # 標記訂單為交易失敗
        database.update_payment_order_status(
            order_id, 
            'FAILED', 
            trade_no=result.get("TradeNo") or data.get("TradeNo"), 
            pay_time=result.get("PayTime") or data.get("PayTime"), 
            amount=result.get("Amt") or data.get("Amt")
        )
        
    return "OK"

@app.route("/newebpay/period_return", methods=["POST"])
def newebpay_period_return():
    period_hex = request.form.get("Period") or request.args.get("Period") or request.values.get("Period")
    if not period_hex:
        app.logger.error("[NewebPay Period Return] No Period data found in form, args, or values")
        return "No PeriodData", 400
        
    data = newebpay_integration.decrypt_newebpay_period_response(
        period_hex, 
        newebpay_integration.HASH_KEY, 
        newebpay_integration.HASH_IV
    )
    
    if not data:
        app.logger.error(f"[NewebPay Period Return] Decryption failed for Period: {period_hex[:50] if period_hex else 'None'}...")
        return "Decrypt Error", 400
        
    # 加入日誌以利除錯
    app.logger.info(f"[NewebPay Period Return] Decrypted Data: {data}")
    status = data.get("Status")
    result = data.get("Result") or {}
    order_id = (
        result.get("MerchantOrderNo")
        or data.get("MerchantOrderNo")
        or result.get("MerOrderNo")
        or data.get("MerOrderNo")
    )
    if status == "SUCCESS":
        # 從資料庫抓回對應的 user_id 和 plan_id
        order_info = database.get_payment_order(order_id)
        
        user_id = None
        plan_id = None
        if order_info:
            user_id = order_info['user_id']
            plan_id = order_info['plan_id']
            
        if user_id and plan_id:
            ext_day = result.get("Extday") or data.get("Extday")
            
            if ext_day:
                expiry_str = f"{ext_day} 23:59:59"
            else:
                from datetime import datetime, timedelta, timezone
                tz_tw = timezone(timedelta(hours=8))
                expiry_str = (datetime.now(tz_tw) + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            
            warning_note = "\n⚠️【重要提醒】系統限制每位用戶只能訂閱「一個」包月方案。如需更多額度，請於聊天室輸入「購買」並加購「單筆儲值」點數，請勿重複訂閱多個方案，以防被重複扣款。"
            
            if plan_id == "basic_single":
                database.update_subscription(user_id, "BASIC", expiry_str)
                msg_text = "🎉 [藍新訂閱] 感謝訂閱！升級為「小資玩家」定期定額方案，每月固定扣款，本月已開通 8 次智能健檢！" + warning_note
            elif plan_id == "advanced_single":
                database.update_subscription(user_id, "ADVANCED", expiry_str)
                msg_text = "🎉 [藍新訂閱] 感謝訂閱！升級為「進階藏家」定期定額方案，每月固定扣款，本月已開通 50 次智能健檢！" + warning_note
            elif plan_id == "business_single":
                database.update_subscription(user_id, "BUSINESS", expiry_str)
                msg_text = "🎉 [藍新訂閱] 感謝訂閱！升級為「商務旗艦」定期定額方案，每月固定扣款，本月已開通 150 次智能健檢！" + warning_note
            else:
                msg_text = "🎉 [藍新訂閱] 您的定期定額委託已成功建立並完成首期扣款！" + warning_note
                
            # 取得最新額度資訊
            from datetime import datetime, timezone, timedelta
            tz_tw = timezone(timedelta(hours=8))
            now = datetime.now(tz_tw)
            month_str = f"{now.year}-{now.month:02d}"
            user_state = database.get_user_status_data(user_id, month_str)
            free_limit = int(user_state.get('free_limit', 3))
            usage = int(user_state.get('usage', 0))
            purchased = int(user_state.get('purchased', 0))
            tier = user_state.get('tier', 'FREE')
            
            rem_free = max(0, free_limit - usage)
            msg_text += f"\n\n---\n📊 目前最新額度狀態：\n⭐ 會員方案：{tier}\n🎁 當月方案額度剩餘：{rem_free} 次\n🪙 終身可用儲值點數：{purchased} 點"
            
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=msg_text))
            except Exception as e:
                app.logger.error(f"Push message failed: {e}")
        
        # 標記訂單為支付成功，並記錄交易資訊
        auth_time = result.get("AuthTime") or data.get("AuthTime")
        auth_amt = result.get("AuthAmt") or data.get("AuthAmt")
        trade_no = result.get("TradeNo") or data.get("TradeNo")
        database.update_payment_order_status(
            order_id, 
            'SUCCESS', 
            trade_no=trade_no, 
            pay_time=auth_time, 
            amount=auth_amt
        )
    else:
        # 標記訂單為交易失敗
        database.update_payment_order_status(
            order_id, 
            'FAILED'
        )
                
    return "OK"

@app.route("/ecpay/return", methods=["POST"])
def ecpay_return():
    import ecpay_integration
    import database
    
    if not ecpay_integration.verify_ecpay_callback(request.form):
        return "0|CheckMacValue Error", 400
        
    rtn_code = request.form.get("RtnCode")
    order_id = request.form.get("MerchantTradeNo")
    
    if rtn_code == "1":
        # 交易成功
        custom_field = request.form.get("CustomField1", "")
        parts = custom_field.split("|")
        if len(parts) == 2:
            user_id, plan_id = parts
            
            if plan_id == "point10":
                trade_amt = int(request.form.get("TradeAmt", 100))
                qty = trade_amt // 100
                added_quota = qty * 10
                database.add_purchased_quota(user_id, added_quota)
                msg_text = f"🎉 感謝購買！您的 {added_quota} 次額度已入帳 (永久有效)。\n現在您可以繼續傳送照片進行智能文物健檢！"
            elif plan_id == "basic_single":
                database.update_subscription(user_id, "BASIC")
                msg_text = "🎉 感謝訂閱！升級為「小資玩家」，本月擁有 15 次智能健檢，且人工鑑定折抵 100 元！"
            elif plan_id == "advanced_single":
                database.update_subscription(user_id, "ADVANCED")
                msg_text = "🎉 感謝訂閱！升級為「進階藏家」，本月擁有 100 次智能健檢，且人工鑑定折抵 200 元！"
            elif plan_id == "business_single":
                database.update_subscription(user_id, "BUSINESS")
                msg_text = "🎉 感謝訂閱！升級為「商務旗艦」，本月擁有 1000 次智能健檢，且人工鑑定折抵 300 元！"
                
            # 取得最新額度資訊並附加在訊息後方
            from datetime import datetime, timezone, timedelta
            tz_tw = timezone(timedelta(hours=8))
            now = datetime.now(tz_tw)
            month_str = f"{now.year}-{now.month:02d}"
            user_state = database.get_user_status_data(user_id, month_str)
            free_limit = int(user_state.get('free_limit', 3))
            usage = int(user_state.get('usage', 0))
            purchased = int(user_state.get('purchased', 0))
            tier = user_state.get('tier', 'FREE')
            
            rem_free = max(0, free_limit - usage)
            
            msg_text += f"\n\n---\n📊 目前最新額度狀態：\n⭐ 會員方案：{tier}\n🎁 當月方案額度剩餘：{rem_free} 次\n🪙 終身可用儲值點數：{purchased} 點"
            
            # 主動推播給消費者
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=msg_text))
            except Exception as e:
                app.logger.error(f"Push message failed: {e}")
                
        if order_id:
            database.update_payment_order_status(
                order_id, 
                'SUCCESS', 
                trade_no=request.form.get("TradeNo"), 
                pay_time=request.form.get("PaymentDate"), 
                amount=request.form.get("TradeAmt")
            )
    else:
        if order_id:
            database.update_payment_order_status(
                order_id, 
                'FAILED', 
                trade_no=request.form.get("TradeNo"), 
                pay_time=request.form.get("PaymentDate"), 
                amount=request.form.get("TradeAmt")
            )
                
    return "1|OK"

# ==========================================
# 5. 訊息處理邏輯
# ==========================================

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_msg = event.message.text.strip()
    
    # 自動更新/保存使用者暱稱
    try:
        stored_name = database.get_user_display_name(user_id)
        if not stored_name:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
            database.update_user_display_name(user_id, display_name)
    except Exception as e:
        app.logger.warning(f"Failed to auto-update display name: {e}")

    # 1. 關鍵字觸發：價目表 (優先攔截)
    # 只要訊息包含這些字，就直接丟漂亮的卡片，不經過 Gemini
    price_keywords = ["收費", "費用", "價錢", "價目", "多少錢", "價格"]
    if any(k in user_msg for k in price_keywords):
        flex_msg = get_price_flex()
        messages = [flex_msg]
        if user_id in user_images and len(user_images[user_id]) > 0:
            user_images[user_id] = []
            messages.append(TextSendMessage(text="⚠️ 已為您中斷先前的文物健檢流程（未扣除額度）。"))
        line_bot_api.reply_message(event.reply_token, messages)
        return
        
    buy_keywords = ["購買", "儲值", "點數", "方案", "付費", "訂閱"]
    if any(k in user_msg for k in buy_keywords):
        # 解決 Flask Context 失效問題 (這是背景執行緒)
        railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        if railway_domain:
            host = f"https://{railway_domain}"
        else:
            host = "http://localhost:8080" # 備用
            
        flex_msg = get_subscription_flex(host, user_id)
        messages = [flex_msg]
        if user_id in user_images and len(user_images[user_id]) > 0:
            user_images[user_id] = []
            messages.append(TextSendMessage(text="⚠️ 已為您中斷先前的文物健檢流程（未扣除額度）。"))
        line_bot_api.reply_message(event.reply_token, messages)
        return
        
    quota_keywords = ["查詢額度", "額度", "我的狀態", "會員狀態"]
    if any(k in user_msg for k in quota_keywords):
        from datetime import datetime, timezone, timedelta
        tz_tw = timezone(timedelta(hours=8))
        now = datetime.now(tz_tw)
        month_str = f"{now.year}-{now.month:02d}"
        
        user_state = database.get_user_status_data(user_id, month_str)
        free_limit = int(user_state.get('free_limit', 3))
        usage = int(user_state.get('usage', 0))
        purchased = int(user_state.get('purchased', 0))
        tier = user_state.get('tier', 'FREE')
        expiry = user_state.get('expiry', '無') or '無'
        
        rem_free = max(0, free_limit - usage)
        discounts = {'FREE': '無折扣', 'BASIC': '折抵 100 元', 'ADVANCED': '折抵 200 元', 'BUSINESS': '折抵 300 元'}
        disc_text = discounts.get(tier, '無折扣')
        
        msg_text = (
            f"👤 您的會員狀態：\n"
            f"🔸 當前方案：{tier}\n"
            f"🔸 包月到期日：{expiry}\n"
            f"🔸 預約人工鑑定專屬折扣：{disc_text}\n\n"
            f"📊 您的健檢剩餘可用額度：\n"
            f"🎁 本月專屬額度：{rem_free} / {free_limit} 次\n"
            f"🪙 永久買斷點數：{purchased} 點\n\n"
            f"💡 若額度不足，請輸入「購買」瀏覽升級方案。"
        )
        messages = [TextSendMessage(text=msg_text)]
        if user_id in user_images and len(user_images[user_id]) > 0:
            user_images[user_id] = []
            messages.append(TextSendMessage(text="⚠️ 已為您中斷先前的文物健檢流程（未扣除額度）。"))
        line_bot_api.reply_message(event.reply_token, messages)
        return
        
    # 0. 解除訂閱/退訂 (導向真人客服)
    cancel_keywords = ["解除訂閱", "取消訂閱", "退訂", "取消方案"]
    if any(k in user_msg for k in cancel_keywords):
        database.set_user_mode(user_id, "HUMAN")
        msg = (
            "⚠️ 訂閱方案變更與解除\n\n"
            "為了保護您的帳號與金流安全，解除訂閱或退訂需要由官方客服專員為您人工處理。\n\n"
            "請點擊下方連結加入官方 LINE，並告知您欲「解除訂閱」，同仁將馬上協助您辦理手續：\n"
            "Line ID: @640aodur\n"
            "連結: https://line.me/R/ti/p/@640aodur"
        )
        messages = [TextSendMessage(text=msg)]
        if user_id in user_images and len(user_images[user_id]) > 0:
            user_images[user_id] = []
            messages.append(TextSendMessage(text="⚠️ 已為您中斷先前的文物健檢流程（未扣除額度）。"))
        line_bot_api.reply_message(event.reply_token, messages)
        return
    # 1. 偵測是否要「切換人工」 (配合你的圖文選單按鈕)
    if user_msg in ["人工預約", "人工客服", "專人服務", "真人客服", "預約送檢"]:
        database.set_user_mode(user_id, "HUMAN")
        flex_msg = get_booking_guide_flex()
        text_msg = TextSendMessage(
            text="請點擊下方連結或搜尋 ID 加好友，並發送物件照片與預約訊息：\n"
                 "Line ID: @640aodur\n"
                 "連結: https://line.me/R/ti/p/@640aodur"
        )
        messages = [flex_msg, text_msg]
        if user_id in user_images and len(user_images[user_id]) > 0:
            user_images[user_id] = []
            messages.append(TextSendMessage(text="⚠️ 已為您中斷先前的文物健檢流程（未扣除額度）。"))
        line_bot_api.reply_message(event.reply_token, messages)
        return

    # 2. 偵測是否要「切換回 AI」
    elif user_msg in ["AI文物健檢", "結束專人", "開啟智能客服"]:
        if check_quota_and_notify(user_id, event.reply_token):
            return
        database.set_user_mode(user_id, "AI")
        msg = (
            "🤖 歡迎使用【AI文物健檢】服務！\n\n"
            "請直接傳送您的「物件照片」與「文字說明」，我將為您進行初步分析。\n\n"
            "⚠️ 【重要提醒】\n"
            "1. AI文物健檢乃基於資料庫與市場資訊，仍有較高誤差值，不具任何鑑定效益，僅供藏家初步過濾使用。\n"
            "2. 單次上傳的照片，請確保只包含「同一件」物件，以免造成AI誤判。\n"
            "3. 單次健檢照片上傳上限為 8 張，若超出限制將無法再新增照片。\n\n"
            "若AI評估機率較高，建議您後續點選「人工預約」進行實體鑑定！"
        )
        messages = [TextSendMessage(text=msg)]
        if user_id in user_images and len(user_images[user_id]) > 0:
            user_images[user_id] = []
            messages.append(TextSendMessage(text="⚠️ 已為您中斷先前的文物健檢流程並清空暫存（未扣除額度）。"))
        line_bot_api.reply_message(event.reply_token, messages)
        return

    # 3. 核心邏輯：預設為 HUMAN（靜音），需主動點選「AI文物健檢」才啟用 AI
    current_mode = database.get_user_mode(user_id)

    # 防呆機制：只要輸入「開始健檢」，強制切換至 AI 模式
    if user_msg == "開始健檢":
        if check_quota_and_notify(user_id, event.reply_token):
            return
        database.set_user_mode(user_id, "AI")
        current_mode = "AI"

    if current_mode == "HUMAN":
        # 人工模式下完全靜音，讓真人透過 LINE 後台回覆
        print(f"人工模式中，忽略訊息: {user_msg}")
        return

    elif current_mode == "AI":
        # --- 新增防呆機制：觸發健檢 ---
        if user_msg == "開始健檢":
            # 檢查是否有上傳照片
            if user_id not in user_images or len(user_images[user_id]) == 0:
                msg = (
                    "🤖 歡迎使用【AI文物健檢】服務！\n\n"
                    "請直接傳送您的「物件照片」與「文字說明」，我將為您進行初步分析。\n\n"
                    "⚠️ 【重要提醒】\n"
                    "1. AI文物健檢乃基於資料庫與市場資訊，仍有較高誤差值，不具任何鑑定效益，僅供藏家初步過濾使用。\n"
                    "2. 單次上傳的照片，請確保只包含「同一件」物件，以免造成AI誤判。\n"
                    "3. 單次健檢照片上傳上限為 8 張，若超出限制將無法再新增照片。\n\n"
                    "若AI評估機率較高，建議您後續點選「人工預約」進行實體鑑定！"
                )
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
                return
            
            # ---- 獲取用戶方案資訊 ----
            from datetime import datetime, timezone, timedelta
            tz_tw = timezone(timedelta(hours=8))
            now = datetime.now(tz_tw)
            month_str = f"{now.year}-{now.month:02d}"
            user_state = database.get_user_status_data(user_id, month_str)
            tier = user_state.get('tier', 'FREE')
            
            try:
                # 告知用戶正在處理
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🔍 系統正在分析您的照片，請稍候... (您的方案：{tier})"))
                
                # 圖片分析改用 generate_content
                prompt = "請根據這些照片，嚴格依照【AI文物健檢規則與原則】與【Response Format】進行分析。"
                
                # 構建新版 SDK payload，將圖片字典轉為 types.Part.from_bytes
                payload = [prompt]
                first_image_bytes = None
                for item in user_images[user_id]:
                    if isinstance(item, dict) and "data" in item:
                        if first_image_bytes is None:
                            first_image_bytes = item["data"]
                        payload.append(types.Part.from_bytes(
                            data=item["data"],
                            mime_type=item.get("mime_type", "image/jpeg")
                        ))
                    else:
                        payload.append(item)
                        
                response = client.models.generate_content(
                    model=gemini_model_name,
                    contents=payload,
                    config=gemini_config
                )
                
                resp_text = response.text
                title = "古文物珍品"
                prob = "75%"
                valuation = "TWD 10萬~15萬"
                
                # 嘗試找尋 ###DATA:{...}###
                data_match = re.search(r"###DATA:(\{.*?\})###", resp_text)
                if data_match:
                    try:
                        data_json = json.loads(data_match.group(1))
                        title = data_json.get("title", title)
                        prob = data_json.get("prob", prob)
                        valuation = data_json.get("valuation", valuation)
                    except:
                        pass
                    # 將 DATA 標籤自給用戶顯示的文字中移除
                    resp_text = resp_text.replace(data_match.group(0), "").strip()

                # 使用正則從文字中提取以確保跟文字完全一致 (優先覆蓋)
                prob_m = re.search(r"真品機率評估為：.*?(\d+\s*%)", resp_text)
                if prob_m:
                    prob = prob_m.group(1)
                
                title_m = re.search(r"分析為一件[「\[]*(.*?)[」\]]*其當前市場參考價值", resp_text)
                if title_m:
                    title = title_m.group(1).strip()
                    
                price_m = re.search(r"當前市場參考價值約落在[「\[]*(.*?)[」\]]*[。\n]", resp_text)
                if price_m:
                    valuation = price_m.group(1).strip()

                # 獲取使用者 LINE 暱稱作為健檢操作者
                display_name = "VIP 藏家"
                try:
                    profile = line_bot_api.get_profile(user_id)
                    display_name = profile.display_name
                except Exception as e:
                    app.logger.warning(f"Failed to fetch LINE profile display name: {e}")

                # 判斷是否為拒絕受理的物件
                is_rejected = "您所上傳的照片不在檢測項目內" in resp_text
                
                quota_consumed = False
                was_purchased_quota = False

                if not is_rejected:
                    card_filename = ig_card_generator.generate_ig_card(
                        user_id, title, prob, valuation, first_image_bytes, user_name=display_name
                    )
                    # ---- 實際扣除使用次數 ----
                    success, rem_free, rem_purchased, was_purchased = database.consume_quota(user_id, month_str)
                    if success:
                        quota_consumed = True
                        was_purchased_quota = was_purchased
                    quota_suffix = f"\n\n---\n📊 目前剩餘可健檢額度：\n🎁 本月免費/訂閱額度：{rem_free} 次\n🪙 單筆儲值備用點數：{rem_purchased} 點"
                    
                    railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
                    if railway_domain:
                        host_url = f"https://{railway_domain}"
                    else:
                        from flask import has_request_context
                        if has_request_context():
                            host_url = request.host_url.rstrip("/")
                        else:
                            host_url = "http://localhost:8080"
                    card_url = f"{host_url}/cards/{card_filename}"

                    # ---- 寫入歷史健檢資料 (防禦性異常容錯) ----
                    try:
                        cat = classify_category(title, resp_text)
                        prob_num = 75
                        prob_clean = prob.replace("%", "").strip()
                        if prob_clean.isdigit():
                            prob_num = int(prob_clean)
                        val_min, val_max = parse_valuation_numeric(valuation)
                        database.add_diagnosis_record(user_id, display_name, cat, title, prob_num, valuation, val_min, val_max, card_filename)
                    except Exception as record_err:
                        app.logger.error(f"Failed to save diagnosis record: {record_err}")
                
                # 清空該用戶的暫存照片
                user_images[user_id] = []
                
                # LINE 單則訊息上限 5000 字，超過需要拆分
                MAX_LEN = 4800  # 留緩衝給 quota_suffix
                messages_to_send = []
                
                if len(resp_text) <= MAX_LEN:
                    # 文字足夠短，直接一則送出
                    messages_to_send.append(TextSendMessage(text=resp_text + quota_suffix))
                else:
                    # 將 resp_text 切成多段，每段不超過 4800 字
                    chunks = []
                    remaining = resp_text
                    while remaining:
                        if len(remaining) <= MAX_LEN:
                            chunks.append(remaining)
                            break
                        # 嘗試在最近的換行符切割
                        cut_pos = remaining.rfind('\n', 0, MAX_LEN)
                        if cut_pos == -1:
                            cut_pos = MAX_LEN
                        chunks.append(remaining[:cut_pos])
                        remaining = remaining[cut_pos:].lstrip('\n')
                    
                    # 第一段直接送出
                    for i, chunk in enumerate(chunks):
                        if i == len(chunks) - 1:
                            # 最後一段附加額度資訊
                            messages_to_send.append(TextSendMessage(text=chunk + quota_suffix))
                        else:
                            messages_to_send.append(TextSendMessage(text=chunk))
                
                if card_url:
                    messages_to_send.append(ImageSendMessage(original_content_url=card_url, preview_image_url=card_url))
                
                line_bot_api.push_message(
                    user_id,
                    messages_to_send
                )
                
                # 健檢結束後，自動切換回人工模式，避免影響後續對話或動作
                database.set_user_mode(user_id, "HUMAN")
                return
                
            except Exception as e:
                import traceback
                print(f"Gemini Analysis Error: {e}")
                print(traceback.format_exc())
                
                # ---- 發生錯誤時安全退還已扣除的額度 (回滾) ----
                if quota_consumed:
                    try:
                        database.refund_quota(user_id, month_str, was_purchased_quota)
                        print(f"[Quota Rollback] Successfully refunded quota for user {user_id}")
                    except Exception as refund_err:
                        print(f"[Quota Rollback] Failed to refund quota: {refund_err}")
                
                # ---- 安全發送錯誤訊息通知 ----
                try:
                    # 避免 429 超限時重複呼叫 push_message 導致再次崩潰
                    is_line_limit = "monthly limit" in str(e) or (hasattr(e, "status_code") and e.status_code == 429)
                    if is_line_limit:
                        print(f"LINE monthly limit reached. Skipping error notification push to {user_id}")
                    else:
                        line_bot_api.push_message(user_id, TextSendMessage(text="抱歉，A.A.D 系統分析過程中發生錯誤，請稍後再試。"))
                except Exception as push_err:
                    print(f"Failed to send error notification: {push_err}")
                
                # 發生錯誤也務必清空暫存，並切回人工模式，以防用戶卡死
                user_images[user_id] = []
                database.set_user_mode(user_id, "HUMAN")
                return

        # 將用戶輸入的文字視為物件說明加入暫存
        if user_id not in user_images:
            user_images[user_id] = []
        user_images[user_id].append(user_msg)
        
        # 統計目前暫存庫內數量
        img_count = sum(1 for item in user_images[user_id] if isinstance(item, dict))
        text_count = sum(1 for item in user_images[user_id] if isinstance(item, str))
        
        msg = f"📝 已收到您的文字說明 (目前暫存 {img_count} 張照片, {text_count} 則說明)。\n\n請問還有其他要補充的照片或描述嗎？\n若已傳送完畢，請再點擊『開始健檢』以取得分析結果。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    current_mode = database.get_user_mode(user_id)

    # 自動更新/保存使用者暱稱
    try:
        stored_name = database.get_user_display_name(user_id)
        if not stored_name:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
            database.update_user_display_name(user_id, display_name)
    except Exception as e:
        app.logger.warning(f"Failed to auto-update display name: {e}")

    try:
        # 檢查照片數量上限 (上限為 8 張)
        if user_id in user_images:
            img_count = sum(1 for item in user_images[user_id] if isinstance(item, dict))
            if img_count >= 8:
                if current_mode == "AI":
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="⚠️ 單次文物健檢的照片上限為 8 張，已達上限，無法再新增照片。\n若已上傳完畢，請輸入『開始健檢』。\n\n（系統將以前 8 張照片進行分析，且仍會扣除健檢額度）")
                    )
                return

        # 取得圖片內容 (不論在哪個模式，都先暫存起來，防呆)
        message_content = line_bot_api.get_message_content(event.message.id)
        image_bytes = b""
        for chunk in message_content.iter_content():
            image_bytes += chunk

        # 構建 Gemini 支援的圖片格式
        image_part = {
            "mime_type": "image/jpeg",
            "data": image_bytes
        }

        # 存入該用戶的暫存區
        if user_id not in user_images:
            user_images[user_id] = []
        user_images[user_id].append(image_part)

        # 統計目前暫存庫內數量
        img_count = sum(1 for item in user_images[user_id] if isinstance(item, dict))
        text_count = sum(1 for item in user_images[user_id] if isinstance(item, str))

        # 只有在 AI 模式下，才回覆確認訊息 (人工模式下保持靜音，但照片已偷偷存好)
        if current_mode == "AI":
            if check_quota_and_notify(user_id, event.reply_token):
                # 清空該用戶的暫存照片並退回人工模式
                user_images[user_id] = []
                database.set_user_mode(user_id, "HUMAN")
                return
            msg = f"✅ 已收到照片 (目前暫存 {img_count} 張照片, {text_count} 則說明)。\n\n請問還有其他角度（如底部、特寫）或文字補充嗎？\n若已傳送完畢，請再點擊『開始健檢』以取得分析結果。。"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

    except Exception as e:
        print(f"Image Receive Error: {e}")
        # 如果是 AI 模式才報錯，人工模式報錯會干擾對話
        if current_mode == "AI":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="抱歉，圖片接收失敗，請重新傳送。"))



@app.route("/admin/lookup/<order_id>")
def admin_lookup(order_id):
    order_info = database.get_payment_order(order_id)
    if not order_info:
        return f"<h3>找不到此商店訂單編號: {order_id}</h3>", 404
        
    user_id = order_info['user_id']
    plan_id = order_info['plan_id']
    
    from datetime import datetime, timezone, timedelta
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    month_str = f"{now.year}-{now.month:02d}"
    user_state = database.get_user_status_data(user_id, month_str)
    
    html = f"""
    <h2>🔍 訂單與客戶對照結果</h2>
    <p><b>商店訂單編號 (Order ID):</b> {order_id}</p>
    <p><b>客戶 LINE User ID:</b> {user_id}</p>
    <p><b>訂購方案 (Plan ID):</b> {plan_id}</p>
    <hr>
    <h3>📊 目前該用戶在資料庫的狀態：</h3>
    <p><b>目前方案等級:</b> {user_state.get('tier', 'FREE')}</p>
    <p><b>當月方案已用額度:</b> {user_state.get('usage', 0)} 次</p>
    <p><b>儲值備用點數:</b> {user_state.get('purchased', 0)} 點</p>
    <p><b>當前客服狀態:</b> {user_state.get('current_mode', 'HUMAN')}</p>
    <p><b>方案到期時間:</b> {user_state.get('expiry', '無')}</p>
    """
    return html

@app.route("/admin/upgrade/<user_id>/<tier>")
def admin_upgrade(user_id, tier):
    if tier not in ["BASIC", "ADVANCED", "BUSINESS", "FREE"]:
        return "無效的方案等級", 400
        
    database.update_subscription(user_id, tier)
    
    # 取得最新額度資訊
    from datetime import datetime, timezone, timedelta
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw)
    month_str = f"{now.year}-{now.month:02d}"
    user_state = database.get_user_status_data(user_id, month_str)
    free_limit = int(user_state.get('free_limit', 3))
    usage = int(user_state.get('usage', 0))
    purchased = int(user_state.get('purchased', 0))
    
    rem_free = max(0, free_limit - usage)
    
    msg_text = f"🎉 [系統更新] 感謝您的訂閱！會員方案已開通/升級。\n(提醒：一個帳號僅能訂閱一個方案，如需更多額度請加購「單筆儲值」點數)\n---\n📊 目前最新額度狀態：\n⭐ 會員方案：{tier}\n🎁 當月方案額度剩餘：{rem_free} 次\n🪙 終身可用儲值點數：{purchased} 點"
    
    try:
        line_bot_api.push_message(user_id, TextSendMessage(text=msg_text))
    except Exception as e:
        app.logger.error(f"Push message failed: {e}")
        
    return f"<h3>成功將用戶 {user_id} 變更為 {tier}！已發送 LINE 通知。</h3>"

@app.route("/admin/debug_user/<user_id>")
def admin_debug_user(user_id):
    import datetime
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    server_now = datetime.datetime.now(tz_tw)
    conn = database.get_connection()
    if not conn:
        return "無法連線資料庫", 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return f"找不到此用戶。伺服器時間為: {server_now}", 404
            # 轉換為 dict
            data = dict(row)
            return f"<h3>用戶 {user_id} 的原始資料庫資料：</h3><pre>{data}</pre><p>伺服器目前時間: {server_now}</p>"
    finally:
        conn.close()

# ==========================================
# 后台管理系統 (Admin Dashboard)
# ==========================================

def render_admin(logged_in=False, error=None):
    users = []
    orders = []
    analytics_json = "{}"
    if logged_in:
        users = database.get_all_users()
        orders = database.get_all_payment_orders()
        
        # 尋找 display_name 為空的使用者，並從 LINE API 補載入與更新資料庫
        updated_any = False
        for u in users:
            if not u.get('display_name'):
                try:
                    profile = line_bot_api.get_profile(u['user_id'])
                    database.update_user_display_name(u['user_id'], profile.display_name)
                    u['display_name'] = profile.display_name
                    updated_any = True
                except Exception as e:
                    app.logger.warning(f"Failed to fetch LINE profile for {u['user_id']}: {e}")
                    
        if updated_any:
            orders = database.get_all_payment_orders()
            
        try:
            analytics = database.get_analytics_summary()
            import json
            analytics_json = json.dumps(analytics, ensure_ascii=False)
        except Exception as e:
            app.logger.error(f"Failed to fetch analytics: {e}")
    try:
        with open("admin.html", "r", encoding="utf-8") as f:
            template_content = f.read()
        return render_template_string(template_content, logged_in=logged_in, error=error, users=users, orders=orders, analytics_json=analytics_json)
    except Exception as e:
        return f"讀取 admin.html 範本發生錯誤: {e}", 500

@app.route("/admin", methods=["GET"])
def admin_page():
    logged_in = session.get("admin_logged_in", False)
    return render_admin(logged_in=logged_in)

@app.route("/admin/login", methods=["POST"])
def admin_login():
    password = request.form.get("password")
    admin_password = os.getenv("ADMIN_PASSWORD", "1931sf1164")
    if password == admin_password:
        session["admin_logged_in"] = True
        return redirect("/admin")
    else:
        return render_admin(logged_in=False, error="密碼錯誤，請重新輸入！")

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect("/admin")

@app.route("/admin/api/toggle_mode", methods=["POST"])
def admin_api_toggle_mode():
    if not session.get("admin_logged_in", False):
        return jsonify({"success": False, "message": "未授權"}), 403
    
    data = request.get_json() or {}
    user_id = data.get("user_id")
    mode = data.get("mode")
    if not user_id or mode not in ["AI", "HUMAN"]:
        return jsonify({"success": False, "message": "無效參數"}), 400
        
    try:
        database.set_user_mode(user_id, mode)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/admin/api/upgrade", methods=["POST"])
def admin_api_upgrade():
    if not session.get("admin_logged_in", False):
        return jsonify({"success": False, "message": "未授權"}), 403
    
    data = request.get_json() or {}
    user_id = data.get("user_id")
    tier = data.get("tier")
    points = data.get("points", 0)
    expiry = data.get("expiry")
    usage_count = data.get("usage_count")
    usage_month = data.get("usage_month")
    
    if not user_id or tier not in ["BASIC", "ADVANCED", "BUSINESS", "FREE", "ADMIN"]:
        return jsonify({"success": False, "message": "參數不正確"}), 400
        
    try:
        # 轉換已使用次數
        try:
            usage_val = int(usage_count) if usage_count is not None else None
        except ValueError:
            usage_val = None

        # 手動更新使用者狀態
        database.manual_update_user(user_id, tier, points, expiry, usage_count=usage_val, usage_month=usage_month)
        
        # 取得最新額度資訊並推播通知
        from datetime import datetime, timezone, timedelta
        tz_tw = timezone(timedelta(hours=8))
        now = datetime.now(tz_tw)
        month_str = f"{now.year}-{now.month:02d}"
        
        # 若有指定月份，以指定月份查詢最新額度
        query_month = usage_month[:7] if (usage_month and len(usage_month) >= 7) else month_str
        user_state = database.get_user_status_data(user_id, query_month)
        free_limit = int(user_state.get('free_limit', 3))
        usage = int(user_state.get('usage', 0))
        purchased = int(user_state.get('purchased', 0))
        
        rem_free = max(0, free_limit - usage)
        rem_free_str = "無限制" if tier == "ADMIN" else f"{rem_free} 次"
        msg_text = f"🎉 [系統更新] 感謝您的訂閱！會員方案已手動開通/升級。\n(提醒：一個帳號僅能訂閱一個方案，如需更多額度請加購「單筆儲值」點數)\n---\n📊 目前最新額度狀態：\n⭐ 會員方案：{tier}\n🎁 當月方案額度剩餘：{rem_free_str}\n🪙 終身可用儲值點數：{purchased} 點"
        
        try:
            line_bot_api.push_message(user_id, TextSendMessage(text=msg_text))
        except Exception as push_err:
            app.logger.warning(f"Push message failed on manual update: {push_err}")
            
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/admin/api/broadcast", methods=["POST"])
def admin_api_broadcast():
    if not session.get("admin_logged_in", False):
        return jsonify({"success": False, "message": "未授權"}), 403
        
    data = request.get_json() or {}
    message_text = data.get("message", "").strip()
    segment = data.get("segment", "ALL")
    if not message_text:
        return jsonify({"success": False, "message": "訊息內容不可為空"}), 400
        
    try:
        users = database.get_all_users()
        
        # Filter users based on segment
        target_users = []
        for u in users:
            tier = u.get("subscription_tier") or "FREE"
            if segment == "ALL":
                target_users.append(u)
            elif segment == "FREE" and tier == "FREE":
                target_users.append(u)
            elif segment == "SUBSCRIBED" and tier in ["BASIC", "ADVANCED", "BUSINESS"]:
                target_users.append(u)
            elif segment == "BUSINESS" and tier == "BUSINESS":
                target_users.append(u)
                
        user_ids = [u["user_id"] for u in target_users]
        if not user_ids:
            return jsonify({"success": True, "sent_count": 0})
            
        # LINE Multicast 限制單次發送最多 500 個 user ID
        chunk_size = 500
        sent_count = 0
        for i in range(0, len(user_ids), chunk_size):
            chunk = user_ids[i:i + chunk_size]
            try:
                line_bot_api.multicast(chunk, TextSendMessage(text=message_text))
                sent_count += len(chunk)
            except Exception as multicast_err:
                app.logger.error(f"Multicast failed for chunk {i}: {multicast_err}")
                # 若 multicast 失敗，嘗試 fallback 到個別 push_message 確保送達
                for uid in chunk:
                    try:
                        line_bot_api.push_message(uid, TextSendMessage(text=message_text))
                        sent_count += 1
                    except Exception as push_err:
                        app.logger.error(f"Fallback push message failed for {uid}: {push_err}")
                        
        return jsonify({"success": True, "sent_count": sent_count, "target": segment})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/admin/api/user_profile/<user_id>", methods=["GET"])
def admin_api_user_profile(user_id):
    if not session.get("admin_logged_in", False):
        return jsonify({"success": False, "message": "未授權"}), 403
    try:
        diagnoses = database.get_user_diagnoses(user_id)
        orders = database.get_user_payment_orders(user_id)
        return jsonify({
            "success": True,
            "diagnoses": diagnoses,
            "orders": orders
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/admin/api/logs", methods=["GET"])
def admin_api_logs():
    if not session.get("admin_logged_in", False):
        return jsonify({"success": False, "message": "未授權"}), 403
    
    lines = int(request.args.get("lines", 100))
    try:
        app_logs = ""
        err_logs = ""
        if os.path.exists("app.log"):
            with open("app.log", "r", encoding="utf-8") as f:
                app_logs = "".join(f.readlines()[-lines:])
        if os.path.exists("err.log"):
            with open("err.log", "r", encoding="utf-8") as f:
                err_logs = "".join(f.readlines()[-lines:])
        
        return jsonify({
            "success": True,
            "app_logs": app_logs,
            "err_logs": err_logs
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/admin/api/gallery", methods=["GET"])
def admin_api_gallery():
    if not session.get("admin_logged_in", False):
        return jsonify({"success": False, "message": "未授權"}), 403
    limit = int(request.args.get("limit", 100))
    try:
        records = database.get_recent_diagnoses("all", limit=limit)
        return jsonify({
            "success": True,
            "records": records
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/admin/api/analytics", methods=["GET"])
def admin_api_analytics():
    if not session.get("admin_logged_in", False):
        return jsonify({"success": False, "message": "未授權"}), 403
        
    date_range = request.args.get("range", "30days")
    if date_range not in ["today", "7days", "30days", "month", "all"]:
        date_range = "30days"
        
    try:
        summary = database.get_analytics_summary(date_range)
        recent = database.get_recent_diagnoses(date_range, limit=50)
        vip = database.get_vip_leaderboard(limit=10)
        return jsonify({
            "success": True,
            "summary": summary,
            "recent": recent,
            "vip": vip
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/admin/api/export_csv", methods=["GET"])
def admin_api_export_csv():
    if not session.get("admin_logged_in", False):
        return "未授權", 403
        
    date_range = request.args.get("range", "all")
    if date_range not in ["today", "7days", "30days", "month", "all"]:
        date_range = "all"
        
    try:
        records = database.get_recent_diagnoses(date_range, limit=5000)
        
        import csv
        import io
        
        output = io.StringIO()
        output.write('\ufeff')
        
        writer = csv.writer(output)
        writer.writerow([
            "紀錄編號", "LINE使用者ID", "LINE暱稱", "類別", "文物名稱", 
            "真品機率", "估值區間描述", "估值下限(TWD)", "估值上限(TWD)", "鑑定時間"
        ])
        
        for r in records:
            writer.writerow([
                r.get("id"),
                r.get("user_id"),
                r.get("display_name") or "隱藏藏家",
                r.get("category") or "其他",
                r.get("title") or "古文物",
                f"{r.get('probability')}%",
                r.get("valuation_text"),
                r.get("val_min"),
                r.get("val_max"),
                r.get("formatted_date")
            ])
            
        output.seek(0)
        
        response = Response(output.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=aad_analytics_export_{date_range}.csv"
        return response
    except Exception as e:
        return f"匯出 CSV 失敗: {e}", 500

# ==========================================
# 6. 啟動伺服器
#cd /Volumes/Work_Drive/東方森煌共用/Senhuang_linebot
#source venv/bin/activate
#cloudflared tunnel --url http://localhost:5001
#https://receiving-prescription-close-convert.trycloudflare.com
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)