from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from models import Service, Booking, SessionLocal, init_db
from pydantic import BaseModel
from typing import List
from datetime import datetime

app = FastAPI()

# DBの初期化
init_db()

# DBセッションを取得する関数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========================
# Pydantic スキーマ
# ========================
class ServiceCreate(BaseModel):
    name: str
    price: int

class ServiceResponse(BaseModel):
    id: int
    name: str
    price: int
    class Config:
        orm_mode = True

class BookingCreate(BaseModel):
    customer_name: str
    service_id: int
    date: datetime

class BookingResponse(BaseModel):
    id: int
    customer_name: str
    service: ServiceResponse
    date: datetime
    class Config:
        orm_mode = True


# ========================
# エンドポイント
# ========================

# サービス一覧
@app.get("/services", response_model=List[ServiceResponse])
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).all()


# サービス追加
@app.post("/services", response_model=ServiceResponse)
def create_service(service: ServiceCreate, db: Session = Depends(get_db)):
    new_service = Service(name=service.name, price=service.price)
    db.add(new_service)
    db.commit()
    db.refresh(new_service)
    return new_service


# 予約登録
@app.post("/bookings", response_model=BookingResponse)
def create_booking(booking: BookingCreate, db: Session = Depends(get_db)):
    new_booking = Booking(
        customer_name=booking.customer_name,
        service_id=booking.service_id,
        date=booking.date,
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking


# 予約一覧
@app.get("/bookings", response_model=List[BookingResponse])
def list_bookings(db: Session = Depends(get_db)):
    return db.query(Booking).all()
from fastapi import Query
from datetime import date

# 予約を日付ごとに取得
@app.get("/bookings/by-date", response_model=List[BookingResponse])
def list_bookings_by_date(
    target_date: date = Query(..., description="YYYY-MM-DD 形式で指定"),
    db: Session = Depends(get_db)
):
    # その日の0:00〜23:59まで
    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date, datetime.max.time())

    return db.query(Booking).filter(
        Booking.date >= start,
        Booking.date <= end
    ).all()

# 今日の予約一覧
@app.get("/bookings/today", response_model=List[BookingResponse])
def list_todays_bookings(db: Session = Depends(get_db)):
    today = datetime.now().date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    return db.query(Booking).filter(
        Booking.date >= start,
        Booking.date <= end
    ).all()

from fastapi import Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import uvicorn

templates = Jinja2Templates(directory="templates")

# トップページ
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# サービス一覧ページ
@app.get("/services")
def service_list(request: Request, db: Session = Depends(get_db)):
    services = db.query(Service).all()
    return templates.TemplateResponse("services.html", {"request": request, "services": services})

# 予約フォーム表示
@app.get("/bookings/new")
def booking_form(request: Request, db: Session = Depends(get_db)):
    services = db.query(Service).all()
    return templates.TemplateResponse("booking.html", {"request": request, "services": services})

# 予約フォーム送信処理
@app.post("/bookings/new")
def create_booking_form(
    request: Request,
    customer_name: str = Form(...),
    service_id: int = Form(...),
    date: str = Form(...),
    db: Session = Depends(get_db)
):
    booking = Booking(customer_name=customer_name, service_id=service_id, date=datetime.fromisoformat(date))
    db.add(booking)
    db.commit()
    return RedirectResponse(url="/", status_code=303)
