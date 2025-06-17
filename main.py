from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from Department.APIs import router as dept_router
from User.APIs import router as user_router
from Grievances.APIs import router as grv_router
from Comments.APIs import router as com_router
import auth
import User.APIs as user_apis
from Department import models as dept_models
from User import models as user_models


# Create database tables
Base.metadata.create_all(bind=engine)
dept_models.Base.metadata.create_all(bind=engine)
user_models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Register routers
app.include_router(dept_router)
app.include_router(user_router)
app.include_router(user_apis.router)
app.include_router(auth.router)
app.include_router(grv_router)
app.include_router(com_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
