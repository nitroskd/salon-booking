# main.py
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
import os

# --- 環境変数読み込み ---
load_dotenv()

app = FastAPI()

# --- static フォルダ設定 ---
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- templates フォルダ設定 ---
templates_dir = "templates"
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
templates = Jinja2Templates(directory=templates_dir)

# --- PostgreSQL 接続設定 ---
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

# --- DB 初期化 ---
def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()

        # 予約テーブル
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

        # 商品テーブル
        c.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                image_filename TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()

init_db()

# =====================================================
# ページ構成
# =====================================================

# --- ホームページ ---
@app.get("/", response_class=HTMLResponse)
@app.get("/home", response_class=HTMLResponse)
def home_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# --- 予約ページ ---
@app.get("/index", response_class=HTMLResponse)
def booking_page(request: Request):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT booking_date, booking_time FROM bookings;")
        booked = c.fetchall()

    booked_dict = {}
    for date, time in booked:
        booked_dict.setdefault(str(date), []).append(time)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "booked": booked_dict
    })


# --- 予約完了ページ ---
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
                SELECT id FROM bookings WHERE booking_date = %s AND booking_time = %s
            """, (booking_date, booking_time))
            if c.fetchone():
                return HTMLResponse("<h3>⚠️ この時間はすでに予約されています。</h3>", status_code=400)

            # 登録
            c.execute("""
                INSERT INTO bookings (customer_name, phone_number, service_name, booking_date, booking_time, notes)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (customer_name, phone_number, service_name, booking_date, booking_time, notes))
            conn.commit()

        return templates.TemplateResponse("complete.html", {
            "request": request,
            "customer_name": customer_name,
            "service_name": service_name,
            "booking_date": booking_date,
            "booking_time": booking_time
        })

    except Exception as e:
        print(f"予約エラー: {e}")
        return HTMLResponse("<h3>サーバーエラーが発生しました。</h3>", status_code=500)


# --- ショップページ（商品一覧） ---
@app.get("/shop", response_class=HTMLResponse)
def shop_page(request: Request):
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, price, image_filename FROM products ORDER BY created_at DESC;")
        products = c.fetchall()

    product_list = [
        {"id": p[0], "name": p[1], "price": p[2], "image_filename": p[3]} for p in products
    ]

    return templates.TemplateResponse("shop.html", {
        "request": request,
        "products": product_list
    })


# =====================================================
# 管理者ページ
# =====================================================

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # .envで設定推奨


# --- 管理画面（予約一覧 & 商品一覧） ---
@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, password: str = ""):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="管理者パスワードが違います。")

    with get_db_connection() as conn:
        c = conn.cursor()

        # 予約一覧
        c.execute("""
            SELECT customer_name, phone_number, service_name, booking_date, booking_time, notes, created_at
            FROM bookings
            ORDER BY booking_date DESC, booking_time DESC;
        """)
        bookings = c.fetchall()

        # 商品一覧
        c.execute("""
            SELECT id, name, price, image_filename, created_at
            FROM products
            ORDER BY created_at DESC;
        """)
        products = c.fetchall()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "bookings": bookings,
        "products": products
    })


# --- 商品管理ページ ---
@app.get("/admin_products", response_class=HTMLResponse)
def admin_products_page(request: Request, password: str = ""):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="管理者パスワードが違います。")

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, price, image_filename FROM products ORDER BY created_at DESC;")
        products = c.fetchall()

    products_list = [
        {"id": p[0], "name": p[1], "price": p[2], "image_filename": p[3]} for p in products
    ]

    return templates.TemplateResponse("admin_products.html", {
        "request": request,
        "products": products_list
    })


# --- 商品登録 ---
@app.post("/admin_products/add")
async def add_product(
    name: str = Form(...),
    price: int = Form(...),
    image: UploadFile = File(...),
    password: str = Form(...)
):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="パスワードが違います。")

    os.makedirs("static/images", exist_ok=True)
    image_path = os.path.join("static/images", image.filename)
    with open(image_path, "wb") as f:
        f.write(await image.read())

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO products (name, price, image_filename) VALUES (%s, %s, %s);",
            (name, price, image.filename)
        )
        conn.commit()

    return RedirectResponse("/admin_products?password=" + password, status_code=303)


# --- 商品削除 ---
@app.post("/admin_products/delete/{product_id}")
def delete_product(product_id: int, password: str = Form(...)):
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="パスワードが違います。")

    with get_db_connection() as conn:
        c = conn.cursor()

        c.execute("SELECT image_filename FROM products WHERE id=%s;", (product_id,))
        result = c.fetchone()
        if result and result[0]:
            path = os.path.join("static/images", result[0])
            if os.path.exists(path):
                os.remove(path)

        c.execute("DELETE FROM products WHERE id=%s;", (product_id,))
        conn.commit()

    return RedirectResponse(f"/admin_products?password={password}", status_code=303)


# --- ヘルスチェック ---
@app.get("/health")
def health_check():
    return {"status": "ok"}


