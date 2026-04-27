import hashlib
import time
import urllib.parse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# 藍新測試環境金鑰 (Sandbox)
MERCHANT_ID = "MS158900594" 
HASH_KEY = "NNQ0KoXoI3sQihl2R48OhOZu8oL6DVNZ" 
HASH_IV = "Cuz9N0Cbfaamhi4P"  

# 藍新 MPG 閘道網址 (測試機)
NEWEBPAY_URL = "https://ccore.newebpay.com/MPG/mpg_gateway"

def create_aes_encrypt(params_dict, hash_key, hash_iv):
    """
    將參數字典轉成 Query String 後進行 AES 加密 (CBC 模式, PKCS7 Padding)
    注意：PHP 的 http_build_query 預設使用 RFC 3986 (空格轉為 %20)
    Python 的 urlencode 預設會將空格轉為 +，需指定 quote_via 避免 SHA 驗證失敗
    """
    url_encoded = urllib.parse.urlencode(params_dict, quote_via=urllib.parse.quote)
    raw_bytes = url_encoded.encode('utf-8')
    padded_bytes = pad(raw_bytes, 16)
    cipher = AES.new(hash_key.encode('utf-8'), AES.MODE_CBC, hash_iv.encode('utf-8'))
    encrypted_bytes = cipher.encrypt(padded_bytes)
    return encrypted_bytes.hex()

def create_sha256_hash(trade_info, hash_key, hash_iv):
    """
    產生 TradeSha：HashKey=xxx&TradeInfo=xxx&HashIV=xxx 並 SHA256 加密轉大寫
    """
    check_string = f"HashKey={hash_key}&{trade_info}&HashIV={hash_iv}"
    sha256 = hashlib.sha256(check_string.encode('utf-8')).hexdigest()
    return sha256.upper()

def generate_newebpay_form_html(order_id, amount, item_desc, email, notify_url, is_period=False):
    """
    產生藍新支付的自動跳轉表單。
    is_period=True 時，額外注入定期定額參數 (每月扣款，共12期)。
    """
    params = {
        "MerchantID": MERCHANT_ID,
        "RespondType": "String",
        "TimeStamp": int(time.time()),
        "Version": "2.0",
        "MerchantOrderNo": order_id,
        "Amt": amount,
        "ItemDesc": item_desc,
        "Email": email,
        "LoginType": 0,
        "NotifyURL": notify_url,
    }

    if is_period:
        # 定期定額必須指定信用卡 (Credit=1)，否則 MPG 不會導向定期定額綁卡頁
        params["Credit"] = 1
        params["PeriodAmt"] = amount        # 每期金額
        params["PeriodType"] = "M"          # 月扣
        params["PeriodPoint"] = "01"        # 每月 1 號
        params["PeriodStartType"] = "2"     # 立即執行委託金額授權
        params["PeriodTimes"] = "12"        # 共 12 期 (一年)
    else:
        # 單筆儲值：開放所有支付方式
        params["Credit"] = 1

    # 強制依照 Key 字母排序確保跨語言一致性
    sorted_params = dict(sorted(params.items()))
    
    trade_info = create_aes_encrypt(sorted_params, HASH_KEY, HASH_IV)
    trade_sha = create_sha256_hash(trade_info, HASH_KEY, HASH_IV)
    
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

def decrypt_newebpay_response(trade_info_hex, hash_key, hash_iv):
    """
    解密藍新回傳的 TradeInfo
    """
    try:
        encrypted_bytes = bytes.fromhex(trade_info_hex)
        cipher = AES.new(hash_key.encode('utf-8'), AES.MODE_CBC, hash_iv.encode('utf-8'))
        decrypted_padded = cipher.decrypt(encrypted_bytes)
        decrypted_bytes = unpad(decrypted_padded, 16)
        decrypted_str = decrypted_bytes.decode('utf-8')
        result_params = dict(urllib.parse.parse_qsl(decrypted_str))
        return result_params
    except Exception as e:
        print(f"NewebPay Decrypt Error: {e}")
        return None
