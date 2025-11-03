from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import contextmanager
from urllib.parse import urlencode
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from datetime import datetime, timedelta
import schedule
import threading
import time

app = FastAPI()

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

# 通知設定
GMAIL_USER = os.getenv("GMAIL_USER")  # 送信元メールアドレス
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")  # 通知を送りたいユーザーのID

def send_gmail_notification(booking_data):
    """SendGrid経由でメール通知を送信"""
    if not SENDGRID_API_KEY or not GMAIL_USER:
        print("SendGrid設定が見つかりません")
        return False
    
    try:
        # サイトのベースURLを取得
        base_url = os.getenv("BASE_URL", "https://salon-booking-k54d.onrender.com")
        admin_url = f"{base_url}/admin"
        
        # メール内容を作成
        subject = f"【新規予約】{booking_data['customer_name']}様 - {booking_data['booking_date']}"
        
        # HTML形式のメール本文
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
        
        # プレーンテキスト版
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
        
        # SendGrid API経由で送信
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
        # LINE通知メッセージを作成
        message = f"""🌿 新しい予約が入りました

👤 {booking_data['customer_name']} 様
📞 {booking_data['phone_number']}
💆 {booking_data['service_name']}
📅 {booking_data['booking_date']} {booking_data['booking_time']}"""
        
        if booking_data.get('notes'):
            message += f"\n📝 {booking_data['notes']}"
        
        # サイトのベースURLを取得
        base_url = os.getenv("BASE_URL", "https://salon-booking-k54d.onrender.com")
        admin_url = f"{base_url}/admin"
        
        # LINE Messaging APIにPOST
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

def init_db():
    """データベースとテーブルを初期化"""
    with get_db_connection() as conn:
        with conn.cursor() as c:
            # bookingsテーブル
            c.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id SERIAL PRIMARY KEY,
                    customer_name VARCHAR(100) NOT NULL,
                    phone_number VARCHAR(20) NOT NULL,
                    service_name VARCHAR(100) NOT NULL,
                    booking_date DATE NOT NULL,
                    booking_time TIME NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                    category VARCHAR(50),
                    stock_quantity INTEGER DEFAULT 0,
                    image_data TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # remindersテーブル（新規追加）
            c.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    booking_date DATE NOT NULL,
                    booking_time TIME NOT NULL,
                    customer_name VARCHAR(100) NOT NULL,
                    service_name VARCHAR(100) NOT NULL,
                    sent BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 既存テーブルにカラム追加
            try:
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_data TEXT")
            except Exception as e:
                print(f"カラム追加スキップ: {e}")
            
            # インデックス作成
            c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(booking_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_reminders_date ON reminders(booking_date)")
            try:
                c.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
            except:
                pass
            
            conn.commit()

# リマインダー送信バッチ処理
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
                        # リマインダーメール送信
                        if send_reminder_email(reminder):
                            # 送信済みフラグを更新
                            c.execute("UPDATE reminders SET sent = TRUE WHERE id = %s", (reminder['id'],))
                            conn.commit()
                            print(f"リマインダー送信完了: ID {reminder['id']}")
                    except Exception as e:
                        print(f"リマインダー送信エラー (ID: {reminder['id']}): {e}")
    except Exception as e:
        print(f"リマインダーチェックエラー: {e}")
        import traceback
        traceback.print_exc()

# スケジューラー実行
def run_scheduler():
    """バックグラウンドでスケジュール実行"""
    schedule.every().day.at("09:00").do(send_reminders)
    print("スケジューラー起動: 毎日9:00にリマインダーチェック")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# データベース初期化
init_db()

# スケジューラーをバックグラウンドで起動
threading.Thread(target=run_scheduler, daemon=True).start()

# ========== ページ表示のエンドポイント ==========

@app.get("/home", response_class=HTMLResponse)
def home_page(request: Request):
    """ホームページを表示"""
    return templates.TemplateResponse("home.html", {"request": request})

@app.get("/shop", response_class=HTMLResponse)
def shop_page(request: Request):
    """商品一覧ページを表示"""
    return templates.TemplateResponse("shop.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    """管理画面 - 予約管理を表示"""
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/admin/products", response_class=HTMLResponse)
def admin_products_page(request: Request):
    """管理画面 - 商品登録ページを表示"""
    return templates.TemplateResponse("admin_products.html", {"request": request})

@app.get("/admin/products/list", response_class=HTMLResponse)
def admin_products_list_page(request: Request):
    """管理画面 - 商品一覧管理ページを表示"""
    return templates.TemplateResponse("admin_products_list.html", {"request": request})

@app.get("/complete", response_class=HTMLResponse)
def complete_page(request: Request, customer_name: str = "", phone_number: str = "",
                  service_name: str = "", booking_date: str = "", booking_time: str = "", notes: str = ""):
    """予約完了ページを表示"""
    return templates.TemplateResponse("complete.html", {
        "request": request, 
        "customer_name": customer_name, 
        "phone_number": phone_number,
        "service_name": service_name, 
        "booking_date": booking_date, 
        "booking_time": booking_time, 
        "notes": notes
    })

@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
    """予約フォームを表示"""
    with get_db_connection() as conn:
        with conn.cursor() as c:
            c.execute("SELECT booking_date, booking_time FROM bookings ORDER BY booking_date, booking_time")
            booked = c.fetchall()
    
    booked_dict = {}
    for date, time in booked:
        date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        time_str = time.strftime('%H:%M') if hasattr(time, 'strftime') else str(time)
        booked_dict.setdefault(date_str, []).append(time_str)
    
    return templates.TemplateResponse("index.html", {"request": request, "booked": booked_dict})

# ========== 予約API（ユーザー用） ==========

@app.post("/book")
def book_service(customer_name: str = Form(...), phone_number: str = Form(...),
                 service_name: str = Form(...), booking_date: str = Form(...),
                 booking_time: str = Form(...), notes: str = Form(default="")):
    """予約を登録"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id FROM bookings WHERE booking_date = %s AND booking_time = %s",
                         (booking_date, booking_time))
                if c.fetchone():
                    return RedirectResponse("/?error=already_booked", status_code=303)
                
                c.execute("""INSERT INTO bookings (customer_name, phone_number, service_name, booking_date, booking_time, notes)
                            VALUES (%s, %s, %s, %s, %s, %s)""",
                         (customer_name, phone_number, service_name, booking_date, booking_time, notes))
                conn.commit()
        
        # 予約データを準備
        booking_data = {
            'customer_name': customer_name,
            'phone_number': phone_number,
            'service_name': service_name,
            'booking_date': booking_date,
            'booking_time': booking_time,
            'notes': notes
        }
        
        # Gmail通知を送信（非同期で実行してエラーでも予約は完了させる）
        try:
            send_gmail_notification(booking_data)
        except Exception as e:
            print(f"Gmail通知エラー（無視）: {e}")
        
        # LINE通知を送信
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
        return RedirectResponse("/?error=system", status_code=303)

@app.get("/bookings")
def get_bookings():
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
async def create_booking_admin(request: Request):
    """予約を追加（管理者用）"""
    data = await request.json()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""INSERT INTO bookings (customer_name, phone_number, service_name, booking_date, booking_time, notes)
                            VALUES (%s, %s, %s, %s, %s, %s)""",
                         (data['customer_name'], data['phone_number'], data['service_name'],
                          data['booking_date'], data['booking_time'], data.get('notes', '')))
                conn.commit()
        return {"success": True, "message": "予約を追加しました"}
    except Exception as e:
        print(f"予約追加エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.put("/admin/bookings/{booking_id}")
async def update_booking_admin(booking_id: int, request: Request):
    """予約を更新（管理者用）"""
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
def delete_booking_admin(booking_id: int):
    """予約を削除（管理者用）"""
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
def get_products(category: str = None, active_only: bool = True):
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
            query += " ORDER BY category, product_name"
            c.execute(query, params)
            products = c.fetchall()
    return {"products": products}

@app.post("/admin/products/add")
async def create_product_admin(request: Request, product_name: str = Form(...),
                                price: float = Form(...), category: str = Form(...),
                                stock_quantity: int = Form(...), description: str = Form(default=""),
                                image_data: str = Form(...)):
    """商品を追加（管理者用）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""INSERT INTO products (product_name, description, price, category, stock_quantity, image_data)
                            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                         (product_name, description, price, category, stock_quantity, image_data))
                product_id = c.fetchone()[0]
                conn.commit()
        return {"success": True, "product_id": product_id, "message": "商品を追加しました"}
    except Exception as e:
        print(f"商品追加エラー: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.put("/admin/products/{product_id}")
async def update_product_admin(product_id: int, request: Request):
    """商品を更新（管理者用）"""
    try:
        form_data = await request.form()
        product_name = form_data.get('product_name')
        price = float(form_data.get('price'))
        category = form_data.get('category')
        stock_quantity = int(form_data.get('stock_quantity'))
        description = form_data.get('description', '')
        image_data = form_data.get('image_data', '')
        
        with get_db_connection() as conn:
            with conn.cursor() as c:
                if image_data:
                    # 画像も更新
                    c.execute("""UPDATE products SET product_name=%s, description=%s, price=%s, 
                                category=%s, stock_quantity=%s, image_data=%s, updated_at=CURRENT_TIMESTAMP
                                WHERE id=%s""",
                             (product_name, description, price, category, stock_quantity, image_data, product_id))
                else:
                    # 画像以外を更新
                    c.execute("""UPDATE products SET product_name=%s, description=%s, price=%s, 
                                category=%s, stock_quantity=%s, updated_at=CURRENT_TIMESTAMP
                                WHERE id=%s""",
                             (product_name, description, price, category, stock_quantity, product_id))
                conn.commit()
        return {"success": True, "message": "商品を更新しました"}
    except Exception as e:
        print(f"商品更新エラー: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/admin/products/{product_id}")
async def delete_product_admin(product_id: int):
    """商品を削除（管理者用）"""
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
        
        # バリデーション
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

@app.get("/health")
def health_check():
    """ヘルスチェック"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
