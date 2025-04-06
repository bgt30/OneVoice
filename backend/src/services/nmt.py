from google.cloud import storage
import os
from pathlib import Path
import re
from typing import Optional
import pandas as pd
from . import config
from google.cloud import translate_v3 as translate

class NMTService:
    def __init__(self):
        # 번역 클라이언트 초기화
        self.client = translate.TranslationServiceClient()
        self.project_id = config.PROJECT_ID
        self.location = config.LOCATION
        self.parent = f"projects/{self.project_id}/locations/{self.location}"
        
        self.storage_client = storage.Client()
        self.bucket_name = "onevoice-test-bucket"
        self.output_dir = os.path.join(config.TEMP_DIR, "text_ko")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    async def _upload_to_gcs(self, local_path: str, gcs_path: str) -> bool:
        """GCS에 파일 업로드"""
        try:
            # GCS 경로 파싱 (gs://bucket-name/path/to/file)
            gcs_parts = gcs_path.replace("gs://", "").split("/", 1)
            bucket_name = gcs_parts[0]
            blob_name = gcs_parts[1] if len(gcs_parts) > 1 else os.path.basename(local_path)
            
            # 스토리지 클라이언트 사용
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # 파일 업로드
            print(f"파일 업로드 시작: {local_path} -> {gcs_path}")
            blob.upload_from_filename(local_path)
            print(f"파일 업로드 완료: {local_path} -> {gcs_path}")
            
            return True
        except Exception as e:
            print(f"GCS 업로드 오류: {str(e)}")
            return False

    async def translate_text(self, text: str) -> str:
        """Translation LLM 모델을 사용하여 텍스트 번역"""
        try:
            # 번역 요청 준비
            request = translate.TranslateTextRequest(
                parent=self.parent,
                contents=[text],
                mime_type="text/plain",  # 텍스트 형식 지정
                source_language_code="en",  # 영어
                target_language_code="ko",  # 한국어
                # model="general/nmt"  # Translation LLM 모델 지정
            )
            
            # 번역 요청 실행
            response = self.client.translate_text(request)
            
            # 응답에서 번역된 텍스트 추출
            if response.translations and len(response.translations) > 0:
                translated = response.translations[0].translated_text
                return translated
            else:
                print("번역 결과가 없습니다.")
                return None
            
        except Exception as e:
            print(f"번역 실패: {str(e)}")
            return None

    async def process_transcript(self, text: str, task_id: str, input_filename: str) -> Optional[str]:
        """
        타임스탬프가 포함된 텍스트를 번역 (입력 형식: [start_time s - end_time s] 화자 speaker_id: text)
        
        Args:
            text (str): 번역할 텍스트 (파일 전체 내용)
            task_id (str): 작업 ID
            input_filename (str): 입력 파일명
        """
        try:
            translated_lines = []
            lines = text.strip().split('\n')
            total_lines = len(lines)
            
            # 각 줄을 처리하기 위한 정규 표현식
            line_pattern = re.compile(r"^\s*\[\s*(\d+\.\d+)s\s*-\s*(\d+\.\d+)s\s*\]\s*화자\s*(\w+):\s*(.*)$")
            
            for i, line in enumerate(lines):
                match = line_pattern.match(line)
                
                if match:
                    start_time_str = match.group(1)
                    end_time_str = match.group(2)
                    speaker_id = match.group(3)
                    text_to_translate = match.group(4).strip()
                    
                    # 텍스트가 비어있지 않은 경우에만 번역 시도
                    if text_to_translate:
                        translated_text = await self.translate_text(text_to_translate)
                        if not translated_text:
                            print(f"경고: 라인 {i+1} 번역 실패: {line}")
                            continue
                        
                        # TSV 형식으로 데이터 저장 (시작 시간, 종료 시간, 화자 ID, 번역된 텍스트)
                        translated_lines.append(f"{start_time_str}\t{end_time_str}\t{speaker_id}\t{translated_text}")
                    else:
                        # 텍스트 내용이 없는 경우 빈 줄로 추가 (선택 사항)
                        # translated_lines.append(f"{start_time_str}\t{end_time_str}\t{speaker_id}\t")
                        print(f"정보: 라인 {i+1} 텍스트 내용 없음: {line}")
                else:
                    print(f"경고: 라인 {i+1} 형식이 맞지 않아 건너뜁니다: {line}")
            
            # 입력 파일명에서 확장자를 제거하고 .tsv 확장자 추가
            base_filename = os.path.splitext(input_filename)[0]
            output_filename = f"{base_filename}.tsv"
            
            # TSV 파일로 저장
            output_path = os.path.join(self.output_dir, output_filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                # 헤더 순서 변경: start_time, end_time, speaker_id, translated_text
                f.write("start_time\tend_time\tspeaker_id\ttranslated_text\n")
                f.write('\n'.join(translated_lines))
            
            # GCS에 업로드
            gcs_bucket = "gs://onevoice-test-bucket/resources/text_ko"
            await self._upload_to_gcs(output_path, f"{gcs_bucket}/{output_filename}")
            
            return '\n'.join(translated_lines)
            
        except Exception as e:
            print(f"트랜스크립트 처리 실패: {str(e)}")
            return None

# 서비스 인스턴스 생성
nmt_service = NMTService() 