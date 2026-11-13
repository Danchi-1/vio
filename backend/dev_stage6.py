
from fastapi import FastAPI

from backend.src.api.lecturer_reply_api import router


app = FastAPI(
    title="Vio Stage 6 Development API",
    version="0.1.0"
)

app.include_router(router)
