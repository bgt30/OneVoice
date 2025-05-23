import json
from typing import Optional, Dict, Any
import redis
from enum import Enum
import os

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessingStage(str, Enum):
    STT = "stt"
    DIARIZATION = "diarization"
    MERGE = "merge"
    TRANSLATION = "translation"
    TTS = "tts"

class TaskManager:
    def __init__(self):
        redis_host = os.getenv('REDIS_HOST', 'redis')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True,
            socket_connect_timeout=300,
            retry_on_timeout=True
        )

    async def create_task(self, task_id: str) -> None:
        """새로운 작업을 생성합니다."""
        task_data = {
            "status": TaskStatus.PENDING,
            "stage": None,
            "progress": 0,
            "result": None,
            "error": None,
            "diarization_result": None,
            "merged_result": None
        }
        self.redis.set(f"task:{task_id}", json.dumps(task_data))

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """작업의 현재 상태를 조회합니다."""
        task_data = self.redis.get(f"task:{task_id}")
        return json.loads(task_data) if task_data else None

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        stage: Optional[ProcessingStage] = None,
        progress: Optional[float] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
        diarization_result: Optional[str] = None,
        merged_result: Optional[str] = None
    ) -> None:
        """작업 상태를 업데이트합니다."""
        task_data = await self.get_task_status(task_id)
        if task_data:
            if status:
                task_data["status"] = status
            if stage:
                task_data["stage"] = stage
            if progress is not None:
                task_data["progress"] = progress
            if result:
                task_data["result"] = result
            if error:
                task_data["error"] = error
            if diarization_result:
                task_data["diarization_result"] = diarization_result
            if merged_result:
                task_data["merged_result"] = merged_result
            
            self.redis.set(f"task:{task_id}", json.dumps(task_data))

    async def complete_task(self, task_id: str, result: str) -> None:
        """작업을 완료 상태로 표시합니다."""
        await self.update_task_status(
            task_id,
            status=TaskStatus.COMPLETED,
            stage=ProcessingStage.TTS,
            progress=100,
            result=result
        )

    async def fail_task(self, task_id: str, error: str) -> None:
        """작업을 실패 상태로 표시합니다."""
        await self.update_task_status(
            task_id,
            status=TaskStatus.FAILED,
            error=error
        )

    async def update_diarization_result(self, task_id: str, diarization_result: str) -> None:
        """화자 분리 결과를 업데이트합니다."""
        task_data = await self.get_task_status(task_id)
        if task_data:
            task_data["diarization_result"] = diarization_result
            self.redis.set(f"task:{task_id}", json.dumps(task_data))

    async def update_merged_result(self, task_id: str, merged_result: str) -> None:
        """병합된 결과를 업데이트합니다."""
        task_data = await self.get_task_status(task_id)
        if task_data:
            task_data["merged_result"] = merged_result
            self.redis.set(f"task:{task_id}", json.dumps(task_data))

# 전역 TaskManager 인스턴스 생성
task_manager = TaskManager() 