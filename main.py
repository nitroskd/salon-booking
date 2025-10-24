# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
import os

# --- 環境変数を読み込む ---
load_dotenv()

app = FastAPI()

# --- テンプレート設定 ---
templates_dir = "templates"
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)

templates = Jinja2Templates(directory=templates_dir)

# --- PostgreSQL接続設定 ---
DB_URL = os.getenv("DATABASE_URL")  # .env で設定する

if not DB_URL:
    raise Exception("❌ DATABASE_URL が .env に設定されていません。")

# --- DB接続のコンテキストマネージャー ---
@contextmanager
def get_db_connection():
    """PostgreSQL接続を安全に管理"""
    conn = psycopg2.connect(DB_URL)
    try:
        yield conn
    finally:
        conn.close()

# --- DB初期化 ---
def init_db():
    """PostgreSQLテーブル初期化"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                customer_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                service_name TEXT NOT NULL,
                booking_date DATE NOT NULL,
                booking_time TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(booking_date, booking_time)
            );
        """)
        conn.commit()

# --- 初期化実行 ---
init_db()

@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
    """予約フォームを表示"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT booking_date, booking_time FROM bookings ORDER BY booking_date, booking_time;")
        booked = c.fetchall()

    booked_dict = {}
    for date, time in booked:
        booked_dict.setdefault(str(date), []).append(time)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "booked": booked_dict
    })

@app.post("/book")
def book_service(
    customer_name: str = Form(...),
    phone_number: str = Form(...),
    service_name: str = Form(...),
    booking_date: str = Form(...),
    booking_time: str = Form(...),
    notes: str = Form(default="")
):
    """予約を登録"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # 重複チェック
            c.execute("""
                SELECT id FROM bookings 
                WHERE booking_date = %s AND booking_time = %s;
            """, (booking_date, booking_time))
            
            if c.fetchone():
                return RedirectResponse("/?error=already_booked", status_code=303)
            
            # 挿入処理
            c.execute("""
                INSERT INTO bookings (customer_name, phone_number, service_name, booking_date, booking_time, notes)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (customer_name, phone_number, service_name, booking_date, booking_time, notes))
            conn.commit()

        return RedirectResponse("/?success=true", status_code=303)
    
    except Exception as e:
        print(f"❌ 予約エラー: {e}")
        return RedirectResponse("/?error=system", status_code=303)

@app.get("/bookings")
def get_bookings():
    """予約一覧をJSONで返す"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, customer_name, phone_number, service_name, booking_date, booking_time, notes, created_at 
            FROM bookings 
            ORDER BY booking_date DESC, booking_time DESC;
        """)
        rows = c.fetchall()

    return {
        "bookings": [
            {
                "id": r[0],
                "customer_name": r[1],
                "phone_number": r[2],
                "service_name": r[3],
                "booking_date": str(r[4]),
                "booking_time": r[5],
                "notes": r[6],
                "created_at": str(r[7])
            }
            for r in rows
        ]
    }
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    """管理画面：予約一覧"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT customer_name, phone_number, service_name, booking_date, booking_time, notes, created_at 
            FROM bookings 
            ORDER BY booking_date DESC, booking_time DESC;
        """)
        bookings = c.fetchall()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "bookings": bookings
    })

@app.get("/health")
def health_check():
    """Render用ヘルスチェック"""
    return {"status": "ok"}
