from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("booking.html", {"request": request})

@app.post("/reserve")
def reserve(name: str = Form(...), date: str = Form(...), service: str = Form(...)):
    # 本来はここでDBに保存するが、今回は表示だけ
    return {
        "message": f"{name}さん、{date}に「{service}」を予約しました！"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
from fastapi.responses import HTMLResponse

# 予約データを一時的に保存するリスト（既にあるなら重複しないよう確認）
bookings = []

@app.post("/book")
def book(name: str = Form(...), date: str = Form(...), service: str = Form(...)):
    booking = {"name": name, "date": date, "service": service}
    bookings.append(booking)
    return {"message": f"{name}さんの予約を受け付けました！"}

# ★ここからがSTEP2★
@app.get("/bookings", response_class=HTMLResponse)
def show_bookings():
    html = "<h2>予約一覧</h2><ul>"
    for booking in bookings:
        html += f"<li>{booking['date']} - {booking['name']} ({booking['service']})</li>"
    html += "</ul>"
    return html
