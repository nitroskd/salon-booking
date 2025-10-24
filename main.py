# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import contextmanager
import sqlite3
import os

app = FastAPI()

# テンプレートディレクトリの存在確認
templates_dir = "templates"
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)

templates = Jinja2Templates(directory=templates_dir)

# データベースファイルのパス
DB_PATH = "bookings.db"

# --- DB接続のコンテキストマネージャー ---
@contextmanager
def get_db_connection():
    """データベース接続を安全に管理"""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

# --- DB初期化 ---
def init_db():
    """データベースとテーブルを初期化"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                service_name TEXT NOT NULL,
                booking_date TEXT NOT NULL,
                booking_time TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(booking_date, booking_time)
            )
        """)
        conn.commit()

# アプリ起動時にDB初期化
init_db()

@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
    """予約フォームを表示"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT booking_date, booking_time FROM bookings ORDER BY booking_date, booking_time")
        booked = c.fetchall()
    
    # 予約済みデータを {日付: [時間,時間]} の形式に変換
    booked_dict = {}
    for date, time in booked:
        booked_dict.setdefault(date, []).append(time)
    
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
                WHERE booking_date = ? AND booking_time = ?
            """, (booking_date, booking_time))
            
            if c.fetchone():
                # 既に予約済みの場合はエラー
                return RedirectResponse("/?error=already_booked", status_code=303)
            
            # 予約を挿入
            c.execute("""
                INSERT INTO bookings (customer_name, phone_number, service_name, booking_date, booking_time, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (customer_name, phone_number, service_name, booking_date, booking_time, notes))
            conn.commit()
        
        return RedirectResponse("/?success=true", status_code=303)
    
    except sqlite3.IntegrityError:
        # UNIQUE制約違反の場合
        return RedirectResponse("/?error=already_booked", status_code=303)
    except Exception as e:
        # その他のエラー
        print(f"予約エラー: {e}")
        return RedirectResponse("/?error=system", status_code=303)

@app.get("/bookings")
def get_bookings():
    """予約一覧をJSON形式で返す（管理用API）"""
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, customer_name, phone_number, service_name, booking_date, booking_time, notes, created_at 
            FROM bookings 
            ORDER BY booking_date DESC, booking_time DESC
        """)
        bookings = c.fetchall()
    
    return {
        "bookings": [
            {
                "id": b[0],
                "customer_name": b[1],
                "phone_number": b[2],
                "service_name": b[3],
                "booking_date": b[4],
                "booking_time": b[5],
                "notes": b[6],
                "created_at": b[7]
            }
            for b in bookings
        ]
    }

# ヘルスチェック用エンドポイント
@app.get("/health")
def health_check():
    """アプリケーションの稼働状態を確認"""
    return {"status": "ok"}
