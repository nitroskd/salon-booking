from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

# サービス（例：カット、カラーなど）
class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)


# 予約
class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"))
    date = Column(DateTime, default=datetime.utcnow)

    service = relationship("Service")


# SQLiteデータベース接続
engine = create_engine("sqlite:///./salon.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 初期化（テーブル作成）
def init_db():
    Base.metadata.create_all(bind=engine)
