import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from main import app
from services.task_manager import TaskStatus, ProcessingStage

client = TestClient(app)

@pytest.fixture
def mock_redis():
    with patch('services.task_manager.redis.Redis') as mock:
        redis_instance = MagicMock()
        mock.return_value = redis_instance
        yield redis_instance

@pytest.fixture
def mock_process_video():
    with patch('services.stt.process_video') as mock:
        mock.return_value = "테스트 텍스트"
        yield mock

@pytest.fixture
def mock_download_youtube():
    with patch('routes.process.download_youtube_video') as mock:
        mock.return_value = "test.mp4"
        yield mock

@pytest.fixture
def mock_translate_text():
    with patch('services.nmt.translate_text') as mock:
        mock.return_value = "번역된 텍스트"
        yield mock

@pytest.fixture
def mock_synthesize_speech():
    with patch('services.tts.process_text') as mock:
        mock.return_value = "output.mp4"
        yield mock

@pytest.fixture
def mock_task_manager(mock_redis):
    task_data = {
        "status": TaskStatus.PENDING,
        "stage": None,
        "progress": 0,
        "result": None,
        "error": None
    }
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    return mock_redis

def test_upload_invalid_file():
    """잘못된 파일 형식 업로드 테스트"""
    files = {
        "file": ("test.txt", b"test content", "text/plain")
    }
    response = client.post("/api/process/upload", files=files)
    assert response.status_code == 400
    assert "MP4" in response.json()["detail"]

def test_upload_valid_file(mock_process_video, mock_translate_text, mock_synthesize_speech, mock_task_manager):
    """올바른 MP4 파일 업로드 테스트"""
    files = {
        "file": ("test.mp4", b"test mp4 content", "video/mp4")
    }
    response = client.post("/api/process/upload", files=files)
    assert response.status_code == 200
    assert "task_id" in response.json()
    task_id = response.json()["task_id"]
    assert task_id is not None

def test_invalid_youtube_url():
    """잘못된 YouTube URL 테스트"""
    response = client.post(
        "/api/process/youtube",
        json={"url": "https://invalid-url.com"}
    )
    assert response.status_code == 400
    assert "유효하지 않은" in response.json()["detail"]

def test_valid_youtube_url(mock_download_youtube, mock_process_video, mock_translate_text, mock_synthesize_speech, mock_task_manager):
    """올바른 YouTube URL 테스트"""
    response = client.post(
        "/api/process/youtube",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
    )
    assert response.status_code == 200
    assert "task_id" in response.json()

def test_get_invalid_task_status(mock_task_manager):
    """존재하지 않는 작업 상태 조회 테스트"""
    mock_task_manager.get.return_value = None
    response = client.get("/api/process/status/invalid-task-id")
    assert response.status_code == 404
    assert "작업을 찾을 수 없습니다" in response.json()["detail"]

def test_get_valid_task_status(mock_process_video, mock_translate_text, mock_synthesize_speech, mock_task_manager):
    """올바른 작업 상태 조회 테스트"""
    task_data = {
        "status": TaskStatus.PROCESSING,
        "stage": ProcessingStage.STT,
        "progress": 33,
        "result": None,
        "error": None
    }
    mock_task_manager.get.return_value = task_data
    
    # 먼저 작업 생성
    files = {
        "file": ("test.mp4", b"test content", "video/mp4")
    }
    response = client.post("/api/process/upload", files=files)
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    # 상태 조회
    response = client.get(f"/api/process/status/{task_id}")
    assert response.status_code == 200
    assert "status" in response.json()
    assert "progress" in response.json() 