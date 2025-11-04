# infra/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1) 환경변수에서 먼저 읽기
#    우선순위: DATABASE_URL > DB_URL
DB_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("DB_URL")
    or "postgresql+psycopg2://myhts:myhts_pw@localhost:5432/myhts"
    # ↑ 여기 기본값은 네가 도커로 띄운다고 가정한 값으로 넣은 거야
    #   사용자/비번/DB이름 다 다르면 이 줄만 바꾸면 됨
)

engine = create_engine(DB_URL, echo=False, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
