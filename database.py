import os
import psycopg2
from psycopg2.extras import DictCursor

def get_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("WARNING: DATABASE_URL not found. Database functionality will fail if not deployed on Railway with DB attached.")
        return None
    conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SET TIMEZONE='Asia/Taipei';")
    except Exception as e:
        print(f"Failed to set database session timezone: {e}")
    return conn

def init_db():
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            # 建立使用者表
            # user_id: Line User ID
            # current_mode: AI 或 HUMAN
            # usage_month: 紀錄當前使用月份 (格式 'YYYY-MM')
            # usage_count: 該月份已使用次數
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    current_mode TEXT DEFAULT 'HUMAN',
                    usage_month TEXT,
                    usage_count INTEGER DEFAULT 0
                )
            ''')
            # 擴充新欄位: 購買額度
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS purchased_quota INTEGER DEFAULT 0;")
            # 擴充新欄位: 會員等級
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'FREE';")
            # 擴充新欄位: 訂閱到期日
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expiry TEXT;")
            # 擴充新欄位: LINE暱稱
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;")
            
            # 建立支付訂單對照表 (用於藍新 NotifyURL 不帶參數時的對照)
            cur.execute('''
                CREATE TABLE IF NOT EXISTS payment_orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 擴充欄位以利追蹤實際金流支付狀態
            cur.execute("ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS trade_no TEXT;")
            cur.execute("ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS amount INTEGER;")
            cur.execute("ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'PENDING';")
            cur.execute("ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS pay_time TEXT;")
            
            # 建立 A.A.D 歷史檢測紀錄表
            cur.execute('''
                CREATE TABLE IF NOT EXISTS diagnosis_records (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    display_name TEXT,
                    category TEXT,
                    title TEXT,
                    probability INTEGER,
                    valuation_text TEXT,
                    val_min BIGINT,
                    val_max BIGINT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # 擴充新欄位: 健檢評分卡圖片檔名
            cur.execute("ALTER TABLE diagnosis_records ADD COLUMN IF NOT EXISTS card_filename TEXT;")
            
            # 執行資料庫欄位遷移：將既存的 TIMESTAMP 改為 TIMESTAMPTZ 並指定以 UTC 解析
            cur.execute("""
                SELECT data_type FROM information_schema.columns 
                WHERE table_name = 'diagnosis_records' AND column_name = 'created_at';
            """)
            row = cur.fetchone()
            if row and row['data_type'] == 'timestamp without time zone':
                cur.execute("ALTER TABLE diagnosis_records ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';")
                print("Successfully migrated diagnosis_records.created_at to TIMESTAMPTZ")
                
            cur.execute("""
                SELECT data_type FROM information_schema.columns 
                WHERE table_name = 'payment_orders' AND column_name = 'created_at';
            """)
            row = cur.fetchone()
            if row and row['data_type'] == 'timestamp without time zone':
                cur.execute("ALTER TABLE payment_orders ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';")
                print("Successfully migrated payment_orders.created_at to TIMESTAMPTZ")
            
            # 自動配對與修補歷史紀錄中 card_filename 為 NULL 的項目
            try:
                cur.execute("SELECT id FROM diagnosis_records WHERE card_filename IS NULL ORDER BY id ASC")
                null_rows = cur.fetchall()
                if null_rows and os.path.exists("cards"):
                    card_files = sorted(
                        [f for f in os.listdir("cards") if f.startswith("card_") and f.endswith(".png")],
                        key=lambda x: os.path.getmtime(os.path.join("cards", x))
                    )
                    if card_files:
                        for idx, row in enumerate(null_rows):
                            file_idx = idx % len(card_files)
                            cur.execute("UPDATE diagnosis_records SET card_filename = %s WHERE id = %s", (card_files[file_idx], row['id']))
            except Exception as patch_err:
                print(f"Error retrofitting null card filenames: {patch_err}")
                
        conn.commit()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        conn.close()

def get_user_mode(user_id):
    conn = get_connection()
    if not conn:
        return "AI"  # 預設為 AI
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_mode FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if row and row['current_mode']:
                return row['current_mode']
            return "AI"
    finally:
        conn.close()

def set_user_mode(user_id, mode):
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, current_mode)
                VALUES (%s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET current_mode = EXCLUDED.current_mode
            """, (user_id, mode))
        conn.commit()
    finally:
        conn.close()

def get_user_status_data(user_id, month_str):
    """取得用戶詳細狀態、月用量與相關配額，用於主邏輯判斷"""
    conn = get_connection()
    if not conn:
        return {"tier": "FREE", "free_limit": 3, "usage": 0, "purchased": 0, "current_mode": "HUMAN"}
    try:
        with conn.cursor() as cur:
            # 確認用戶存在
            cur.execute("SELECT current_mode, usage_month, usage_count, purchased_quota, subscription_tier, subscription_expiry FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            
            if not row:
                return {"tier": "FREE", "free_limit": 3, "usage": 0, "purchased": 0, "current_mode": "HUMAN"}
            
            tier = row['subscription_tier'] or 'FREE'
            expiry = row['subscription_expiry']
            
            import datetime
            if expiry:
                try:
                    exp_date = datetime.datetime.strptime(expiry, '%Y-%m-%d %H:%M:%S')
                    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
                    tw_now = datetime.datetime.now(tz_tw).replace(tzinfo=None)
                    if tw_now > exp_date:
                        tier = 'FREE' # 過期退回 FREE
                except:
                    pass

            # 計算當前等級的免費上限
            limits = {'FREE': 3, 'BASIC': 8, 'ADVANCED': 50, 'BUSINESS': 150, 'ADMIN': 99999}
            free_limit = limits.get(tier, 3)

            # 跨月重置邏輯 (僅針對免費方案用戶；付費訂閱用戶的額度跟隨藍新扣款週期重置)
            usage = row['usage_count'] or 0
            db_month = row['usage_month'][:7] if row['usage_month'] else ""
            if db_month != month_str:
                tz_tw = datetime.timezone(datetime.timedelta(hours=8))
                today = datetime.datetime.now(tz_tw)
                if today.strftime('%Y-%m') == month_str:
                    write_date = today.strftime('%Y-%m-%d')
                else:
                    write_date = f"{month_str}-01"

                if tier == 'FREE':
                    usage = 0
                    cur.execute("UPDATE users SET usage_month = %s, usage_count = 0 WHERE user_id = %s", (write_date, user_id))
                    conn.commit()
                else:
                    # 訂閱用戶只更新月份欄位，不重設已使用次數
                    cur.execute("UPDATE users SET usage_month = %s WHERE user_id = %s", (write_date, user_id))
                    conn.commit()

            return {
                "tier": tier,
                "free_limit": free_limit,
                "usage": usage,
                "purchased": row['purchased_quota'] or 0,
                "current_mode": row['current_mode'] or "HUMAN",
                "expiry": expiry
            }
    finally:
        conn.close()

def consume_quota(user_id, month_str):
    """
    動態扣除額度 (優先扣月免費、再扣買斷額度)
    回傳: (is_success, 剩餘月免費用量, 剩餘買斷額度)
    """
    conn = get_connection()
    if not conn:
        return (False, 0, 0, False)
    try:
        # 先取得狀態
        data = get_user_status_data(user_id, month_str)
        free_limit = int(data.get("free_limit", 3))
        usage = int(data.get("usage", 0))
        purchased = int(data.get("purchased", 0))
        
        # 1. 判斷是否有免費額度可扣
        if usage < free_limit:
            new_usage = usage + 1
            new_purchased = purchased
            was_purchased = False
        # 2. 無料可扣，判斷是否有付費額度可扣
        elif purchased > 0:
            new_usage = usage
            new_purchased = purchased - 1
            was_purchased = True
        # 3. 皆無額度
        else:
            return (False, 0, 0, False)

        # 更新資料庫
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users 
                SET usage_count = %s, purchased_quota = %s
                WHERE user_id = %s
            """, (new_usage, new_purchased, user_id))
        conn.commit()
        
        return (True, max(0, free_limit - new_usage), new_purchased, was_purchased)
    finally:
        conn.close()

def refund_quota(user_id, month_str, was_purchased):
    """
    退還扣除的額度 (當健檢後續推送失敗或出錯時回滾)
    """
    conn = get_connection()
    if not conn:
        return
    try:
        data = get_user_status_data(user_id, month_str)
        usage = int(data.get("usage", 0))
        purchased = int(data.get("purchased", 0))
        
        if was_purchased:
            new_usage = usage
            new_purchased = purchased + 1
        else:
            new_usage = max(0, usage - 1)
            new_purchased = purchased
            
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE users 
                SET usage_count = %s, purchased_quota = %s
                WHERE user_id = %s
            """, (new_usage, new_purchased, user_id))
        conn.commit()
    finally:
        conn.close()

def add_purchased_quota(user_id, amount):
    """由綠界 Webhook 若訂單是購買單次額度時呼叫"""
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, purchased_quota)
                VALUES (%s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET purchased_quota = users.purchased_quota + EXCLUDED.purchased_quota
            """, (user_id, amount))
        conn.commit()
    finally:
        conn.close()

def update_subscription(user_id, tier, expiry_str_or_add_months=1):
    """由綠界 Webhook 若訂單是訂閱/包月時呼叫"""
    import datetime
    
    conn = get_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            tz_tw = datetime.timezone(datetime.timedelta(hours=8))
            now = datetime.datetime.now(tz_tw)
            next_month = now + datetime.timedelta(days=30)
            
            if isinstance(expiry_str_or_add_months, str):
                expiry_str = expiry_str_or_add_months
            else:
                expiry_str = next_month.strftime('%Y-%m-%d %H:%M:%S')
                
            today_str = now.strftime('%Y-%m-%d')

            cur.execute("""
                INSERT INTO users (user_id, subscription_tier, subscription_expiry, usage_count, usage_month)
                VALUES (%s, %s, %s, 0, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    subscription_tier = EXCLUDED.subscription_tier,
                    subscription_expiry = EXCLUDED.subscription_expiry,
                    usage_count = 0,
                    usage_month = EXCLUDED.usage_month
            """, (user_id, tier, expiry_str, today_str))
        conn.commit()
    finally:
        conn.close()

def create_payment_order(order_id, user_id, plan_id, amount=0):
    conn = get_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payment_orders (order_id, user_id, plan_id, amount, status) 
                VALUES (%s, %s, %s, %s, 'PENDING')
            """, (order_id, user_id, plan_id, amount))
        conn.commit()
    finally:
        conn.close()

def update_payment_order_status(order_id, status, trade_no=None, pay_time=None, amount=None):
    if order_id and "_" in order_id:
        order_id = order_id.split("_")[0]
    conn = get_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            if amount is not None:
                cur.execute("""
                    UPDATE payment_orders 
                    SET status = %s, trade_no = %s, pay_time = %s, amount = %s 
                    WHERE order_id = %s
                """, (status, trade_no, pay_time, int(amount), order_id))
            else:
                cur.execute("""
                    UPDATE payment_orders 
                    SET status = %s, trade_no = %s, pay_time = %s 
                    WHERE order_id = %s
                """, (status, trade_no, pay_time, order_id))
        conn.commit()
    finally:
        conn.close()

def get_payment_order(order_id):
    if order_id and "_" in order_id:
        order_id = order_id.split("_")[0]
        
    conn = get_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, plan_id FROM payment_orders WHERE order_id = %s", (order_id,))
            return cur.fetchone()
    finally:
        conn.close()

def manual_update_user(user_id, tier, purchased_quota, subscription_expiry, usage_count=None, usage_month=None):
    conn = get_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, subscription_tier, purchased_quota, subscription_expiry, usage_count, usage_month)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    subscription_tier = EXCLUDED.subscription_tier,
                    purchased_quota = EXCLUDED.purchased_quota,
                    subscription_expiry = EXCLUDED.subscription_expiry,
                    usage_count = EXCLUDED.usage_count,
                    usage_month = EXCLUDED.usage_month
            """, (user_id, tier, purchased_quota, subscription_expiry or None, usage_count, usage_month or None))
        conn.commit()
    finally:
        conn.close()

def update_user_display_name(user_id, display_name):
    conn = get_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (user_id, display_name)
                VALUES (%s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET display_name = EXCLUDED.display_name
            """, (user_id, display_name))
        conn.commit()
    finally:
        conn.close()

def get_all_users():
    conn = get_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT user_id, display_name, current_mode, usage_month, usage_count, purchased_quota, subscription_tier, subscription_expiry 
                FROM users 
                ORDER BY 
                    CASE subscription_tier
                        WHEN 'ADMIN' THEN 1
                        WHEN 'BUSINESS' THEN 2
                        WHEN 'ADVANCED' THEN 3
                        WHEN 'BASIC' THEN 4
                        ELSE 5
                    END ASC, 
                    user_id
            """)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()

def get_user_diagnoses(user_id):
    conn = get_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, category, title, probability, valuation_text, val_min, val_max, card_filename, TO_CHAR(created_at, 'YYYY/MM/DD HH24:MI:SS') as formatted_date
                FROM diagnosis_records
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def get_user_payment_orders(user_id):
    conn = get_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT order_id, plan_id, created_at, trade_no, amount, status, pay_time
                FROM payment_orders
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

def get_all_payment_orders():
    conn = get_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.order_id, p.user_id, p.plan_id, p.created_at, p.trade_no, p.amount, p.status, p.pay_time, u.display_name
                FROM payment_orders p
                LEFT JOIN users u ON p.user_id = u.user_id
                ORDER BY p.created_at DESC
            """)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()

def get_user_display_name(user_id):
    conn = get_connection()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT display_name FROM users WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            if row and row['display_name']:
                return row['display_name']
            return None
    finally:
        conn.close()

def add_diagnosis_record(user_id, display_name, category, title, probability, valuation_text, val_min, val_max, card_filename=None):
    conn = get_connection()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO diagnosis_records (user_id, display_name, category, title, probability, valuation_text, val_min, val_max, card_filename)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, display_name, category, title, probability, valuation_text, val_min, val_max, card_filename))
        conn.commit()
    finally:
        conn.close()

def get_analytics_summary(date_range='30days'):
    conn = get_connection()
    if not conn:
        return {"total": 0, "avg_prob": 0, "total_val": 0, "categories": {}, "probabilities": {}, "timeline": []}
        
    time_filter = ""
    if date_range == 'today':
        time_filter = "WHERE created_at >= CURRENT_DATE"
    elif date_range == '7days':
        time_filter = "WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"
    elif date_range == '30days':
        time_filter = "WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'"
    elif date_range == 'month':
        time_filter = "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
    try:
        with conn.cursor() as cur:
            # 1. 基礎指標
            cur.execute(f"SELECT COUNT(*), COALESCE(AVG(probability), 0), COALESCE(SUM(val_max), 0) FROM diagnosis_records {time_filter}")
            row = cur.fetchone()
            total = row[0] or 0
            avg_prob = row[1] or 0
            total_val = row[2] or 0
            
            # 2. 分類統計
            cur.execute(f"SELECT category, COUNT(*) FROM diagnosis_records {time_filter} GROUP BY category")
            categories = {r[0] or "其他": r[1] for r in cur.fetchall()}
            
            # 3. 機率區間統計
            cur.execute(f"""
                SELECT 
                    CASE 
                        WHEN probability < 30 THEN '10%-30%'
                        WHEN probability < 50 THEN '30%-50%'
                        WHEN probability < 70 THEN '50%-70%'
                        WHEN probability < 85 THEN '70%-85%'
                        ELSE '85%-95%'
                    END as prob_range,
                    COUNT(*)
                FROM diagnosis_records
                {time_filter}
                GROUP BY 
                    CASE 
                        WHEN probability < 30 THEN '10%-30%'
                        WHEN probability < 50 THEN '30%-50%'
                        WHEN probability < 70 THEN '50%-70%'
                        WHEN probability < 85 THEN '70%-85%'
                        ELSE '85%-95%'
                    END
            """)
            probabilities = {r[0]: r[1] for r in cur.fetchall()}
            
            # 4. 每日趨勢
            days_interval = "30 days"
            if date_range == '7days':
                days_interval = "7 days"
            elif date_range == 'today':
                days_interval = "1 day"
            elif date_range == 'month':
                days_interval = "31 days"
            elif date_range == 'all':
                days_interval = "90 days"
                
            cur.execute(f"""
                SELECT TO_CHAR(created_at, 'YYYY-MM-DD') as date, COUNT(*)
                FROM diagnosis_records
                WHERE created_at >= CURRENT_DATE - INTERVAL '{days_interval}'
                GROUP BY TO_CHAR(created_at, 'YYYY-MM-DD')
                ORDER BY date ASC
            """)
            timeline = [{"date": r[0], "count": r[1]} for r in cur.fetchall()]
            
            return {
                "total": total,
                "avg_prob": round(float(avg_prob), 1),
                "total_val": int(total_val),
                "categories": categories,
                "probabilities": probabilities,
                "timeline": timeline
            }
    finally:
        conn.close()

def get_recent_diagnoses(date_range='all', limit=50):
    conn = get_connection()
    if not conn: return []
    
    time_filter = ""
    if date_range == 'today':
        time_filter = "WHERE created_at >= CURRENT_DATE"
    elif date_range == '7days':
        time_filter = "WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'"
    elif date_range == '30days':
        time_filter = "WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'"
    elif date_range == 'month':
        time_filter = "WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)"
        
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, user_id, display_name, category, title, probability, valuation_text, val_min, val_max, card_filename, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as formatted_date
                FROM diagnosis_records
                {time_filter}
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()

def get_vip_leaderboard(limit=10):
    conn = get_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.user_id, COALESCE(u.display_name, r.display_name, '隱藏藏家') as display_name, COALESCE(u.subscription_tier, 'FREE') as subscription_tier, COUNT(*) as count
                FROM diagnosis_records r
                LEFT JOIN users u ON r.user_id = u.user_id
                GROUP BY r.user_id, u.display_name, r.display_name, u.subscription_tier
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()
