from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from src.routes import process
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("uvicorn")

# Load environment variables
load_dotenv()

app = FastAPI(
    title="OneVoice API",
    description="영어 동영상을 한국어로 더빙하는 API",
    version="1.0.0",
    debug=False
)

# CORS 설정
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:80",
    "*"  # 개발 환경에서만 사용하세요
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

@app.middleware("http")
async def log_requests(request, call_next):
    logger.debug(f"Request: {request.method} {request.url}")
    logger.debug(f"Headers: {request.headers}")
    response = await call_next(request)
    logger.debug(f"Response status: {response.status_code}")
    return response

# 라우터 등록
app.include_router(process.router, prefix="/api/process", tags=["process"])

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Root endpoint
@app.get("/")
async def root():
    return {"status": "healthy", "message": "OneVoice API is running"} 