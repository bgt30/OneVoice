import os
from google.cloud import texttospeech, storage
from pathlib import Path
from typing import Optional, List, Tuple
import pandas as pd
from pydub import AudioSegment
import io
import ffmpeg
import time
from . import config

class TTSService:
    def __init__(self):
        self.client = config.tts_client
        self.storage_client = storage.Client()
        self.bucket_name = "onevoice-test-bucket"
        self.output_dir = os.path.join(config.TEMP_DIR, "audio")
        self.text_ko_dir = os.path.join(config.TEMP_DIR, "text_ko")

    async def delete_existing_file(self, gcs_uri: str) -> bool:
        """GCS에서 기존 파일 삭제"""
        try:
            bucket_name = gcs_uri.split('/')[2]
            blob_name = '/'.join(gcs_uri.split('/')[3:])
            
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if blob.exists():
                blob.delete()
                print(f"파일 삭제 완료: {gcs_uri}")
            return True
        except Exception as e:
            print(f"파일 삭제 실패: {str(e)}")
            return False

    def generate_silence(self, duration_sec: float) -> AudioSegment:
        """무음 세그먼트 생성"""
        return AudioSegment.silent(duration=int(duration_sec * 1000))

    def remove_timestamps(self, text: str) -> str:
        """타임스탬프 제거"""
        import re
        return re.sub(r'\[\d+\.\d+s - \d+\.\d+s\]', '', text).strip()

    async def calculate_speaking_rate(self, text: str, target_duration: float) -> float:
        """목표 시간에 맞는 말하기 속도 계산"""
        try:
            # 기본 설정으로 음성 합성 시도
            input_text = texttospeech.SynthesisInput(text=text)
            voice = config.VOICE_CONFIG
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=1.0  # 기본 속도
            )
            
            response = self.client.synthesize_speech(
                input=input_text,
                voice=voice,
                audio_config=audio_config
            )
            
            # 임시 파일로 저장하여 길이 측정
            temp_audio = AudioSegment.from_wav(io.BytesIO(response.audio_content))
            current_duration = len(temp_audio) / 1000  # 밀리초 -> 초
            
            # 현재 지속 시간과 타겟 지속 시간 비교
            if current_duration > target_duration:
                # 타임스탬프 시간보다 길다면 속도를 빠르게 조절
                speaking_rate = current_duration / target_duration
            else:
                # 타임스탬프 시간보다 짧다면 속도는 1.0으로 유지
                speaking_rate = 1.0
            
            return speaking_rate
            
        except Exception as e:
            print(f"말하기 속도 계산 실패: {str(e)}")
            return 1.0

    async def synthesize_segment(self, text: str, speaking_rate: float = 1.0) -> Optional[AudioSegment]:
        """텍스트 세그먼트를 음성으로 변환"""
        try:
            input_text = texttospeech.SynthesisInput(text=text)
            voice = config.VOICE_CONFIG
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                speaking_rate=speaking_rate
            )
            
            response = self.client.synthesize_speech(
                input=input_text,
                voice=voice,
                audio_config=audio_config
            )
            
            return AudioSegment.from_wav(io.BytesIO(response.audio_content))
            
        except Exception as e:
            print(f"음성 합성 실패: {str(e)}")
            return None

    async def process_tsv_segments(self, tsv_path: str, task_id: str) -> Optional[str]:
        """TSV 파일의 세그먼트를 처리하여 음성으로 변환"""
        try:
            output_path = os.path.join(self.output_dir, f"{task_id}_merged.mp3")
            final_audio = AudioSegment.empty()
            epsilon = 1e-6  # 부동소수점 오차 보정용
            
            # 파일 직접 읽기 방식으로 변경
            with open(tsv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines:  # 파일이 비어 있는 경우
                    print("파일이 비어 있습니다.")
                    return None
                
                # 헤더가 있는지 확인하고 스킵
                if len(lines) > 0 and lines[0].strip().startswith('start'):  # 헤더가 있는 경우
                    lines = lines[1:]  # 헤더 제외
                
                total_lines = len(lines)
                last_check_time = time.time()  # 마지막 체크 시간 초기화
                previous_end_time = 0.0  # 이전 세그먼트의 종료 시간 초기화
                
                for i, line in enumerate(lines, start=1):
                    parts = line.strip().split('\t')
                    if len(parts) < 3:
                        parts.extend([''] * (3 - len(parts)))
                    
                    try:
                        start = float(parts[0])
                        end = float(parts[1])
                        text = parts[2].strip()
                        
                        # 이전 세그먼트와 현재 세그먼트 사이의 빈 시간 처리 (부동소수점 오차 보정)
                        time_gap = start - previous_end_time
                        if time_gap > epsilon:  # 0보다 큰 경우에만 처리
                            silence_duration = time_gap
                            silence = self.generate_silence(silence_duration)
                            final_audio += silence
                        
                        # 현재 세그먼트 처리
                        duration = end - start
                        
                        if text:  # 텍스트가 있는 경우
                            # 말하기 속도 계산
                            speaking_rate = await self.calculate_speaking_rate(text, duration)
                            
                            # 음성 합성
                            segment = await self.synthesize_segment(text, speaking_rate)
                            if segment is None:
                                continue
                            
                            # 타임스탬프 시간보다 짧다면 무음 추가 (부동소수점 오차 보정)
                            segment_duration = len(segment) / 1000  # 밀리초 -> 초
                            if segment_duration < duration - epsilon:
                                silence = AudioSegment.silent(duration=int((duration - segment_duration) * 1000))
                                segment += silence
                            elif segment_duration > duration + epsilon:
                                # 세그먼트가 길면 잘라내기
                                segment = segment[:int(duration * 1000)]
                        else:  # 텍스트 없는 경우 무음
                            segment = self.generate_silence(duration)
                        
                        final_audio += segment
                        previous_end_time = end  # 이전 세그먼트의 종료 시간 업데이트
                    
                    except ValueError as ve:
                        print(f"잘못된 타임스탬프 형식: {line.strip()} - {str(ve)}")
                        continue
                    except Exception as e:
                        print(f"세그먼트 처리 중 오류 발생: {str(e)}")
                        continue
                    
                    # 5초마다 진행률 체크
                    current_time = time.time()
                    if current_time - last_check_time >= 5:
                        progress = (i / total_lines) * 100
                        print(f"진행률: {progress:.2f}% ({i}/{total_lines})")
                        last_check_time = current_time
            
            # 최종 오디오 파일 저장 (MP3 형식 유지)
            final_audio.export(output_path, format="mp3")
            print(f"TTS 처리 완료: {output_path}")
            
            return output_path
            
        except Exception as e:
            print(f"TSV 세그먼트 처리 실패: {str(e)}")
            return None

    async def find_local_tsv_file(self, input_filename: str) -> Optional[str]:
        """로컬 text_ko 디렉토리에서 TSV 파일 찾기"""
        try:
            # 입력 파일명에서 확장자를 제외한 이름 추출
            base_filename = os.path.splitext(input_filename)[0]
            tsv_filename = f"{base_filename}.tsv"
            local_path = os.path.join(self.text_ko_dir, tsv_filename)
            
            # 파일 존재 여부 확인
            if os.path.exists(local_path):
                print(f"로컬 TSV 파일 찾음: {local_path}")
                return local_path
            else:
                print(f"로컬 TSV 파일을 찾을 수 없습니다: {local_path}")
                return None
            
        except Exception as e:
            print(f"로컬 TSV 파일 검색 실패: {str(e)}")
            return None

    async def process_text(self, task_id: str, video_path: str) -> Optional[str]:
        """전체 TTS 처리 프로세스"""
        try:
            # 입력 파일명 추출
            input_filename = os.path.basename(video_path)
            
            # 로컬 text_ko 디렉토리에서 TSV 파일 찾기
            tsv_path = await self.find_local_tsv_file(input_filename)
            if not tsv_path:
                raise Exception("로컬 TSV 파일을 찾을 수 없습니다")
            
            # TSV 파일 처리
            output_path = await self.process_tsv_segments(tsv_path, task_id)
            if not output_path:
                raise Exception("TSV 세그먼트 처리 실패")
            
            return output_path
            
        except Exception as e:
            print(f"TTS 처리 실패: {str(e)}")
            return None

# 서비스 인스턴스 생성
tts_service = TTSService() 