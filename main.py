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
