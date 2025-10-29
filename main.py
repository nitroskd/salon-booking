# main.py
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import contextmanager
from urllib.parse import urlencode
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

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
            
            # 既存テーブルにカラム追加
            try:
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_data TEXT")
            except Exception as e:
                print(f"カラム追加スキップ: {e}")
            
            # インデックス作成
            c.execute("CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(booking_date)")
            try:
                c.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
            except:
                pass
            
            conn.commit()

init_db()

# ========== ページ表示 ==========

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
    """管理画面を表示"""
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
    return templates.TemplateResponse("complete.html", {
        "request": request, "customer_name": customer_name, "phone_number": phone_number,
        "service_name": service_name, "booking_date": booking_date, "booking_time": booking_time, "notes": notes
    })

@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
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
        
        params = urlencode({'customer_name': customer_name, 'phone_number': phone_number,
                           'service_name': service_name, 'booking_date': booking_date,
                           'booking_time': booking_time, 'notes': notes or ''})
        return RedirectResponse(f"/complete?{params}", status_code=303)
    except Exception as e:
        print(f"予約エラー: {e}")
        return RedirectResponse("/?error=system", status_code=303)

@app.get("/bookings")
def get_bookings():
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

@app.get("/health")
def health_check():
    return {"status": "ok"}
