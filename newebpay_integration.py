import hashlib
import time
import os
import urllib.parse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# 藍新正式環境金鑰（從 Railway 環境變數讀取，.strip() 去除可能的空白字元）
MERCHANT_ID = (os.getenv("MERCHANT_ID") or "").strip()
HASH_KEY = (os.getenv("HASH_KEY") or "").strip()
HASH_IV = (os.getenv("HASH_IV") or "").strip()

# 藍新 MPG 閘道網址（正式環境：core，測試環境：ccore）
NEWEBPAY_URL = "https://core.newebpay.com/MPG/mpg_gateway"

def create_aes_encrypt(params_dict, hash_key, hash_iv):
    """
    將參數字典轉成 Query String 後進行 AES 加密 (CBC 模式, PKCS7 Padding)
    """
    # 1. 將字典轉為 Query String
    # 注意：PHP 的 http_build_query 預設使用 RFC 3986 (空格轉為 %20)
    # Python 的 urlencode 預設會將空格轉為 +，這常導致藍新驗證失敗，需指定 quote_via
    url_encoded = urllib.parse.urlencode(params_dict, quote_via=urllib.parse.quote)
    
    # 2. PKCS7 Padding (AES 區塊大小為 16 bytes)
    raw_bytes = url_encoded.encode('utf-8')
    padded_bytes = pad(raw_bytes, 16)
    
    # 3. AES CBC 加密
    cipher = AES.new(hash_key.encode('utf-8'), AES.MODE_CBC, hash_iv.encode('utf-8'))
    encrypted_bytes = cipher.encrypt(padded_bytes)
    
    # 4. 轉為 Hex 字串
    return encrypted_bytes.hex()

def create_sha256_hash(trade_info, hash_key, hash_iv):
    """
    產生 TradeSha：HashKey=xxx&[trade_info_hex]&HashIV=xxx 並 SHA256 加密轉大寫
    手冊規範：此處不可帶 "TradeInfo=" 字樣
    """
    check_string = f"HashKey={hash_key}&{trade_info}&HashIV={hash_iv}"
    sha256 = hashlib.sha256(check_string.encode('utf-8')).hexdigest()
    return sha256.upper()

def generate_newebpay_form_html(order_id, amount, item_desc, email, notify_url, client_back_url):
    """
    產生藍新支付的自動跳轉表單 (嚴格比照手冊規範)
    """
    # 依手冊規範：MerchantID 為 TradeInfo 內含必填參數，且亦需放在表單外層
    params = {
        "MerchantID": MERCHANT_ID,
        "RespondType": "JSON",
        "TimeStamp": int(time.time()),
        "Version": "2.0",
        "MerchantOrderNo": order_id,
        "Amt": amount,
        "ItemDesc": item_desc,
        "LoginType": 0,
    }
    if email:
        params["Email"] = email
        
    params.update({
        "NotifyURL": notify_url,
        "ClientBackURL": client_back_url,
    })
    
    # 強制依照 Key 字母排序
    sorted_params = dict(sorted(params.items()))
    
    # DEBUG LOG：印出加密前的原始字串，方便在 Railway 確認內容
    import urllib.parse as _up
    raw_query = _up.urlencode(sorted_params, quote_via=_up.quote)
    print(f"[NewebPay DEBUG] Raw TradeInfo string: {raw_query}")
    
    # DEBUG LOG：驗證 KEY 長度和頭尾字元（不暴露完整金鑰）
    print(f"[NewebPay DEBUG] MERCHANT_ID: {MERCHANT_ID}")
    print(f"[NewebPay DEBUG] HASH_KEY len={len(HASH_KEY)}, first4={HASH_KEY[:4]!r}, last4={HASH_KEY[-4:]!r}")
    print(f"[NewebPay DEBUG] HASH_IV  len={len(HASH_IV)}, first4={HASH_IV[:4]!r}, last4={HASH_IV[-4:]!r}")
    
    trade_info = create_aes_encrypt(sorted_params, HASH_KEY, HASH_IV)
    
    # DEBUG LOG：印出 TradeSha 計算字串
    check_string = f"HashKey={HASH_KEY}&{trade_info}&HashIV={HASH_IV}"
    print(f"[NewebPay DEBUG] SHA256 check_string length: {len(check_string)}")
    print(f"[NewebPay DEBUG] TradeInfo (hex): {trade_info[:40]}...")
    
    trade_sha = create_sha256_hash(trade_info, HASH_KEY, HASH_IV)
    print(f"[NewebPay DEBUG] TradeSha: {trade_sha}")
    
    # 產生自提交 HTML 表單
    form_html = f'''
    <html>
    <body onload="document.newebpay.submit();">
        <form name="newebpay" method="post" action="{NEWEBPAY_URL}">
            <input type="hidden" name="MerchantID" value="{MERCHANT_ID}">
            <input type="hidden" name="TradeInfo" value="{trade_info}">
            <input type="hidden" name="TradeSha" value="{trade_sha}">
            <input type="hidden" name="Version" value="2.0">
        </form>
        <p>正在引導您至藍新金流支付頁面，請稍候...</p>
    </body>
    </html>
    '''
    return form_html

def generate_newebpay_period_form_html(order_id, amount, desc, email, notify_url, client_back_url):
    """
    產生藍新定期定額 (Credit Card Periodical Payment NPA-B05) 的自提交 HTML 表單
    """
    from datetime import datetime
    
    # 扣款日期：設定為當前月份的今日，例如今日是 21 號，就設定每月 21 號扣款
    today_day = datetime.now().day
    period_point = f"{today_day:02d}"
    
    # 依照定期定額手冊規範的參數格式
    params = {
        "RespondType": "JSON",
        "TimeStamp": int(time.time()),
        "Version": "1.5",
        "LangType": "zh-Tw",
        "MerOrderNo": order_id,
        "ProdDesc": desc,
        "PeriodAmt": int(amount),
        "PeriodType": "M",          # M = 每月扣款
        "PeriodPoint": period_point, # 每月扣款日期 (01~31)
        "PeriodStartType": 2,       # 2 = 立即執行首期委託金額授權
        "PeriodTimes": 99,          # 委託授權總期數 (99 = 未啟用CAU時的實質無上限)
        "PaymentInfo": "Y",         # 顯示付款人姓名、電話、手機等欄位
        "OrderInfo": "N",           # 不顯示收件人資訊欄位
        "EmailModify": 1,           # 允許付款人修改電子信箱
    }
    if email:
        params["PayerEmail"] = email
        
    params.update({
        "NotifyURL": notify_url,    # 每期授權結果通知網址 (幕後 Post)
        "ReturnURL": client_back_url # 首次扣款成功後，Form Post 導回商店頁面
    })
    
    # 強制依照 Key 字母排序以進行加密
    sorted_params = dict(sorted(params.items()))
    
    # 進行 AES256 加密
    post_data = create_aes_encrypt(sorted_params, HASH_KEY, HASH_IV)
    
    # 定期定額 API 傳送端點
    gateway_url = NEWEBPAY_URL.replace("mpg_gateway", "period")
    
    form_html = f'''
    <html>
    <body onload="document.newebpay_period.submit();">
        <form name="newebpay_period" method="post" action="{gateway_url}">
            <input type="hidden" name="MerchantID_" value="{MERCHANT_ID}">
            <input type="hidden" name="PostData_" value="{post_data}">
        </form>
        <p>正在引導您至藍新定期定額安全支付頁面，請稍候...</p>
    </body>
    </html>
    '''
    return form_html

def decrypt_newebpay_period_response(period_hex, hash_key, hash_iv):
    """
    解密藍新定期定額回傳的 Period 密文
    """
    import json
    try:
        clean_hex = period_hex.strip().replace("\n", "").replace("\r", "").replace(" ", "")
        
        # 1. Hex 轉 Bytes
        encrypted_bytes = bytes.fromhex(clean_hex)
        
        # 2. AES CBC 解密
        cipher = AES.new(hash_key.encode('utf-8'), AES.MODE_CBC, hash_iv.encode('utf-8'))
        decrypted_padded = cipher.decrypt(encrypted_bytes)
        
        # 3. PKCS7 Unpadding
        decrypted_bytes = unpad(decrypted_padded, 16)
        
        # 4. 解碼為字串 (安全防錯)
        try:
            decrypted_str = decrypted_bytes.decode('utf-8')
        except UnicodeDecodeError:
            decrypted_str = decrypted_bytes.decode('cp950', errors='ignore')
            
        # 5. 嘗試以 JSON 解析，若失敗則回歸 Query String 解析
        try:
            return json.loads(decrypted_str)
        except Exception:
            return dict(urllib.parse.parse_qsl(decrypted_str))
    except Exception as e:
        import traceback
        print(f"NewebPay Period Decrypt Error: {e}")
        traceback.print_exc()
        return None

def decrypt_newebpay_response(trade_info_hex, hash_key, hash_iv):
    """
    解密藍新回傳的 TradeInfo
    """
    import json
    try:
        clean_hex = trade_info_hex.strip().replace("\n", "").replace("\r", "").replace(" ", "")
        
        # 1. Hex 轉 Bytes
        encrypted_bytes = bytes.fromhex(clean_hex)
        
        # 2. AES CBC 解密
        cipher = AES.new(hash_key.encode('utf-8'), AES.MODE_CBC, hash_iv.encode('utf-8'))
        decrypted_padded = cipher.decrypt(encrypted_bytes)
        
        # 3. PKCS7 Unpadding
        decrypted_bytes = unpad(decrypted_padded, 16)
        
        # 4. 解碼為字串 (安全防錯)
        try:
            decrypted_str = decrypted_bytes.decode('utf-8')
        except UnicodeDecodeError:
            decrypted_str = decrypted_bytes.decode('cp950', errors='ignore')
            
        # 5. 優先以 JSON 解析，失敗則以 Query String 解析
        try:
            return json.loads(decrypted_str)
        except Exception:
            return dict(urllib.parse.parse_qsl(decrypted_str))
            
    except Exception as e:
        import traceback
        print(f"NewebPay Decrypt Error: {e}")
        traceback.print_exc()
        return None
