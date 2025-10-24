# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- DB初期化 ---
def init_db():
    conn = sqlite3.connect("bookings.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            service_name TEXT,
            booking_date TEXT,
            booking_time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
    conn = sqlite3.connect("bookings.db")
    c = conn.cursor()
    c.execute("SELECT booking_date, booking_time FROM bookings")
    booked = c.fetchall()
    conn.close()

    # 予約済みデータを {日付: [時間,時間]} の形式に変換
    booked_dict = {}
    for date, time in booked:
        booked_dict.setdefault(date, []).append(time)

    return templates.TemplateResponse("index.html", {"request": request, "booked": booked_dict})


@app.post("/book")
def book_service(
    customer_name: str = Form(...),
    service_name: str = Form(...),
    booking_date: str = Form(...),
    booking_time: str = Form(...)
):
    conn = sqlite3.connect("bookings.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO bookings (customer_name, service_name, booking_date, booking_time)
        VALUES (?, ?, ?, ?)
    """, (customer_name, service_name, booking_date, booking_time))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)
