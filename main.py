# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
import os

# --- 環境変数読み込み ---
load_dotenv()

app = FastAPI()

# --- テンプレート設定 ---
templates_dir = "templates"
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
templates = Jinja2Templates(directory=templates_dir)

# --- PostgreSQL接続 ---
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise Exception("❌ DATABASE_URL が .env に設定されていません。")

@contextmanager
def get_db_connection():
    conn = psycopg2.connect(DB_URL)
    try:
        yield conn
    finally:
        conn.close()

# --- DB初期化 ---
def init_db():
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

init_db()

# --- 予約フォーム ---
@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
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

# --- 予約登録 & 完了画面 ---
@app.post("/book", response_class=HTMLResponse)
def book_service(
    request: Request,
    customer_name: str = Form(...),
    phone_number: str = Form(...),
    service_name: str = Form(...),
    booking_date: str = Form(...),
    booking_time: str = Form(...),
    notes: str = Form(default="")
):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # 重複チェック
            c.execute("""
                SELECT id FROM bookings
                WHERE booking_date = %s AND booking_time = %s
            """, (booking_date, booking_time))
            
            if c.fetchone():
                return HTMLResponse("<h2>この時間は既に予約済みです</h2>", status_code=400)
            
            # 予約挿入
            c.execute("""
                INSERT INTO bookings (customer_name, phone_number, service_name, booking_date, booking_time, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (customer_name, phone_number, service_name, booking_date, booking_time, notes))
            conn.commit()

        # 完了画面表示
        return templates.TemplateResponse("complete.html", {
            "request": request,
            "customer_name": customer_name,
            "phone_number": phone_number,
            "service_name": service_name,
            "booking_date": booking_date,
            "booking_time": booking_time,
            "notes": notes
        })
    except Exception as e:
        print(f"予約エラー: {e}")
        return HTMLResponse("<h2>システムエラーが発生しました</h2>", status_code=500)

# --- 管理画面 ---
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
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

# --- ヘルスチェック ---
@app.get("/health")
def health_check():
    return {"status": "ok"}

