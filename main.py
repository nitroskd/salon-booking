# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
import os

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
                    image_url VARCHAR(500),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 既存のproductsテーブルにカラムを追加（エラーを無視）
            try:
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS category VARCHAR(50)")
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS stock_quantity INTEGER DEFAULT 0")
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR(500)")
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE")
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except Exception as e:
                print(f"カラム追加をスキップ: {e}")
            
            # インデックス作成
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_bookings_date 
                ON bookings(booking_date)
            """)
            
            # categoryカラムが存在する場合のみインデックス作成
            try:
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_products_category 
                    ON products(category)
                """)
            except Exception as e:
                print(f"インデックス作成をスキップ: {e}")
            
            conn.commit()

init_db()

# ========== 予約関連のエンドポイント ==========

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
    """管理画面を表示"""
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/admin/products", response_class=HTMLResponse)
def admin_products_page(request: Request):
    """管理画面 - 商品管理ページを表示"""
    return templates.TemplateResponse("admin_products.html", {"request": request})

@app.get("/complete", response_class=HTMLResponse)
def complete_page(
    request: Request,
    customer_name: str = "",
    phone_number: str = "",
    service_name: str = "",
    booking_date: str = "",
    booking_time: str = "",
    notes: str = ""
):
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
            c.execute("""
                SELECT booking_date, booking_time 
                FROM bookings 
                ORDER BY booking_date, booking_time
            """)
            booked = c.fetchall()
    
    booked_dict = {}
    for date, time in booked:
        date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
        time_str = time.strftime('%H:%M') if hasattr(time, 'strftime') else str(time)
        booked_dict.setdefault(date_str, []).append(time_str)
    
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
            with conn.cursor() as c:
                c.execute("""
                    SELECT id FROM bookings 
                    WHERE booking_date = %s AND booking_time = %s
                """, (booking_date, booking_time))
                
                if c.fetchone():
                    return RedirectResponse("/?error=already_booked", status_code=303)
                
                c.execute("""
                    INSERT INTO bookings 
                    (customer_name, phone_number, service_name, booking_date, booking_time, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (customer_name, phone_number, service_name, booking_date, booking_time, notes))
                conn.commit()
        
        return RedirectResponse("/?success=true", status_code=303)
    
    except Exception as e:
        print(f"予約エラー: {e}")
        return RedirectResponse("/?error=system", status_code=303)

@app.get("/bookings")
def get_bookings():
    """予約一覧を取得"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute("""
                SELECT id, customer_name, phone_number, service_name, 
                       booking_date, booking_time, notes, created_at 
                FROM bookings 
                ORDER BY booking_date DESC, booking_time DESC
            """)
            bookings = c.fetchall()
    
    return {"bookings": bookings}

# ========== 商品関連のエンドポイント ==========

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

@app.get("/products/{product_id}")
def get_product(product_id: int):
    """特定の商品を取得"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as c:
            c.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            product = c.fetchone()
    
    if not product:
        return JSONResponse(status_code=404, content={"error": "商品が見つかりません"})
    
    return {"product": product}

@app.post("/products/add")
def create_product(
    product_name: str = Form(...),
    description: str = Form(default=""),
    price: float = Form(...),
    category: str = Form(default=""),
    stock_quantity: int = Form(default=0),
    image_url: str = Form(default="")
):
    """新しい商品を追加"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    INSERT INTO products 
                    (product_name, description, price, category, stock_quantity, image_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (product_name, description, price, category, stock_quantity, image_url))
                
                product_id = c.fetchone()[0]
                conn.commit()
        
        return {"success": True, "product_id": product_id, "message": "商品を追加しました"}
    
    except Exception as e:
        print(f"商品追加エラー: {e}")
        return JSONResponse(status_code=500, content={"error": "商品の追加に失敗しました"})

@app.put("/products/{product_id}")
def update_product(
    product_id: int,
    product_name: str = Form(...),
    description: str = Form(default=""),
    price: float = Form(...),
    category: str = Form(default=""),
    stock_quantity: int = Form(default=0),
    image_url: str = Form(default=""),
    is_active: bool = Form(default=True)
):
    """商品情報を更新"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE products 
                    SET product_name = %s, description = %s, price = %s, 
                        category = %s, stock_quantity = %s, image_url = %s,
                        is_active = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (product_name, description, price, category, stock_quantity, 
                      image_url, is_active, product_id))
                
                conn.commit()
        
        return {"success": True, "message": "商品を更新しました"}
    
    except Exception as e:
        print(f"商品更新エラー: {e}")
        return JSONResponse(status_code=500, content={"error": "商品の更新に失敗しました"})

@app.delete("/products/{product_id}")
def delete_product(product_id: int):
    """商品を削除（論理削除）"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE products 
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (product_id,))
                
                conn.commit()
        
        return {"success": True, "message": "商品を削除しました"}
    
    except Exception as e:
        print(f"商品削除エラー: {e}")
        return JSONResponse(status_code=500, content={"error": "商品の削除に失敗しました"})

@app.get("/health")
def health_check():
    """ヘルスチェック"""
    return {"status": "ok"}
