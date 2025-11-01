from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os
DB_URL = os.environ.get('DATABASE_URL')
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
