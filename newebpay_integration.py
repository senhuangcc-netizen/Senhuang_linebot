import hashlib
import time
import urllib.parse
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# 藍新測試環境金鑰 (Sandbox)
# 注意：以下為手冊範例 ID，若您有自己的測試帳號，請務必替換為您的商店資訊
MERCHANT_ID = "MS127874575" 
HASH_KEY = "Fs5cX1TGqYM2PpdbE14a9H83YQSQF5jn" 
HASH_IV = "C6AcmfqJILwgnhIP"  

# 藍新 MPG 閘道網址 (測試機)
NEWEBPAY_URL = "https://ccore.newebpay.com/MPG/mpg_gateway"

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
    產生 TradeSha：HashKey=xxx&TradeInfo=xxx&HashIV=xxx 並 SHA256 加密轉大寫
    """
    check_string = f"HashKey={hash_key}&{trade_info}&HashIV={hash_iv}"
    sha256 = hashlib.sha256(check_string.encode('utf-8')).hexdigest()
    return sha256.upper()

def generate_newebpay_form_html(order_id, amount, item_desc, email, notify_url, client_back_url):
    """
    產生藍新支付的自動跳轉表單 (嚴格比照手冊範例排序與參數)
    """
    # 選用手冊最標準的參數集
    params = {
        "MerchantID": MERCHANT_ID,
        "RespondType": "String", # 改用手冊範例的 String
        "TimeStamp": int(time.time()),
        "Version": "2.0",
        "MerchantOrderNo": order_id,
        "Amt": amount,
        "ItemDesc": item_desc,
        "Email": email,
        "LoginType": 0,
        "NotifyURL": notify_url,
    }
    
    # 強制依照 Key 字母排序 (這在計算簽章/加密時非常重要，能確保跨語言一致性)
    sorted_params = dict(sorted(params.items()))
    
    trade_info = create_aes_encrypt(sorted_params, HASH_KEY, HASH_IV)
    trade_sha = create_sha256_hash(trade_info, HASH_KEY, HASH_IV)
    
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

def decrypt_newebpay_response(trade_info_hex, hash_key, hash_iv):
    """
    解密藍新回傳的 TradeInfo
    """
    try:
        # 1. Hex 轉 Bytes
        encrypted_bytes = bytes.fromhex(trade_info_hex)
        
        # 2. AES CBC 解密
        cipher = AES.new(hash_key.encode('utf-8'), AES.MODE_CBC, hash_iv.encode('utf-8'))
        decrypted_padded = cipher.decrypt(encrypted_bytes)
        
        # 3. PKCS7 Unpadding
        decrypted_bytes = unpad(decrypted_padded, 16)
        
        # 4. 解析 Query String 轉回字典
        decrypted_str = decrypted_bytes.decode('utf-8')
        result_params = dict(urllib.parse.parse_qsl(decrypted_str))
        return result_params
    except Exception as e:
        print(f"NewebPay Decrypt Error: {e}")
        return None
