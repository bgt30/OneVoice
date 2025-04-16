import os
import requests
import json
import time
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from . import config

class PyAnnoteClient:
    """PyAnnote.ai API 클라이언트"""
    
    def __init__(self):
        self.api_key = "sk_f0d401256b46428997642f3a9e7c4938"
        self.api_url = "https://api.pyannote.ai/v1"
        self.bucket_name = "onevoice-test-bucket"
        
    async def upload_file_to_pyannote(self, file_path: str) -> Optional[str]:
        """오디오 파일을 PyAnnote.ai에 업로드"""
        try:
            # 파일 이름 가져오기 및 길이 제한
            file_name = os.path.basename(file_path)
            if len(file_name) > 100:
                base, ext = os.path.splitext(file_name)
                file_name = f"{base[:90]}{ext}"  # 확장자 포함 100자 이내로 줄임
                
            # media:// 고유식별자 URL 생성 (타임스탬프 + 파일명)
            timestamp = int(time.time())
            
            # 파일명에서 특수문자 제거하고 알파벳과 숫자만 허용
            import re
            # 알파벳, 숫자만 허용 (모든 하이픈, 언더스코어, 공백 등 제거)
            safe_name = re.sub(r'[^a-zA-Z0-9]', '', os.path.splitext(file_name)[0])
            # 최대 길이 제한
            safe_name = safe_name[:20]
            
            # 최종 object_key 생성 (알파벳, 숫자만 포함)
            object_key = f"{timestamp}{safe_name}"
            
            # media URL 생성
            media_url = f"media://{object_key}"
            
            print(f"생성된 미디어 URL: {media_url}")
            
            # 임시 저장소 생성 요청 (pre-signed URL 얻기)
            create_url = f"{self.api_url}/media/input"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            body = {
                "url": media_url
            }
            
            print(f"임시 저장소 위치 생성 중...")
            
            response = requests.post(create_url, json=body, headers=headers)
            
            if response.status_code not in [200, 201]:
                print(f"임시 저장소 생성 실패: {response.status_code} - {response.text}")
                return None
            
            # 응답에서 pre-signed URL 가져오기
            response_data = response.json()
            presigned_url = response_data.get("url")
            
            if not presigned_url:
                print(f"pre-signed URL을 찾을 수 없음: {response_data}")
                return None
                
            print(f"pre-signed URL 생성됨")
            
            # Content-Type 설정
            content_type = "audio/mpeg" if file_path.lower().endswith('.mp3') else "audio/wav"
            
            with open(file_path, 'rb') as f:
                file_data = f.read()
                
            print(f"파일 업로드 중: {file_path}")
            
            # PUT 요청으로 파일 업로드
            upload_headers = {"Content-Type": content_type}
            upload_response = requests.put(presigned_url, headers=upload_headers, data=file_data)
            
            if upload_response.status_code not in [200, 201]:
                print(f"파일 업로드 실패: {upload_response.status_code} - {upload_response.text}")
                return None
                
            print(f"파일 업로드 성공")
            
            # 원래 media:// URL 반환
            return media_url
            
        except Exception as e:
            print(f"파일 업로드 오류: {e}")
            return None
    
    async def create_diarization_job(self, media_url: str, num_speakers: Optional[int] = None) -> Optional[str]:
        """화자 분리 작업 생성"""
        try:
            # 작업 생성 요청 URL
            job_url = f"{self.api_url}/diarize"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 기본 요청 본문
            body = {
                "url": media_url
            }
            
            # 화자 수가 지정된 경우 설정 추가
            if num_speakers:
                body["numSpeakers"] = num_speakers
                body["confidence"] = False
            
            response = requests.post(job_url, headers=headers, json=body)
            
            if response.status_code in [200, 201]:
                result = response.json()
                job_id = result.get("jobId")
                print(f"화자 분리 작업 생성 성공: Job ID = {job_id}")
                return job_id
            else:
                print(f"화자 분리 작업 생성 실패: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            print(f"화자 분리 작업 생성 오류: {e}")
            return None
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태 확인"""
        try:
            status_url = f"{self.api_url}/jobs/{job_id}"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.get(status_url, headers=headers)
            
            if response.status_code == 200:
                status_data = response.json()
                # 응답에 error 필드가 있는지 확인
                if "failed" in status_data:
                    error_detail = status_data.get("failed", {})
                    print(f"작업 오류 상세: {json.dumps(error_detail, indent=2, ensure_ascii=False)}")
                return status_data
            else:
                print(f"작업 상태 확인 실패: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            print(f"작업 상태 확인 오류: {e}")
            return None
    
    async def get_diarization_result(self, job_id: str) -> Optional[Dict[str, Any]]:
        """화자 분리 결과 가져오기"""
        try:
            result_url = f"{self.api_url}/jobs/{job_id}"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            response = requests.get(result_url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                print("Diarization 결과를 성공적으로 가져왔습니다.")
                
                # 결과에 output이 있는지 확인
                if "output" in result:
                    result = result["output"]  # output 내부의 결과를 사용
                
                return result
            else:
                print(f"Diarization 결과 가져오기 실패: {response.status_code} - {response.text}")
                return None
        
        except Exception as e:
            print(f"Diarization 결과 가져오기 오류: {e}")
            return None


class DiarizationService:
    """화자 분리 서비스"""
    
    def __init__(self):
        self.client = PyAnnoteClient()
        self.output_dir = os.path.join(config.TEMP_DIR, "diarization")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    async def process_audio(self, audio_path: str, num_speakers: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """오디오 파일에 대한 화자 분리 수행"""
        try:
            print(f"화자 분리 시작: {audio_path}")
            
            # 1. PyAnnote.ai에 파일 업로드
            media_url = await self.client.upload_file_to_pyannote(audio_path)
            if not media_url:
                print("오류: 파일 업로드에 실패했습니다.")
                return None
            
            # 2. 화자 분리 작업 생성
            job_id = await self.client.create_diarization_job(media_url, num_speakers)
            if not job_id:
                print("오류: 화자 분리 작업 생성에 실패했습니다.")
                return None
            
            # 3. 작업 완료 대기
            max_attempts = 60  # 최대 60번 시도 (약 10분)
            attempt = 0
            while attempt < max_attempts:
                status_result = await self.client.get_job_status(job_id)
                if not status_result:
                    print("작업 상태 확인 실패")
                    return None
                    
                status = status_result.get("status")
                print(f"현재 작업 상태: {status}")
                
                if status == "succeeded":  # API 응답 상태가 succeeded로 변경됨
                    break
                elif status in ["failed", "error"]:
                    print("작업 처리 중 오류가 발생했습니다.")
                    return None
                
                attempt += 1
                print(f"작업 완료 대기 중... ({attempt}/{max_attempts})")
                await asyncio.sleep(10)  # 10초 대기
            
            if attempt >= max_attempts:
                print("작업 시간 초과")
                return None
            
            # 4. 결과 가져오기
            result = await self.client.get_diarization_result(job_id)
            if not result:
                print("오류: 화자 분리 결과를 가져오는데 실패했습니다.")
                return None
            
            # 5. 결과 저장
            file_name = os.path.basename(audio_path).split('.')[0]
            output_file = os.path.join(self.output_dir, f"{file_name}_diarization.json")
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"화자 분리 결과 저장 완료: {output_file}")
            
            return result
        
        except Exception as e:
            print(f"화자 분리 처리 오류: {e}")
            return None
    
    async def process_video(self, video_path: str, denoised_audio_path: str, original_audio_path: str) -> Optional[Dict[str, Any]]:
        """비디오에서 화자 분리"""
        try:
            # 노이즈가 제거된 오디오 파일 사용
            result = await self.process_audio(denoised_audio_path)
            return result
            
        except Exception as e:
            print(f"비디오 화자 분리 처리 오류: {e}")
            return None


# 서비스 인스턴스 생성
diarization_service = DiarizationService() 