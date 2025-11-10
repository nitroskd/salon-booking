from fastapi import FastAPI, Request, Form, Depends, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import schedule
from contextlib import contextmanager
from urllib.parse import urlencode
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
import requests
from datetime import datetime, timedelta, date
import pytz
import schedule
import threading
import time
import hashlib
import secrets
import bcrypt

# ========== 環境変数バリデーション ==========

REQUIRED_ENV_VARS = {
    "DATABASE_URL": "PostgreSQL接続URL",
    "ADMIN_USERNAME": "管理者ユーザー名",
    # ADMIN_PASSWORDまたはADMIN_PASSWORD_HASHのどちらかが必須
}

OPTIONAL_ENV_VARS = {
    "SENDGRID_API_KEY": "SendGrid APIキー（メール通知用）",
    "GMAIL_USER": "Gmail送信元アドレス",
    "LINE_CHANNEL_ACCESS_TOKEN": "LINE通知用トークン",
    "LINE_USER_ID": "LINE通知先ユーザーID",
    "BASE_URL": "アプリケーションのベースURL",
    "ENVIRONMENT": "動作環境（production/development）",
}

def validate_env_vars():
    """環境変数をバリデート"""
    print("🔍 環境変数をチェック中...")
    
    missing_vars = []
    
    # 基本的な必須変数のチェック
    for var, description in REQUIRED_ENV_VARS.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append(f"  ❌ {var}: {description}")
        else:
            print(f"  ✅ {var}: 設定済み")
    
    if missing_vars:
        print("\n🚨 以下の必須環境変数が設定されていません:")
        print("\n".join(missing_vars))
        print("\n⚠️  アプリケーションを起動できません")
        sys.exit(1)
    
    # オプション変数の警告
    missing_optional = []
    for var, description in OPTIONAL_ENV_VARS.items():
        value = os.getenv(var)
        if not value:
            missing_optional.append(f"  ⚠️  {var}: {description}")
        else:
            print(f"  ✅ {var}: 設定済み")
    
    if missing_optional:
        print("\n⚠️  以下のオプション環境変数が未設定です（一部機能が制限されます）:")
        print("\n".join(missing_optional))
    
    # セキュリティチェック
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if len(admin_password) < 8:
        print("\n⚠️  セキュリティ警告: ADMIN_PASSWORDは8文字以上を推奨します")
    
    # 環境チェック
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        print("\n🚀 本番環境モードで起動します")
        if not os.getenv("BASE_URL"):
            print("  ⚠️  BASE_URLが未設定です（通知機能で問題が起きる可能性があります）")
    else:
        print("\n🔧 開発環境モードで起動します")
    
    print("\n✅ 環境変数のバリデーション完了\n")

# アプリケーション起動時に実行
validate_env_vars()

# DATABASE_URLを取得（バリデーション後なので安全）
DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ FastAPI初期化
app = FastAPI()

# ✅ 本番・開発問わずすべて許可したいホストをまとめる
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "salon-booking-k54d.onrender.com",  # RenderのURL
        "*.onrender.com",
        "salon-couer.jp",
        "www.salon-couer.jp",
        "localhost"  # 開発用
    ]
)
security = HTTPBasic()

# 環境変数から設定を取得
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # production or development
IS_PRODUCTION = ENVIRONMENT == "production"
    
# Limiterの初期化
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ディレクトリの存在確認と作成
templates_dir = "templates"
static_dir = "static"

if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

templates = Jinja2Templates(directory=templates_dir)

# データベース接続情報
DATABASE_URL = os.getenv("DATABASE_URL")

# 日本時間のタイムゾーンを定義
JST = pytz.timezone('Asia/Tokyo')

def get_jst_now():
    """現在の日本時間を取得"""
    return datetime.now(JST)

@contextmanager
def get_db_connection():
    """データベース接続を安全に管理（日本時間設定付き）"""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        # 接続時に日本時間に設定
        with conn.cursor() as c:
            c.execute("SET TIME ZONE 'Asia/Tokyo'")
        yield conn
    finally:
        conn.close()

# 通知設定
GMAIL_USER = os.getenv("GMAIL_USER")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

# 管理者認証情報（環境変数から取得）
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# 後方互換性: ADMIN_PASSWORD_HASHがあればそれを使用、なければADMIN_PASSWORDを使用
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")
ADMIN_PASSWORD_PLAIN = os.getenv("ADMIN_PASSWORD")  # 後方互換性用

if not ADMIN_PASSWORD_HASH and not ADMIN_PASSWORD_PLAIN:
    print("⚠️  警告: ADMIN_PASSWORD_HASHもADMIN_PASSWORDも設定されていません")

    # パスワード系の特別チェック
    has_hash = os.getenv("ADMIN_PASSWORD_HASH")
    has_plain = os.getenv("ADMIN_PASSWORD")
    
    if not has_hash and not has_plain:
        missing_vars.append(f"  ❌ ADMIN_PASSWORD または ADMIN_PASSWORD_HASH: 管理者パスワード")
    elif has_hash:
        print(f"  ✅ ADMIN_PASSWORD_HASH: 設定済み（推奨）")
        if has_plain:
            print(f"  ⚠️  ADMIN_PASSWORDも設定されていますが、ADMIN_PASSWORD_HASHが優先されます")
    elif has_plain:
        print(f"  ⚠️  ADMIN_PASSWORD: 設定済み（非推奨・平文）")
        print(f"      → bcryptハッシュ化への移行を強く推奨します")    

# セッション管理用（本番環境では Redis などを推奨）
active_sessions = {}

def hash_password(password: str) -> str:
    """パスワードをハッシュ化"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, username: str) -> bool:
    """
    パスワードを検証
    - ADMIN_PASSWORD_HASHがあればbcryptで検証
    - なければ平文比較（後方互換性のため、非推奨）
    """
    if ADMIN_PASSWORD_HASH:
        # bcryptで検証（推奨）
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                ADMIN_PASSWORD_HASH.encode('utf-8')
            )
        except Exception as e:
            print(f"bcrypt検証エラー: {e}")
            return False
    elif ADMIN_PASSWORD_PLAIN:
        # 平文比較（非推奨・後方互換性用）
        print("⚠️  警告: 平文パスワード比較を使用中。ADMIN_PASSWORD_HASHへの移行を推奨します")
        return plain_password == ADMIN_PASSWORD_PLAIN
    else:
        return False

def create_session_token() -> str:
    """セッショントークンを生成"""
    return secrets.token_urlsafe(32)

def verify_admin_session(session_token: str = Cookie(None)) -> bool:
    """セッショントークンを検証（タイムアウトチェック追加）"""
    if not session_token:
        return False
    
    if session_token not in active_sessions:
        return False
    
    # セッションのタイムアウトチェック（24時間）
    session_data = active_sessions[session_token]
    login_time = session_data.get('login_time')
    
    if login_time:
        elapsed = datetime.now() - login_time
        if elapsed.total_seconds() > 86400:  # 24時間経過
            del active_sessions[session_token]
            return False
    
    return True

def send_gmail_notification(booking_data):
    """SendGrid経由でメール通知を送信"""
    if not SENDGRID_API_KEY or not GMAIL_USER:
        print("SendGrid設定が見つかりません")
        return False
    
    try:
        base_url = os.getenv("BASE_URL", "https://salon-booking-k54d.onrender.com")
        admin_url = f"{base_url}/admin"
        
        subject = f"【新規予約】{booking_data['customer_name']}様 - {booking_data['booking_date']}"
        
        html_body = f"""
<html>
<body style="font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; color: #333; line-height: 1.8;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #a3b18a 0%, #879f6f 100%); padding: 20px; border-radius: 10px 10px 0 0;">
            <h2 style="color: white; margin: 0; font-size: 1.3em;">🌿 新しい予約が入りました</h2>
        </div>
        
        <div style="background: #fefbf5; padding: 30px; border: 1px solid #e8e4dc; border-top: none; border-radius: 0 0 10px 10px;">
            <h3 style="color: #6a8f66; margin-top: 0;">予約情報</h3>
            
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="border-bottom: 1px solid #e8e4dc;">
                    <td style="padding: 12px 0; color: #888; width: 100px;">お名前</td>
                    <td style="padding: 12px 0; font-weight: 600;">{booking_data['customer_name']} 様</td>
                </tr>
                <tr style="border-bottom: 1px solid #e8e4dc;">
                    <td style="padding: 12px 0; color: #888;">電話番号</td>
                    <td style="padding: 12px 0; font-weight: 600;">{booking_data['phone_number']}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e8e4dc;">
                    <td style="padding: 12px 0; color: #888;">サービス</td>
                    <td style="padding: 12px 0; font-weight: 600;">{booking_data['service_name']}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e8e4dc;">
                    <td style="padding: 12px 0; color: #888;">予約日</td>
                    <td style="padding: 12px 0; font-weight: 600; color: #6a8f66;">{booking_data['booking_date']}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e8e4dc;">
                    <td style="padding: 12px 0; color: #888;">予約時間</td>
                    <td style="padding: 12px 0; font-weight: 600; color: #6a8f66;">{booking_data['booking_time']}</td>
                </tr>
                <tr>
                    <td style="padding: 12px 0; color: #888; vertical-align: top;">備考</td>
                    <td style="padding: 12px 0;">{booking_data.get('notes', 'なし')}</td>
                </tr>
            </table>
            
            <div style="margin-top: 30px; text-align: center;">
                <a href="{admin_url}" style="display: inline-block; background: linear-gradient(135deg, #a3b18a 0%, #879f6f 100%); color: white; padding: 14px 40px; text-decoration: none; border-radius: 8px; font-weight: 600; box-shadow: 0 4px 12px rgba(163, 177, 138, 0.3);">
                    管理画面で確認する →
                </a>
            </div>
            
            <div style="margin-top: 30px; padding: 15px; background: #f8f6f2; border-radius: 8px; font-size: 0.9em; color: #666;">
                <p style="margin: 0;">このメールは予約システムから自動送信されています。</p>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 20px; color: #999; font-size: 0.85em;">
            <p>© 2025 Salon Coeur</p>
        </div>
    </div>
</body>
</html>
        """
        
        text_body = f"""
新しい予約が入りました。

【予約情報】
お名前: {booking_data['customer_name']} 様
電話番号: {booking_data['phone_number']}
サービス: {booking_data['service_name']}
予約日: {booking_data['booking_date']}
予約時間: {booking_data['booking_time']}
備考: {booking_data.get('notes', 'なし')}

管理画面で確認:
{admin_url}

---
Salon Coeur 予約システム
        """
        
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "personalizations": [{
                "to": [{"email": GMAIL_USER}],
                "subject": subject
            }],
            "from": {"email": GMAIL_USER, "name": "Salon Coeur 予約システム"},
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body}
            ]
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 202:
            print("メール通知を送信しました")
            return True
        else:
            print(f"メール送信エラー: {response.status_code}, {response.text}")
            return False
        
    except Exception as e:
        print(f"メール送信エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_reminder_email(reminder):
    """リマインダーメールを送信"""
    if not SENDGRID_API_KEY or not GMAIL_USER:
        print("SendGrid設定が見つかりません")
        return False
    
    try:
        subject = f"【予約リマインダー】明日のご予約について - Salon Coeur"
        
        html_body = f"""
<html>
<body style="font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; color: #333; line-height: 1.8;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #a3b18a 0%, #879f6f 100%); padding: 20px; border-radius: 10px 10px 0 0;">
            <h2 style="color: white; margin: 0; font-size: 1.3em;">🌿 明日はご予約日です</h2>
        </div>
        
        <div style="background: #fefbf5; padding: 30px; border: 1px solid #e8e4dc; border-top: none; border-radius: 0 0 10px 10px;">
            <p style="font-size: 1.1em; color: #6a8f66; margin-top: 0;">
                {reminder['customer_name']} 様
            </p>
            
            <p style="margin: 20px 0;">
                明日はSalon Coeurのご予約日です。<br>
                お気をつけてお越しくださいませ。
            </p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="border-bottom: 1px solid #e8e4dc;">
                    <td style="padding: 12px 0; color: #888; width: 100px;">予約日</td>
                    <td style="padding: 12px 0; font-weight: 600; color: #6a8f66;">{reminder['booking_date']}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e8e4dc;">
                    <td style="padding: 12px 0; color: #888;">予約時間</td>
                    <td style="padding: 12px 0; font-weight: 600; color: #6a8f66;">{reminder['booking_time']}</td>
                </tr>
                <tr>
                    <td style="padding: 12px 0; color: #888;">サービス</td>
                    <td style="padding: 12px 0; font-weight: 600;">{reminder['service_name']}</td>
                </tr>
            </table>
            
            <div style="margin-top: 30px; padding: 15px; background: #f8f6f2; border-radius: 8px; font-size: 0.9em; color: #666;">
                <p style="margin: 0;">ご不明点がございましたら、お気軽にお問い合わせください。</p>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 20px; color: #999; font-size: 0.85em;">
            <p>© 2025 Salon Coeur</p>
        </div>
    </div>
</body>
</html>
        """
        
        text_body = f"""
{reminder['customer_name']} 様

明日はSalon Coeurのご予約日です。
お気をつけてお越しくださいませ。

【予約情報】
予約日: {reminder['booking_date']}
予約時間: {reminder['booking_time']}
サービス: {reminder['service_name']}

ご不明点がございましたら、お気軽にお問い合わせください。

---
Salon Coeur
        """
        
        url = "https://api.sendgrid.com/v3/mail/send"
        headers = {
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "personalizations": [{
                "to": [{"email": reminder['email']}],
                "subject": subject
            }],
            "from": {"email": GMAIL_USER, "name": "Salon Coeur"},
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body}
            ]
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 202:
            print(f"リマインダーメールを送信しました: {reminder['email']}")
            return True
        else:
            print(f"リマインダー送信エラー: {response.status_code}, {response.text}")
            return False
        
    except Exception as e:
        print(f"リマインダー送信エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_line_notification(booking_data):
    """LINE Messaging APIで予約通知を送信"""
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("LINE Messaging API設定が見つかりません")
        return False
    
    try:
        message = f"""🌿 新しい予約が入りました

👤 {booking_data['customer_name']} 様
📞 {booking_data['phone_number']}
💆 {booking_data['service_name']}
📅 {booking_data['booking_date']} {booking_data['booking_time']}"""
        
        if booking_data.get('notes'):
            message += f"\n📝 {booking_data['notes']}"
        
        base_url = os.getenv("BASE_URL", "https://salon-booking-k54d.onrender.com")
        admin_url = f"{base_url}/admin"
        
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "to": LINE_USER_ID,
            "messages": [
                {
                    "type": "text",
                    "text": message
                },
                {
                    "type": "template",
                    "altText": "管理画面を開く",
                    "template": {
                        "type": "buttons",
                        "text": "予約の詳細を確認しますか？",
                        "actions": [
                            {
                                "type": "uri",
                                "label": "管理画面を開く",
                                "uri": admin_url
                            }
                        ]
                    }
                }
            ]
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            print("LINE通知を送信しました")
            return True
        else:
            print(f"LINE送信エラー: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        print(f"LINE送信エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

@contextmanager
def get_db_connection():
    """データベース接続を安全に管理"""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()

def track_page_view(page_name: str):
    """ページビューを記録"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO page_views (page_name, view_date, view_count)
                    VALUES (%s, CURRENT_DATE, 1)
                    ON CONFLICT (page_name, view_date)
                    DO UPDATE SET view_count = page_views.view_count + 1
                """, (page_name,))
                conn.commit()
    except Exception as e:
        print(f"ページビュー記録エラー: {e}")

def get_page_view_stats():
    """ページビュー統計を取得"""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                today = date.today()
                yesterday = today - timedelta(days=1)
                
                # 当日のビュー数
                c.execute("""
                    SELECT COALESCE(SUM(view_count), 0) as count
                    FROM page_views
                    WHERE view_date = %s
                """, (today,))
                today_views = c.fetchone()['count']
                
                # 前日のビュー数
                c.execute("""
                    SELECT COALESCE(SUM(view_count), 0) as count
                    FROM page_views
                    WHERE view_date = %s
                """, (yesterday,))
                yesterday_views = c.fetchone()['count']
                
                # トータルビュー数
                c.execute("""
                    SELECT COALESCE(SUM(view_count), 0) as count
                    FROM page_views
                """)
                total_views = c.fetchone()['count']
                
                return {
                    'today': int(today_views),
                    'yesterday': int(yesterday_views),
                    'total': int(total_views)
                }
    except Exception as e:
        print(f"統計取得エラー: {e}")
        return {'today': 0, 'yesterday': 0, 'total': 0}

def init_db():
    """データベースとテーブルを初期化"""
    with get_db_connection() as conn:
        with conn.cursor() as c:
            # bookingsテーブル - created_atを日本時間で保存
            c.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    customer_name VARCHAR(100) NOT NULL,
                    phone_number VARCHAR(20) NOT NULL,
                    service_name VARCHAR(100) NOT NULL,
                    booking_date DATE NOT NULL,
                    booking_time TIME NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo'),
                    UNIQUE(booking_date, booking_time)
                )
            """)
            
            # productsテーブル
            c.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    product_name VARCHAR(200) NOT NULL,
                    description TEXT,
                    price DECIMAL(10, 2) NOT NULL,
                    original_price DECIMAL(10, 2),
                    brand VARCHAR(100),
                    category VARCHAR(50),
                    stock_quantity INTEGER DEFAULT 0,
                    image_data TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo'),
                    updated_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo')
                )
            """)
            
            # categoriesテーブル
            c.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    category_name VARCHAR(50) UNIQUE NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo')
                )
            """)
            
            # brandsテーブル
            c.execute("""
                CREATE TABLE IF NOT EXISTS brands (
                    id SERIAL PRIMARY KEY,
                    brand_name VARCHAR(100) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo')
                )
            """)
            
            # remindersテーブル
            c.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    booking_date DATE NOT NULL,
                    booking_time TIME NOT NULL,
                    customer_name VARCHAR(100) NOT NULL,
                    service_name VARCHAR(100) NOT NULL,
                    sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo')
                )
            """)
            
            # page_viewsテーブル
            c.execute("""
                CREATE TABLE IF NOT EXISTS page_views (
                    id SERIAL PRIMARY KEY,
                    page_name VARCHAR(100) NOT NULL,
                    view_date DATE NOT NULL,
                    view_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo'),
                    UNIQUE(page_name, view_date)
                )
            """)

            # available_slotsテーブル（予約可能時間管理）
            c.execute("""
                CREATE TABLE IF NOT EXISTS available_slots (
                    id SERIAL PRIMARY KEY,
                    slot_time TIME NOT NULL UNIQUE,
                    slot_label VARCHAR(20) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo')
                )
            """)
            
            # business_hoursテーブル（営業日管理）
            c.execute("""
                CREATE TABLE IF NOT EXISTS business_hours (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL UNIQUE,
                    is_open BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo')
                )
            """)
            
            # slot_availabilityテーブル（時間枠ごとの有効/無効管理）
            c.execute("""
                CREATE TABLE IF NOT EXISTS slot_availability (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    slot_time TIME NOT NULL,
                    is_available BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo'),
                    updated_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo'),
                    UNIQUE(date, slot_time)
                )
            """)
            
            # servicesテーブル（サービス管理）
            c.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id SERIAL PRIMARY KEY,
                    service_name VARCHAR(100) NOT NULL,
                    description TEXT,
                    price DECIMAL(10, 2) NOT NULL,
                    duration VARCHAR(20),
                    icon VARCHAR(10) DEFAULT '💆',
                    is_popular BOOLEAN DEFAULT FALSE,
                    display_order INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo'),
                    updated_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo')
                )
            """)
            
            # 既存テーブルにカラム追加
            try:
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_data TEXT")
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS original_price DECIMAL(10, 2)")
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS brand VARCHAR(100)")
            except Exception as e:
                print(f"カラム追加スキップ: {e}")
                            
            # デフォルトカテゴリーを追加
            default_categories = ['スキンケア']
            for idx, cat in enumerate(default_categories):
                try:
                    c.execute("""
                        INSERT INTO categories (category_name, display_order)
                        VALUES (%s, %s)
                        ON CONFLICT (category_name) DO NOTHING
                    """, (cat, idx))
                except Exception as e:
                    print(f"デフォルトカテゴリー追加エラー: {e}")
               
            # デフォルト予約時間枠を追加
            default_slots = [
                ('10:00:00', '10:00', 0),
                ('14:00:00', '14:00', 1),
                ('17:00:00', '17:00', 2)
            ]
            for slot_time, slot_label, order in default_slots:
                try:
                    c.execute("""
                        INSERT INTO available_slots (slot_time, slot_label, is_active, display_order)
                        VALUES (%s, %s, TRUE, %s)
                        ON CONFLICT (slot_time) DO NOTHING
                    """, (slot_time, slot_label, order))
                except Exception as e:
                    print(f"デフォルト時間枠追加エラー: {e}")
            
            # デフォルトサービスを追加
            c.execute("SELECT COUNT(*) FROM services")
            if c.fetchone()[0] == 0:
                default_services = [
                    ('シミケア', 'お肌のシミを集中ケア。美白効果の高いトリートメントで透明感のある肌へ。', 8000, '60分', '✨', True, 1),
                    ('フェイシャルWAX', '顔の産毛を丁寧に除去。ワントーン明るい透明肌に仕上げます。', 5000, '40分', '💆', False, 2),
                    ('脳洗浄', 'ヘッドスパで頭皮と心をリフレッシュ。深いリラクゼーションを体験。', 7000, '50分', '🧘', True, 3),
                    ('ピーリング', '古い角質を優しく除去し、つるんとしたなめらか肌へ導きます。', 6000, '45分', '🌟', False, 4),
                    ('ハーブサウナ', '天然ハーブの蒸気で全身デトックス。代謝アップと美肌効果。', 9000, '70分', '🌿', False, 5)
                ]
                
                for service in default_services:
                    c.execute("""
                        INSERT INTO services (service_name, description, price, duration, icon, is_popular, display_order)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, service)
            
            # インデックス作成
            c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(booking_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(booking_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_page_views_date ON page_views(view_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_slot_availability_date ON slot_availability(date)")
            try:
                c.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_services_active ON services(is_active)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_services_order ON services(display_order)")
            except:
                pass
            
            conn.commit()

def send_reminders():
    """前日のリマインダーを送信"""
    try:
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        print(f"リマインダーチェック: {tomorrow}")
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                c.execute("""
                    SELECT * FROM reminders 
                    WHERE booking_date = %s AND sent = FALSE
                """, (tomorrow,))
                reminders = c.fetchall()
                
                print(f"送信するリマインダー数: {len(reminders)}")
                
                for reminder in reminders:
                    try:
                        if send_reminder_email(reminder):
                            c.execute("UPDATE reminders SET sent = TRUE WHERE id = %s", (reminder['id'],))
                            conn.commit()
                            print(f"リマインダー送信完了: ID {reminder['id']}")
                    except Exception as e:
                        print(f"リマインダー送信エラー (ID: {reminder['id']}): {e}")
    except Exception as e:
        print(f"リマインダーチェックエラー: {e}")
        import traceback
        traceback.print_exc()

def run_scheduler():
    """バックグラウンドでスケジュール実行"""
    schedule.every().day.at("09:00").do(send_reminders)
    print("スケジューラー起動: 毎日9:00にリマインダーチェック")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# データベース初期化
init_db()

def migrate_to_jst():
    """既存のテーブルのタイムスタンプを日本時間に移行"""
    print("🔧 データベースを日本時間に移行中...")
    
    with get_db_connection() as conn:
        with conn.cursor() as c:
            # 各テーブルのcreated_atカラムのデフォルト値を変更
            tables_and_columns = [
                ('bookings', ['created_at']),
                ('products', ['created_at', 'updated_at']),
                ('categories', ['created_at']),
                ('brands', ['created_at']),
                ('reminders', ['created_at']),
                ('page_views', ['created_at']),
                ('available_slots', ['created_at']),
                ('business_hours', ['created_at']),
                ('slot_availability', ['created_at', 'updated_at']),
                ('services', ['created_at', 'updated_at'])
            ]
            
            for table, columns in tables_and_columns:
                for column in columns:
                    try:
                        c.execute(f"""
                            ALTER TABLE {table} 
                            ALTER COLUMN {column} 
                            SET DEFAULT (NOW() AT TIME ZONE 'Asia/Tokyo')
                        """)
                        print(f"  ✅ {table}.{column} を日本時間に設定")
                    except Exception as e:
                        print(f"  ⚠️  {table}.{column} のスキップ: {e}")
            
            conn.commit()
    
    print("✅ 移行完了！")

# スケジューラーをバックグラウンドで起動
threading.Thread(target=run_scheduler, daemon=True).start()

# ========== 認証エンドポイント ==========

@app.get("/admin/login", response_class=HTMLResponse)
@limiter.limit("20/minute")  # 1分間に20回まで
def admin_login_page(request: Request):
    """管理画面ログインページ"""
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
@limiter.limit("5/minute")  # 1分間に5回まで（ブルートフォース対策）
async def admin_login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    
    """管理画面ログイン処理"""
    if username == ADMIN_USERNAME and verify_password(password, username):
        session_token = create_session_token()
        active_sessions[session_token] = {
            'username': username,
            'login_time': datetime.now()
        }
        
        redirect_response = RedirectResponse(url="/admin", status_code=303)
        redirect_response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=IS_PRODUCTION,
            samesite="lax",
            max_age=86400,
            path="/"
        )
        return redirect_response
    else:
        return RedirectResponse(url="/admin/login?error=invalid", status_code=303)

@app.get("/admin/logout")
async def admin_logout(response: Response, session_token: str = Cookie(None)):
    """ログアウト処理"""
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]
    
    redirect_response = RedirectResponse(url="/admin/login", status_code=303)
    # Cookieを完全に削除
    redirect_response.delete_cookie(
        key="session_token",
        path="/",
        secure=IS_PRODUCTION,
        samesite="lax"
    )
    return redirect_response

# ========== ページ表示のエンドポイント ==========

@app.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    """ホームページを表示（トップページ）"""
    track_page_view('home')
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/home", response_class=HTMLResponse)
def home_page_redirect(request: Request):
    """/home でもホームページを表示"""
    track_page_view('home')
    return templates.TemplateResponse("home.html", {"request": request})
    
@app.get("/shop", response_class=HTMLResponse)
def shop_page(request: Request):
    """商品一覧ページを表示"""
    track_page_view('shop')
    return templates.TemplateResponse("shop.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, session_token: str = Cookie(None)):
    """管理画面 - 予約管理を表示"""
    if not verify_admin_session(session_token):
        return RedirectResponse(url="/admin/login", status_code=303)
    
    stats = get_page_view_stats()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "stats": stats
    })

@app.get("/admin/products", response_class=HTMLResponse)
async def admin_products_page(request: Request, session_token: str = Cookie(None)):
    """管理画面 - 商品登録ページを表示"""
    if not verify_admin_session(session_token):
        return RedirectResponse(url="/admin/login", status_code=303)
    return templates.TemplateResponse("admin_products.html", {"request": request})

@app.get("/admin/products/list", response_class=HTMLResponse)
async def admin_products_list_page(request: Request, session_token: str = Cookie(None)):
    """管理画面 - 商品一覧管理ページを表示"""
    if not verify_admin_session(session_token):
        return RedirectResponse(url="/admin/login", status_code=303)
    return templates.TemplateResponse("admin_products_list.html", {"request": request})

@app.get("/admin/calendar", response_class=HTMLResponse)
async def admin_calendar_page(request: Request, session_token: str = Cookie(None)):
    """管理画面 - 予約カレンダー管理ページを表示"""
    if not verify_admin_session(session_token):
        return RedirectResponse(url="/admin/login", status_code=303)
    return templates.TemplateResponse("admin_calendar.html", {"request": request})

@app.get("/complete", response_class=HTMLResponse)
def complete_page(request: Request, customer_name: str = "", phone_number: str = "",
                  service_name: str = "", booking_date: str = "", booking_time: str = "", notes: str = ""):
    """予約完了ページを表示"""
    track_page_view('complete')
    return templates.TemplateResponse("complete.html", {
        "request": request, 
        "customer_name": customer_name, 
        "phone_number": phone_number,
        "service_name": service_name, 
        "booking_date": booking_date, 
        "booking_time": booking_time, 
        "notes": notes
    })

@app.get("/booking", response_class=HTMLResponse)
def read_form(request: Request):
    """予約フォームを表示（/booking に移動）"""
    track_page_view('booking_form')
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                # 既存の予約を取得
                c.execute("SELECT booking_date, booking_time FROM bookings ORDER BY booking_date, booking_time")
                booked = c.fetchall()
                
                # 営業日情報を取得（今後3ヶ月分）
                today = date.today()
                three_months_later = today + timedelta(days=90)
                c.execute("""
                    SELECT date, is_open 
                    FROM business_hours
                    WHERE date BETWEEN %s AND %s
                    ORDER BY date
                """, (today, three_months_later))
                business_hours_data = c.fetchall()
                
                # 時間枠ごとの有効/無効情報を取得
                c.execute("""
                    SELECT date, slot_time, is_available
                    FROM slot_availability
                    WHERE date BETWEEN %s AND %s
                    ORDER BY date, slot_time
                """, (today, three_months_later))
                slot_availability_data = c.fetchall()
                
                # 予約可能時間枠を取得
                c.execute("""
                    SELECT slot_time, slot_label, display_order
                    FROM available_slots 
                    WHERE is_active = TRUE
                    ORDER BY display_order, slot_time
                """)
                available_slots = c.fetchall()
                
                # サービス一覧を取得
                c.execute("""
                    SELECT id, service_name, description, price, duration, icon, is_popular
                    FROM services
                    WHERE is_active = TRUE
                    ORDER BY display_order, service_name
                """)
                services = c.fetchall()
        
        # 予約済み時間を辞書形式に変換
        booked_dict = {}
        for booking in booked:
            date_str = booking['booking_date'].strftime('%Y-%m-%d') if hasattr(booking['booking_date'], 'strftime') else str(booking['booking_date'])
            time_str = booking['booking_time'].strftime('%H:%M') if hasattr(booking['booking_time'], 'strftime') else str(booking['booking_time'])
            booked_dict.setdefault(date_str, []).append(time_str)
        
        # 営業日情報を辞書形式に変換
        closed_dates = []
        for bh in business_hours_data:
            if not bh['is_open']:
                date_str = bh['date'].strftime('%Y-%m-%d') if hasattr(bh['date'], 'strftime') else str(bh['date'])
                closed_dates.append(date_str)
        
        # 時間枠の無効化情報を辞書形式に変換
        disabled_slots = {}
        for sa in slot_availability_data:
            date_str = sa['date'].strftime('%Y-%m-%d') if hasattr(sa['date'], 'strftime') else str(sa['date'])
            time_str = sa['slot_time'].strftime('%H:%M') if hasattr(sa['slot_time'], 'strftime') else str(sa['slot_time'])
            if not sa['is_available']:
                if date_str not in disabled_slots:
                    disabled_slots[date_str] = []
                disabled_slots[date_str].append(time_str)
        
        # 時間枠を整形
        time_slots = []
        for slot in available_slots:
            time_str = slot['slot_time'].strftime('%H:%M') if hasattr(slot['slot_time'], 'strftime') else str(slot['slot_time'])
            time_slots.append({
                'value': time_str,
                'label': slot['slot_label']
            })
        
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "booked": booked_dict,
            "closed_dates": closed_dates,
            "disabled_slots": disabled_slots,
            "time_slots": time_slots,
            "services": services
        })
    except Exception as e:
        print(f"予約フォーム表示エラー: {e}")
        import traceback
        traceback.print_exc()
        # エラー時は空のデータで表示
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "booked": {},
            "closed_dates": [],
            "disabled_slots": {},
            "time_slots": [
                {"value": "10:00", "label": "10:00"},
                {"value": "14:00", "label": "14:00"},
                {"value": "17:00", "label": "17:00"}
            ],
            "services": []
        })

@app.get("/admin/services", response_class=HTMLResponse)
async def admin_services_page(request: Request, session_token: str = Cookie(None)):
    """管理画面 - サービス管理ページを表示"""
    if not verify_admin_session(session_token):
        return RedirectResponse(url="/admin/login", status_code=303)
    return templates.TemplateResponse("admin_services.html", {"request": request})
    
# ========== 予約時間枠管理API ==========

@app.get("/available-slots")
def get_available_slots():
    """予約可能時間枠を取得"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute("""
                SELECT * FROM available_slots 
                WHERE is_active = TRUE
                ORDER BY display_order, slot_time
            """)
            slots = c.fetchall()
    return {"slots": slots}

@app.get("/business-hours/{year}/{month}")
async def get_business_hours(year: int, month: int, session_token: str = Cookie(None)):
    """指定月の営業日情報を取得"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as c:
                # 指定月の全日付を取得
                c.execute("""
                    SELECT date, is_open 
                    FROM business_hours
                    WHERE EXTRACT(YEAR FROM date) = %s 
                    AND EXTRACT(MONTH FROM date) = %s
                    ORDER BY date
                """, (year, month))
                hours = c.fetchall()
                
                # 時間枠ごとの有効/無効情報を取得
                c.execute("""
                    SELECT date, slot_time, is_available
                    FROM slot_availability
                    WHERE EXTRACT(YEAR FROM date) = %s 
                    AND EXTRACT(MONTH FROM date) = %s
                    ORDER BY date, slot_time
                """, (year, month))
                slot_data = c.fetchall()
        
        return {
            "business_hours": hours,
            "slot_availability": slot_data
        }
    except Exception as e:
        print(f"営業日取得エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/admin/business-hours")
async def update_business_hours(request: Request, session_token: str = Cookie(None)):
    """営業日を更新"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        data = await request.json()
        date = data['date']
        is_open = data['is_open']
        time_slots = data.get('time_slots', {})  # {slot_time: is_available}
        
        with get_db_connection() as conn:
            with conn.cursor() as c:
                # 営業日情報を更新
                c.execute("""
                    INSERT INTO business_hours (date, is_open)
                    VALUES (%s, %s)
                    ON CONFLICT (date) 
                    DO UPDATE SET is_open = EXCLUDED.is_open
                """, (date, is_open))
                
                # 時間枠ごとの有効/無効を更新
                for slot_time, is_available in time_slots.items():
                    c.execute("""
                        INSERT INTO slot_availability (date, slot_time, is_available, updated_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (date, slot_time)
                        DO UPDATE SET is_available = EXCLUDED.is_available, updated_at = CURRENT_TIMESTAMP
                    """, (date, slot_time, is_available))
                
                conn.commit()
        
        return {"success": True, "message": "営業日を更新しました"}
    except Exception as e:
        print(f"営業日更新エラー: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/admin/available-slots")
async def create_time_slot(request: Request, session_token: str = Cookie(None)):
    """予約時間枠を追加"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        data = await request.json()
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO available_slots (slot_time, slot_label, display_order)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (data['slot_time'], data['slot_label'], data.get('display_order', 0)))
                slot_id = c.fetchone()[0]
                conn.commit()
        
        return {"success": True, "id": slot_id, "message": "時間枠を追加しました"}
    except Exception as e:
        print(f"時間枠追加エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/admin/available-slots/{slot_id}")
async def delete_time_slot(slot_id: int, session_token: str = Cookie(None)):
    """予約時間枠を削除"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM available_slots WHERE id = %s", (slot_id,))
                conn.commit()
        
        return {"success": True, "message": "時間枠を削除しました"}
    except Exception as e:
        print(f"時間枠削除エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ========== 予約API（ユーザー用） ==========

@app.post("/book")
@limiter.limit("10/minute")  # 1分間に10回まで
def book_service(
    request: Request,
    customer_name: str = Form(...),
    phone_number: str = Form(...),
    service_name: str = Form(...),
    booking_date: str = Form(...),
    booking_time: str = Form(...),
    notes: str = Form(default="")
):
    """予約を登録"""
    try:
        # 現在の日本時間を取得
        created_at = get_jst_now()
    
    with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id FROM bookings WHERE booking_date = %s AND booking_time = %s",
                         (booking_date, booking_time))
                if c.fetchone():
                    return RedirectResponse("/booking?error=already_booked", status_code=303)
                
                # 明示的にcreated_atを指定してINSERT
                c.execute("""
                    INSERT INTO bookings 
                    (customer_name, phone_number, service_name, booking_date, booking_time, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (customer_name, phone_number, service_name, booking_date, booking_time, notes, created_at))
                conn.commit()
        
        booking_data = {
            'customer_name': customer_name,
            'phone_number': phone_number,
            'service_name': service_name,
            'booking_date': booking_date,
            'booking_time': booking_time,
            'notes': notes
        }
        
        try:
            send_gmail_notification(booking_data)
        except Exception as e:
            print(f"Gmail通知エラー（無視）: {e}")
        
        try:
            send_line_notification(booking_data)
        except Exception as e:
            print(f"LINE通知エラー（無視）: {e}")
        
        params = urlencode({'customer_name': customer_name, 'phone_number': phone_number,
                           'service_name': service_name, 'booking_date': booking_date,
                           'booking_time': booking_time, 'notes': notes or ''})
       return RedirectResponse(f"/complete?{params}", status_code=303)
    except Exception as e:
        print(f"予約エラー: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse("/booking?error=system", status_code=303)

@app.get("/bookings")
@limiter.limit("60/minute")
def get_bookings(request: Request):
    """予約一覧を取得"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute("""SELECT id, customer_name, phone_number, service_name, 
                       booking_date, booking_time, notes, created_at FROM bookings 
                       ORDER BY booking_date DESC, booking_time DESC""")
            bookings = c.fetchall()
    return {"bookings": bookings}

# ========== 予約管理API（管理者用） ==========

@app.post("/admin/bookings")
@limiter.limit("30/minute")
async def create_booking_admin(request: Request, session_token: str = Cookie(None)):
    """予約を追加（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    data = await request.json()
    try:
        created_at = get_jst_now()
        
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO bookings 
                    (customer_name, phone_number, service_name, booking_date, booking_time, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (data['customer_name'], data['phone_number'], data['service_name'],
                      data['booking_date'], data['booking_time'], data.get('notes', ''), created_at))
                conn.commit()
        return {"success": True, "message": "予約を追加しました"}
    except Exception as e:
        print(f"予約追加エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    
@app.put("/admin/bookings/{booking_id}")
async def update_booking_admin(booking_id: int, request: Request, session_token: str = Cookie(None)):
    """予約を更新（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    data = await request.json()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""UPDATE bookings SET customer_name=%s, phone_number=%s, service_name=%s,
                            booking_date=%s, booking_time=%s, notes=%s WHERE id=%s""",
                         (data['customer_name'], data['phone_number'], data['service_name'],
                          data['booking_date'], data['booking_time'], data.get('notes', ''), booking_id))
                conn.commit()
        return {"success": True, "message": "予約を更新しました"}
    except Exception as e:
        print(f"予約更新エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/admin/bookings/{booking_id}")
async def delete_booking_admin(booking_id: int, session_token: str = Cookie(None)):
    """予約を削除（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
                conn.commit()
        return {"success": True, "message": "予約を削除しました"}
    except Exception as e:
        print(f"予約削除エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    
# ========== 商品API ==========

@app.get("/products")
def get_products(category: str = None, brand: str = None, active_only: bool = True):
    """商品一覧を取得"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            query = "SELECT * FROM products WHERE 1=1"
            params = []
            if active_only:
                query += " AND is_active = %s"
                params.append(True)
            if category:
                query += " AND category = %s"
                params.append(category)
            if brand:
                query += " AND brand = %s"
                params.append(brand)
            query += " ORDER BY category, brand, product_name"
            c.execute(query, params)
            products = c.fetchall()
    return {"products": products}

# カテゴリー管理API
@app.get("/categories")
def get_categories():
    """カテゴリー一覧を取得"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute("SELECT * FROM categories ORDER BY display_order, category_name")
            categories = c.fetchall()
    return {"categories": categories}

@app.post("/admin/categories")
async def create_category(request: Request, session_token: str = Cookie(None)):
    """カテゴリーを追加（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        data = await request.json()
        with get_db_connection() as conn:
            with conn.cursor() as c:
                # 既存のカテゴリーをチェック
                c.execute("SELECT id FROM categories WHERE category_name = %s", (data['category_name'],))
                existing = c.fetchone()
                
                if existing:
                    return JSONResponse(status_code=400, content={"error": "カテゴリーは既に存在します"})
                
                # 新規追加
                c.execute("""
                    INSERT INTO categories (category_name, display_order)
                    VALUES (%s, %s)
                    RETURNING id
                """, (data['category_name'], data.get('display_order', 0)))
                result = c.fetchone()
                conn.commit()
                
                return {"success": True, "message": "カテゴリーを追加しました", "id": result[0]}
    except Exception as e:
        print(f"カテゴリー追加エラー: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/admin/categories/{category_id}")
async def delete_category(category_id: int, session_token: str = Cookie(None)):
    """カテゴリーを削除（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM categories WHERE id = %s", (category_id,))
                conn.commit()
        return {"success": True, "message": "カテゴリーを削除しました"}
    except Exception as e:
        print(f"カテゴリー削除エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ブランド管理API
@app.get("/brands")
def get_brands():
    """ブランド一覧を取得"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute("SELECT * FROM brands ORDER BY brand_name")
            brands = c.fetchall()
    return {"brands": brands}

@app.post("/admin/brands")
async def create_brand(request: Request, session_token: str = Cookie(None)):
    """ブランドを追加（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    data = await request.json()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO brands (brand_name)
                    VALUES (%s)
                    ON CONFLICT (brand_name) DO NOTHING
                    RETURNING id
                """, (data['brand_name'],))
                result = c.fetchone()
                conn.commit()
                if result:
                    return {"success": True, "message": "ブランドを追加しました"}
                else:
                    return JSONResponse(status_code=400, content={"error": "ブランドは既に存在します"})
    except Exception as e:
        print(f"ブランド追加エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/admin/brands/{brand_id}")
async def delete_brand(brand_id: int, session_token: str = Cookie(None)):
    """ブランドを削除（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM brands WHERE id = %s", (brand_id,))
                conn.commit()
        return {"success": True, "message": "ブランドを削除しました"}
    except Exception as e:
        print(f"ブランド削除エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/admin/products/add")
async def create_product_admin(request: Request, product_name: str = Form(...),
                                price: float = Form(...), category: str = Form(...),
                                stock_quantity: int = Form(...), description: str = Form(default=""),
                                image_data: str = Form(...), 
                                original_price: float = Form(None),
                                brand: str = Form(None),
                                session_token: str = Cookie(None)):
    
    """商品を追加（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""INSERT INTO products (product_name, description, price, original_price, brand, category, stock_quantity, image_data)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                         (product_name, description, price, original_price, brand, category, stock_quantity, image_data))
                product_id = c.fetchone()[0]
                conn.commit()
        return {"success": True, "product_id": product_id, "message": "商品を追加しました"}
    except Exception as e:
        print(f"商品追加エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.put("/admin/products/{product_id}")
async def update_product_admin(product_id: int, request: Request, session_token: str = Cookie(None)):
    """商品を更新（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        form_data = await request.form()
        product_name = form_data.get('product_name')
        price = float(form_data.get('price'))
        original_price = form_data.get('original_price')
        original_price = float(original_price) if original_price else None
        brand = form_data.get('brand', None)
        category = form_data.get('category')
        stock_quantity = int(form_data.get('stock_quantity'))
        description = form_data.get('description', '')
        image_data = form_data.get('image_data', '')
        
        with get_db_connection() as conn:
            with conn.cursor() as c:
                if image_data:
                    c.execute("""UPDATE products SET product_name=%s, description=%s, price=%s, original_price=%s, brand=%s,
                                category=%s, stock_quantity=%s, image_data=%s, updated_at=CURRENT_TIMESTAMP
                                WHERE id=%s""",
                             (product_name, description, price, original_price, brand, category, stock_quantity, image_data, product_id))
                else:
                    c.execute("""UPDATE products SET product_name=%s, description=%s, price=%s, original_price=%s, brand=%s, 
                                category=%s, stock_quantity=%s, updated_at=CURRENT_TIMESTAMP
                                WHERE id=%s""",
                             (product_name, description, price, original_price, brand, category, stock_quantity, product_id))
                conn.commit()
        return {"success": True, "message": "商品を更新しました"}
    except Exception as e:
        print(f"商品更新エラー: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/admin/products/{product_id}")
async def delete_product_admin(product_id: int, session_token: str = Cookie(None)):
    """商品を削除（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM products WHERE id = %s", (product_id,))
                conn.commit()
        return {"success": True, "message": "商品を削除しました"}
    except Exception as e:
        print(f"商品削除エラー: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# ========== リマインダーAPI ==========

@app.post("/api/set-reminder")
async def set_reminder(request: Request):
    """リマインダーを設定"""
    try:
        data = await request.json()
        email = data.get('email')
        booking_date = data.get('booking_date')
        booking_time = data.get('booking_time')
        customer_name = data.get('customer_name')
        service_name = data.get('service_name')
        
        if not email or not booking_date or not booking_time:
            return JSONResponse(status_code=400, content={"error": "必須項目が不足しています"})
        
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO reminders (email, booking_date, booking_time, customer_name, service_name)
                    VALUES (%s, %s, %s, %s, %s)
                """, (email, booking_date, booking_time, customer_name, service_name))
                conn.commit()
        
        print(f"リマインダー設定完了: {email} - {booking_date} {booking_time}")
        return {"success": True, "message": "リマインダーを設定しました"}
    except Exception as e:
        print(f"リマインダー設定エラー: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

# ========== サービス管理API ==========

@app.get("/services")
def get_services(active_only: bool = True):
    """サービス一覧を取得"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            if active_only:
                c.execute("""
                    SELECT * FROM services 
                    WHERE is_active = TRUE
                    ORDER BY display_order, service_name
                """)
            else:
                c.execute("SELECT * FROM services ORDER BY display_order, service_name")
            services = c.fetchall()
    return {"services": services}

@app.post("/admin/services")
async def create_service(request: Request, session_token: str = Cookie(None)):
    """サービスを追加（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        data = await request.json()
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO services (service_name, description, price, duration, icon, is_popular, display_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data['service_name'],
                    data.get('description', ''),
                    data['price'],
                    data.get('duration', ''),
                    data.get('icon', '💆'),
                    data.get('is_popular', False),
                    data.get('display_order', 0)
                ))
                service_id = c.fetchone()[0]
                conn.commit()
        
        return {"success": True, "id": service_id, "message": "サービスを追加しました"}
    except Exception as e:
        print(f"サービス追加エラー: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.put("/admin/services/{service_id}")
async def update_service(service_id: int, request: Request, session_token: str = Cookie(None)):
    """サービスを更新（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        data = await request.json()
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE services 
                    SET service_name=%s, description=%s, price=%s, duration=%s, 
                        icon=%s, is_popular=%s, display_order=%s, updated_at=CURRENT_TIMESTAMP
                    WHERE id=%s
                """, (
                    data['service_name'],
                    data.get('description', ''),
                    data['price'],
                    data.get('duration', ''),
                    data.get('icon', '💆'),
                    data.get('is_popular', False),
                    data.get('display_order', 0),
                    service_id
                ))
                conn.commit()
        
        return {"success": True, "message": "サービスを更新しました"}
    except Exception as e:
        print(f"サービス更新エラー: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/admin/services/{service_id}")
async def delete_service(service_id: int, session_token: str = Cookie(None)):
    """サービスを削除（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM services WHERE id = %s", (service_id,))
                conn.commit()
        
        return {"success": True, "message": "サービスを削除しました"}
    except Exception as e:
        print(f"サービス削除エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})
    
# ========== Ontime robot API ==========

@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
def read_root():
    return {"status": "ok"}

# ========== 統計API ==========

@app.get("/api/stats")
async def get_stats(session_token: str = Cookie(None)):
    """アクセス統計を取得（管理者用）"""
    if not verify_admin_session(session_token):
        return JSONResponse(status_code=401, content={"error": "認証が必要です"})
    
    return get_page_view_stats()

@app.get("/health")
def health_check():
    """ヘルスチェック"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
