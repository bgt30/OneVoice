import os
from google.cloud import speech_v2 as speech
from google.cloud import storage
from pathlib import Path
from typing import Optional
import asyncio
from . import config
import subprocess
import time
import tempfile
import json

class STTService:
    def __init__(self):
        self.client = speech.SpeechClient()
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
            
            # 결과를 저장할 GCS 경로 생성
            base_name = os.path.splitext(file_name)[0]
            result_filename = f"{base_name}_transcript_{int(time.time())}"
            results_uri = f"gs://{self.bucket_name}/resources/text_en/{result_filename}/"
            
            print(f"STT: GCS에 업로드된 파일 사용: {gcs_uri}")
            print(f"STT: 결과 저장 위치: {results_uri}")
            
            # v2 인식기 위치 형식 지정
            recognizer = "projects/7923538798/locations/global/recognizers/onevoice-recognizer"
            
            # 음성 인식 요청 생성
            request = speech.BatchRecognizeRequest(
                recognizer=recognizer,
                files=[speech.BatchRecognizeFileMetadata(uri=gcs_uri)],
                config=speech.RecognitionConfig(
                    auto_decoding_config=speech.AutoDetectDecodingConfig(),
                    language_codes=["en-US"],  # 한국어 인식
                    model="latest_long",  # 긴 오디오에 적합한 모델
                    features=speech.RecognitionFeatures(
                        enable_word_time_offsets=True,  # 단어별 타임스탬프 활성화
                        enable_automatic_punctuation=True  # 자동 구두점 추가
                    )
                ),
                recognition_output_config=speech.RecognitionOutputConfig(
                    gcs_output_config=speech.GcsOutputConfig(
                        uri=results_uri
                    )
                )
            )

            # 비동기 음성 인식 수행
            operation = self.client.batch_recognize(request=request)
            
            # 진행 상황 모니터링 및 결과 대기
            while not operation.done():
                await asyncio.sleep(5)
            
            response = operation.result()
            
            # 결과 확인
            if not response.results:
                print("음성 인식 결과가 없습니다.")
                return None
                
            # 결과 파일 경로 가져오기
            transcript = ""
            for file_result in response.results.values():
                # GCS에서 결과 파일 내용 가져오기
                result_uri = file_result.uri
                print(f"결과 파일 URI: {result_uri}")
                
                # GCS에서 결과 파일 다운로드
                transcript = await self._download_and_parse_results(result_uri)
                if transcript:
                    break  # 첫 번째 결과 파일만 사용
            
            if not transcript:
                print("결과 파일을 처리할 수 없습니다.")
                return None
                
            # 결과 파일 저장
            file_name = os.path.basename(audio_path).replace(".wav", "_transcript.txt")
            output_path = os.path.join(self.output_dir, file_name)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(transcript)

            return transcript

        except Exception as e:
            print(f"음성 인식 실패: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None
            
    async def _download_and_parse_results(self, result_uri: str) -> str:
        """
        GCS에서 결과 파일을 다운로드하고 파싱
        
        Args:
            result_uri (str): 결과 파일의 GCS URI
            
        Returns:
            str: 파싱된 트랜스크립트 텍스트
        """
        try:
            # URI에서 버킷 이름과 객체 이름 추출
            # gs://bucket_name/object_name
            uri_parts = result_uri.replace("gs://", "").split("/", 1)
            if len(uri_parts) != 2:
                raise ValueError(f"Invalid GCS URI: {result_uri}")
                
            bucket_name = uri_parts[0]
            object_name = uri_parts[1]
            
            # GCS에서 파일 가져오기
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(object_name)
            
            # 결과 파일 이름 생성
            result_filename = os.path.basename(object_name)
            local_result_path = os.path.join(self.output_dir, result_filename)
            
            # GCS에서 파일 다운로드하여 text_en 디렉토리에 저장
            blob.download_to_filename(local_result_path)
            print(f"결과 파일 다운로드 완료: {local_result_path}")
            
            # JSON 파일 읽기
            with open(local_result_path, "r", encoding="utf-8") as f:
                results_json = json.load(f)
                
            # 문장 구성을 위한 변수 초기화
            current_sentence = ""
            sentence_start_time = None
            sentence_end_time = None
            words_with_time = []
            
            # JSON 결과 파싱하여 트랜스크립트 생성
            transcript = ""
            
            # Speech v2 JSON 결과 구조 파싱
            if "results" in results_json:
                for result in results_json["results"]:
                    if "alternatives" in result and len(result["alternatives"]) > 0:
                        alternative = result["alternatives"][0]  # 첫 번째 대안만 사용
                        
                        if "words" in alternative:
                            for word_info in alternative["words"]:
                                word = word_info["word"]
                                start_offset = word_info["startOffset"]
                                end_offset = word_info["endOffset"]
                                
                                # 's' 문자가 있으면 제거하고 float로 변환
                                if isinstance(start_offset, str) and 's' in start_offset:
                                    start_time = float(start_offset.replace('s', ''))
                                else:
                                    start_time = float(start_offset)
                                    
                                if isinstance(end_offset, str) and 's' in end_offset:
                                    end_time = float(end_offset.replace('s', ''))
                                else:
                                    end_time = float(end_offset)
                                
                                # 단어 정보 저장
                                words_with_time.append({
                                    "word": word,
                                    "start_time": start_time,
                                    "end_time": end_time
                                })
            
            # 단어들을 구두점 기준으로 문장으로 병합
            if words_with_time:
                current_sentence = words_with_time[0]["word"]
                sentence_start_time = words_with_time[0]["start_time"]
                sentence_end_time = words_with_time[0]["end_time"]
                sentence_has_content = True  # 현재 문장이 내용을 가지고 있는지 추적
                
                for i in range(1, len(words_with_time)):
                    word_info = words_with_time[i]
                    word = word_info["word"]
                    
                    # 구두점이 있는지 확인
                    if any(punct in word for punct in ['.', '?', '!']):
                        # 현재 문장에 단어 추가 (구두점 포함)
                        current_sentence += " " + word
                        sentence_end_time = word_info["end_time"]
                        
                        # 구두점이 있으면 문장 완성 및 저장
                        if sentence_has_content and sentence_start_time is not None:
                            transcript += f"[{sentence_start_time:.2f}s - {sentence_end_time:.2f}s] {current_sentence}\n"
                        
                        # 새 문장 초기화
                        sentence_has_content = False
                        current_sentence = ""
                        
                        # 다음 단어가 있으면 새 문장 시작
                        if i < len(words_with_time) - 1:
                            # 다음 단어의 시작 시간이 새 문장의 시작 시간이 됨
                            sentence_start_time = words_with_time[i+1]["start_time"]
                    else:
                        # 구두점이 없는 일반 단어인 경우
                        if not sentence_has_content:
                            # 새 문장의 첫 단어
                            current_sentence = word
                            sentence_has_content = True
                            # 시작 시간은 이미 설정되어 있음 (이전 구두점 처리 단계에서)
                        else:
                            # 문장에 단어 추가
                            current_sentence += " " + word
                        
                        sentence_end_time = word_info["end_time"]
                
                # 마지막 단어 이후 처리 (남은 문장 있는 경우)
                if sentence_has_content and sentence_start_time is not None:
                    transcript += f"[{sentence_start_time:.2f}s - {sentence_end_time:.2f}s] {current_sentence}\n"
            
            # 파싱 완료 후 JSON 파일 삭제 (옵션)
            os.unlink(local_result_path)
            
            return transcript
            
        except Exception as e:
            print(f"결과 파일 처리 오류: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return ""

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