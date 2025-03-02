import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, Tuple
import re
import yt_dlp
import ffmpeg
from pathlib import Path
import subprocess
from src.services import config
from src.services.task_manager import TaskManager, TaskStatus, ProcessingStage
from src.services.stt import stt_service
from src.services.nmt import nmt_service
from src.services.tts import tts_service
from src.services.video_audio_merger import video_audio_merger
from google.cloud import storage
import tempfile
import asyncio
import shutil
import json

router = APIRouter()
task_manager = TaskManager()

# CORS 설정
origins = [
    "http://localhost",
    "http://localhost:3000",
]

class YouTubeRequest(BaseModel):
    url: str
    source_language: Optional[str] = "ko"
    target_language: Optional[str] = "en"

class FeedbackRequest(BaseModel):
    rating: int

class TaskStatusUpdate(BaseModel):
    status: str
    stage: Optional[str] = None
    progress: Optional[int] = None
    result: Optional[str] = None
    error: Optional[str] = None

def sanitize_filename(filename: str) -> str:
    """파일명에서 특수문자 제거 및 공백을 언더스코어로 변경"""
    filename = re.sub(r"[\\/*?:\"<>|#']", '_', filename)
    filename = re.sub(r'\s+', '_', filename)
    return filename

async def extract_audio(video_path: str, original_audio_path: str, denoised_audio_path: str) -> Tuple[str, str]:
    """비디오 파일에서 오디오를 추출하는 함수"""
    try:
        # 원본 오디오 추출
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, original_audio_path,
                             acodec='pcm_s16le',
                             ac=2,
                             ar='44.1k')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        # 노이즈 제거 오디오 추출
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, denoised_audio_path,
                            acodec='pcm_s16le',
                            ac=1,
                            ar='16k',
                            af='afftdn=nf=-25')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        
        return denoised_audio_path, original_audio_path
        
    except ffmpeg.Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg 오류: {e.stderr.decode() if e.stderr else str(e)}"
        )

async def upload_to_gcs(local_path: str, gcs_path: str) -> bool:
    """로컬 파일을 GCS 버킷에 업로드"""
    try:
        # GCS 경로 파싱 (gs://bucket-name/path/to/file)
        gcs_parts = gcs_path.replace("gs://", "").split("/", 1)
        bucket_name = gcs_parts[0]
        blob_name = gcs_parts[1] if len(gcs_parts) > 1 else os.path.basename(local_path)
        
        # 스토리지 클라이언트 생성
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # 파일 업로드
        print(f"파일 업로드 시작: {local_path} -> gs://{bucket_name}/{blob_name}")
        blob.upload_from_filename(local_path)
        print(f"파일 업로드 완료: {local_path} -> gs://{bucket_name}/{blob_name}")
        
        return True
    except Exception as e:
        print(f"GCS 업로드 오류: {str(e)}")
        return False

async def download_youtube_video(url: str) -> Tuple[str, str, str]:
    """유튜브 영상을 다운로드하고 오디오를 추출"""
    output_dir = os.path.join(config.TEMP_DIR, "input_videos")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    try:
        # 비디오 다운로드 옵션
        ydl_opts = {
            'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': True,
            'geo_bypass': True,
            'no_check_certificate': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        }
        
        # 영상 정보를 가져오기
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if info['duration'] > 600:  # 10분 이상
                    raise HTTPException(status_code=400, detail="10분 이하의 동영상만 처리 가능합니다")
                
                original_title = info['title']
                sanitized_title = sanitize_filename(original_title)
                
                print(f"원본 제목: {original_title}")
                print(f"정제된 제목: {sanitized_title}")
                
                # 다운로드 옵션 업데이트 - 정제된 파일명으로 다운로드
                ydl_opts['outtmpl'] = os.path.join(output_dir, f"{sanitized_title}.%(ext)s")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                    # 영상 다운로드
                    ydl_download.download([url])
                
                # 정제된 파일 경로 (이미 정제된 이름으로 다운로드됨)
                sanitized_video_path = os.path.join(output_dir, f"{sanitized_title}.mp4")
                sanitized_audio_path = os.path.join(output_dir, f"{sanitized_title}.wav")
                sanitized_denoised_audio_path = os.path.join(output_dir, f"{sanitized_title}_denoised.wav")
                
                # 파일이 존재하는지 간단히 확인
                if not os.path.exists(sanitized_video_path):
                    raise HTTPException(
                        status_code=400,
                        detail="다운로드된 비디오 파일을 찾을 수 없습니다"
                    )
                
                video_path = sanitized_video_path
                
                # 오디오 추출 함수 호출
                denoised_audio_path, original_audio_path = await extract_audio(
                    video_path, 
                    sanitized_audio_path, 
                    sanitized_denoised_audio_path
                )

                # GCS 버킷에 업로드 (정제된 파일 이름 사용)
                gcs_bucket = "gs://onevoice-test-bucket/resources/input_videos"
                # 정제된 파일명 사용
                sanitized_video_filename = os.path.basename(video_path)
                sanitized_original_audio_filename = os.path.basename(original_audio_path)
                sanitized_denoised_audio_filename = os.path.basename(denoised_audio_path)
                
                await upload_to_gcs(video_path, f"{gcs_bucket}/{sanitized_video_filename}")
                await upload_to_gcs(original_audio_path, f"{gcs_bucket}/{sanitized_original_audio_filename}")
                await upload_to_gcs(denoised_audio_path, f"{gcs_bucket}/{sanitized_denoised_audio_filename}")

                return video_path, denoised_audio_path, original_audio_path
                    
            except yt_dlp.utils.DownloadError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"YouTube 다운로드 오류: {str(e)}"
                )
                
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

async def process_video_file(video_path: str, task_id: str, denoised_audio_path: str = None, original_audio_path: str = None):
    """비디오 파일 처리 프로세스"""
    try:
        # STT: 음성을 텍스트로 변환
        await task_manager.update_task_status(
            task_id,
            status=TaskStatus.PROCESSING,
            stage=ProcessingStage.STT,
            progress=0
        )
        
        transcript = await stt_service.process_video(video_path, denoised_audio_path, original_audio_path)
        if not transcript:
            raise Exception("음성 인식에 실패했습니다.")
            
        await task_manager.update_task_status(
            task_id,
            status=TaskStatus.PROCESSING,
            stage=ProcessingStage.TRANSLATION,
            progress=33
        )
        
        # NMT: 영어 텍스트를 한국어로 번역
        input_filename = os.path.basename(video_path)
        translated_text = await nmt_service.process_transcript(transcript, task_id, input_filename)
        if not translated_text:
            raise Exception("번역에 실패했습니다.")
            
        await task_manager.update_task_status(
            task_id,
            status=TaskStatus.PROCESSING,
            stage=ProcessingStage.TTS,
            progress=66
        )
        
        # TTS: 번역된 텍스트를 음성으로 변환
        tts_audio_path = await tts_service.process_text(task_id, video_path)
        if not tts_audio_path:
            raise Exception("음성 합성에 실패했습니다.")
        
        # 비디오와 오디오 병합
        output_path = await video_audio_merger.process_video(task_id, video_path, tts_audio_path, original_audio_path)
        if not output_path:
            raise Exception("비디오 합성에 실패했습니다.")
        
        # 작업 완료
        await task_manager.complete_task(task_id, output_path)
        
    except Exception as e:
        await task_manager.fail_task(task_id, str(e))
        raise e

@router.post("")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """MP4 파일 업로드 엔드포인트"""
    if not file.filename.endswith('.mp4'):
        raise HTTPException(status_code=400, detail="MP4 파일만 업로드 가능합니다.")
    
    try:
        # 파일 이름 정제
        original_filename = file.filename
        sanitized_filename = sanitize_filename(os.path.splitext(original_filename)[0]) + ".mp4"
        
        print(f"원본 파일명: {original_filename}")
        print(f"정제된 파일명: {sanitized_filename}")
        
        # input_videos 디렉토리 경로 설정
        input_videos_dir = os.path.join(config.TEMP_DIR, "input_videos")
        Path(input_videos_dir).mkdir(parents=True, exist_ok=True)
        
        # 정제된 이름으로 input_videos 디렉토리에 파일 저장
        video_path = os.path.join(input_videos_dir, sanitized_filename)
        with open(video_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            
        # 오디오 추출 경로 설정 (정제된 이름 사용, input_videos 디렉토리에 저장)
        sanitized_base = os.path.splitext(sanitized_filename)[0]
        denoised_audio_path = os.path.join(input_videos_dir, f"{sanitized_base}_denoised.wav")
        original_audio_path = os.path.join(input_videos_dir, f"{sanitized_base}.wav")
        
        # 오디오 추출 함수 호출
        denoised_audio_path, original_audio_path = await extract_audio(
            video_path, 
            original_audio_path, 
            denoised_audio_path
        )
        
        # GCS 버킷에 업로드 (정제된 파일 이름 사용)
        gcs_bucket = "gs://onevoice-test-bucket/resources/input_videos"
        # 정제된 파일명 사용
        sanitized_video_filename = os.path.basename(video_path)
        sanitized_original_audio_filename = os.path.basename(original_audio_path)
        sanitized_denoised_audio_filename = os.path.basename(denoised_audio_path)
        
        await upload_to_gcs(video_path, f"{gcs_bucket}/{sanitized_video_filename}")
        await upload_to_gcs(original_audio_path, f"{gcs_bucket}/{sanitized_original_audio_filename}")
        await upload_to_gcs(denoised_audio_path, f"{gcs_bucket}/{sanitized_denoised_audio_filename}")
        
        # 작업 ID 생성
        task_id = str(uuid.uuid4())
        await task_manager.create_task(task_id)
        
        # 백그라운드 작업 시작
        background_tasks.add_task(
            process_video_file,
            video_path,
            task_id,
            denoised_audio_path,
            original_audio_path
        )
        
        return {"task_id": task_id, "status": TaskStatus.PENDING}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.options("/youtube")
async def youtube_options():
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "3600",
        },
        status_code=200
    )

@router.options("")
async def upload_options():
    return JSONResponse(
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "3600",
        },
        status_code=200
    )

@router.post("/youtube")
async def process_youtube(
    background_tasks: BackgroundTasks,
    request: YouTubeRequest
):
    """YouTube 비디오 처리 엔드포인트"""
    try:
        # URL 유효성 검사
        if not request.url or not isinstance(request.url, str):
            raise HTTPException(status_code=400, detail="유효한 YouTube URL을 입력해주세요.")

        # 비디오 다운로드
        video_path, denoised_audio_path, original_audio_path = await download_youtube_video(request.url)
        if not video_path:
            raise HTTPException(status_code=500, detail="비디오 다운로드에 실패했습니다.")
        
        # 작업 ID 생성
        task_id = str(uuid.uuid4())
        await task_manager.create_task(task_id)
        
        # 백그라운드 작업 시작
        background_tasks.add_task(
            process_video_file,
            video_path,
            task_id,
            denoised_audio_path,
            original_audio_path
        )
        
        return {"task_id": task_id, "status": TaskStatus.PENDING}
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}")
async def get_status(task_id: str):
    """작업 상태 조회 엔드포인트"""
    task_status = await task_manager.get_task_status(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return task_status

@router.get("/download/{task_id}")
async def download_video(task_id: str):
    """완성된 비디오 파일 다운로드"""
    try:
        # 작업 상태 확인
        task_status = await task_manager.get_task_status(task_id)
        if not task_status:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
            
        if task_status["status"] != TaskStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="아직 처리가 완료되지 않았습니다.")
            
        if not task_status.get("result"):
            raise HTTPException(status_code=404, detail="결과 파일을 찾을 수 없습니다.")
        
        # 결과 파일 경로 처리
        result_path = task_status.get("result")
        # 상대 경로인 경우 TEMP_DIR과 결합
        if not os.path.isabs(result_path):
            full_path = os.path.join(config.TEMP_DIR, result_path)
        else:
            # 절대 경로인 경우 그대로 사용
            full_path = result_path
            
        # 파일이 존재하는지 확인
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail=f"결과 파일을 찾을 수 없습니다: {full_path}")
            
        # 파일 응답 반환
        return FileResponse(
            full_path,
            media_type="video/mp4",
            filename=os.path.basename(full_path)
        )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"다운로드 중 오류가 발생했습니다: {str(e)}")

@router.post("/feedback/{task_id}")
async def submit_feedback(task_id: str, request: FeedbackRequest):
    """피드백 제출 엔드포인트"""
    task_status = await task_manager.get_task_status(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    if not 0 <= request.rating <= 5:
        raise HTTPException(status_code=400, detail="평점은 0에서 5 사이여야 합니다.")
    
    # 피드백 저장 (Redis에 저장)
    feedback_key = f"feedback:{task_id}"
    task_manager.redis.set(feedback_key, request.rating)
    
    return {"message": "피드백이 성공적으로 저장되었습니다."}

@router.post("/update-status/{task_id}")
async def update_task_status(task_id: str, status_update: TaskStatusUpdate):
    """작업 상태 업데이트 엔드포인트 (개발용)"""
    try:
        # Redis에서 작업 상태 가져오기
        task_data = await task_manager.get_task_status(task_id)
        if not task_data:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
        
        # 상태 업데이트
        task_data["status"] = status_update.status
        if status_update.stage:
            task_data["stage"] = status_update.stage
        if status_update.progress is not None:
            task_data["progress"] = status_update.progress
        if status_update.result:
            task_data["result"] = status_update.result
        if status_update.error:
            task_data["error"] = status_update.error
        
        # Redis에 업데이트된 상태 저장
        task_manager.redis.set(f"task:{task_id}", json.dumps(task_data))
        
        return {"message": "작업 상태가 업데이트되었습니다.", "task_data": task_data}
    
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e)) 