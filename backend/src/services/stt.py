import os
from google.cloud import speech_v1
from google.cloud import storage
from google.cloud.speech_v1 import types
from . import config
import subprocess
from pathlib import Path
from typing import Optional
import asyncio

class STTService:
    def __init__(self):
        self.client = speech_v1.SpeechClient()
        self.storage_client = storage.Client()
        self.bucket_name = "onevoice-test-bucket"
        self.output_dir = os.path.join(config.TEMP_DIR, "text_en")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """
        오디오 파일을 텍스트로 변환
        
        Args:
            audio_path (str): 노이즈가 제거된 오디오 파일 경로
            
        Returns:
            Optional[str]: 변환된 텍스트
        """
        try:
            # GCS URI 생성 (이미 업로드된 파일 사용)
            file_name = os.path.basename(audio_path)
            gcs_uri = f"gs://{self.bucket_name}/resources/input_videos/{file_name}"
            
            print(f"STT: GCS에 업로드된 파일 사용: {gcs_uri}")
            
            # 음성 인식 설정
            audio = types.RecognitionAudio(uri=gcs_uri)
            config = types.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code="en-US",
                use_enhanced=True,
                model="video",
                sample_rate_hertz=16000,
                enable_automatic_punctuation=True,
                audio_channel_count=1,
                enable_word_time_offsets=True,
            )

            # 음성 인식 수행
            operation = self.client.long_running_recognize(config=config, audio=audio)
            
            # 진행 상황 모니터링 및 결과 대기
            while not operation.done():
                await asyncio.sleep(5)
            
            response = operation.result()
            
            if not response.results:
                return None

            # 결과 텍스트 생성
            transcript = ""
            current_sentence = ""
            sentence_start_time = None
            sentence_end_time = None
            previous_end_time = 0.0
            epsilon = 1e-6

            for result in response.results:
                for word_info in result.alternatives[0].words:
                    word = word_info.word
                    start_time = round(word_info.start_time.total_seconds(), 2)
                    end_time = round(word_info.end_time.total_seconds(), 2)

                    # 문장 내/간 빈 구간 감지
                    time_gap = round(start_time - previous_end_time, 2)
                    if time_gap > epsilon:
                        if time_gap >= 1.5:
                            if current_sentence.strip():
                                transcript += f"[{sentence_start_time:.2f}s - {sentence_end_time:.2f}s] {current_sentence.strip()}\n"
                            transcript += f"[{previous_end_time:.2f}s - {start_time:.2f}s] \n"
                            current_sentence = ""
                            sentence_start_time = None
                            sentence_end_time = None

                    # 현재 문장에 단어 추가
                    current_sentence += word + " "

                    # 문장 시작 시간 설정
                    if sentence_start_time is None:
                        sentence_start_time = start_time

                    # 문장 종료 시간 업데이트
                    sentence_end_time = end_time

                    # 문장 종료 조건
                    if word[-1] in ['.', '?', '!']:
                        if current_sentence.strip():
                            transcript += f"[{sentence_start_time:.2f}s - {sentence_end_time:.2f}s] {current_sentence.strip()}\n"
                        current_sentence = ""
                        sentence_start_time = None
                        sentence_end_time = None

                    previous_end_time = end_time

            # 남은 문장 처리
            if current_sentence.strip():
                transcript += f"[{sentence_start_time:.2f}s - {sentence_end_time:.2f}s] {current_sentence.strip()}\n"

            # 결과 파일 저장
            file_name = os.path.basename(audio_path).replace(".wav", "_transcript.txt")
            output_path = os.path.join(self.output_dir, file_name)
            
            # 짧은 문장 병합 처리
            merged_transcript = self._merge_short_sentences(transcript)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(merged_transcript)

            return merged_transcript

        except Exception as e:
            print(f"음성 인식 실패: {str(e)}")
            return None

    def _merge_short_sentences(self, transcript: str) -> str:
        """
        2초 이하의 짧은 문장을 이전 문장과 병합하는 함수
        
        Args:
            transcript (str): 타임스탬프가 포함된 원본 텍스트
            
        Returns:
            str: 짧은 문장이 병합된 텍스트
        """
        lines = transcript.strip().split('\n')
        if len(lines) <= 1:
            return transcript
            
        merged_lines = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i]
            # 빈 줄이거나 타임스탬프가 없는 줄은 그대로 추가
            if not current_line.strip() or not current_line.startswith('['):
                merged_lines.append(current_line)
                i += 1
                continue
                
            # 타임스탬프와 텍스트 분리
            try:
                timestamp_part = current_line[current_line.find('['): current_line.find(']') + 1]
                text_part = current_line[current_line.find(']') + 1:].strip()
                
                # 타임스탬프 파싱 (예: [0.00s - 2.50s])
                times = timestamp_part.replace('[', '').replace(']', '').replace('s', '').split(' - ')
                start_time = float(times[0])
                end_time = float(times[1])
                duration = end_time - start_time
                
                # 현재 문장을 처리
                if i == 0 or duration > 2.0:
                    # 첫 문장이거나 2초보다 긴 문장은 그대로 추가
                    merged_lines.append(current_line)
                    i += 1
                else:
                    # 2초 이하인 짧은 문장 처리
                    prev_line = merged_lines[-1]
                    
                    # 이전 문장에서 타임스탬프와 텍스트 분리
                    prev_timestamp_part = prev_line[prev_line.find('['): prev_line.find(']') + 1]
                    prev_text_part = prev_line[prev_line.find(']') + 1:].strip()
                    
                    # 이전 문장의 타임스탬프 파싱
                    prev_times = prev_timestamp_part.replace('[', '').replace(']', '').replace('s', '').split(' - ')
                    prev_start_time = float(prev_times[0])
                    
                    # 병합된 문장 생성
                    merged_timestamp = f"[{prev_start_time:.2f}s - {end_time:.2f}s]"
                    merged_text = f"{prev_text_part} {text_part}"
                    
                    # 이전 문장 업데이트
                    merged_lines[-1] = f"{merged_timestamp} {merged_text}"
                    i += 1
                    
                    # 연속된 짧은 문장 처리
                    j = i
                    while j < len(lines):
                        next_line = lines[j]
                        if not next_line.strip() or not next_line.startswith('['):
                            break
                            
                        # 다음 문장의 타임스탬프와 텍스트 분리
                        next_timestamp_part = next_line[next_line.find('['): next_line.find(']') + 1]
                        next_text_part = next_line[next_line.find(']') + 1:].strip()
                        
                        # 다음 문장의 타임스탬프 파싱
                        next_times = next_timestamp_part.replace('[', '').replace(']', '').replace('s', '').split(' - ')
                        next_start_time = float(next_times[0])
                        next_end_time = float(next_times[1])
                        next_duration = next_end_time - next_start_time
                        
                        if next_duration <= 2.0:
                            # 다음 문장도 2초 이하면 계속 병합
                            merged_timestamp = f"[{prev_start_time:.2f}s - {next_end_time:.2f}s]"
                            merged_text = f"{merged_text} {next_text_part}"
                            merged_lines[-1] = f"{merged_timestamp} {merged_text}"
                            j += 1
                            i = j
                        else:
                            break
            except Exception as e:
                print(f"문장 병합 중 오류 발생: {str(e)}, 줄: {current_line}")
                merged_lines.append(current_line)
                i += 1
                
        return '\n'.join(merged_lines)

    async def _upload_to_gcs(self, local_path: str, destination_blob_name: str) -> bool:
        """GCS에 파일 업로드"""
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(destination_blob_name)
            
            print(f"파일 업로드 시작: {local_path} -> gs://{self.bucket_name}/{destination_blob_name}")
            blob.upload_from_filename(local_path)
            print(f"파일 업로드 완료: {local_path} -> gs://{self.bucket_name}/{destination_blob_name}")
            
            return True
        except Exception as e:
            print(f"GCS 업로드 오류: {str(e)}")
            return False

    async def process_video(self, video_path: str, denoised_audio_path: str = None, original_audio_path: str = None) -> Optional[str]:
        """비디오에서 텍스트로 변환"""
        try:
            # 노이즈가 제거된 오디오가 없으면 오류 발생
            if not denoised_audio_path:
                raise Exception("노이즈가 제거된 오디오 파일이 필요합니다.")

            # 텍스트 변환 (노이즈가 제거된 오디오만 사용)
            return await self.transcribe_audio(denoised_audio_path)

        except Exception as e:
            print(f"비디오 처리 실패: {str(e)}")
            return None

# 서비스 인스턴스 생성
stt_service = STTService() 