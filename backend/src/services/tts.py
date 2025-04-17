import os
import logging
from google.cloud import texttospeech, storage
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from pydub import AudioSegment
import io
from . import config

# pydub 로깅 비활성화 (WARNING 레벨 이상만 표시)
logging.getLogger("pydub.converter").setLevel(logging.WARNING)

class TTSService:
    def __init__(self):
        self.client = config.tts_client
        self.storage_client = storage.Client()
        self.bucket_name = "onevoice-test-bucket"
        self.output_dir = os.path.join(config.TEMP_DIR, "audio")
        self.text_ko_dir = os.path.join(config.TEMP_DIR, "text_ko")
        
        # 화자별 음성 프로필 정의
        self.voice_profiles = {
            "00": "ko-KR-Chirp3-HD-Aoede",
            "01": "ko-KR-Chirp3-HD-Charon", 
            "02": "ko-KR-Chirp3-HD-Kore",  
            "03": "ko-KR-Chirp3-HD-Fenrir",  
            "04": "ko-KR-Chirp3-HD-Leda",  
        }
        
        # 필요한 디렉토리 생성
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.text_ko_dir).mkdir(parents=True, exist_ok=True)

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

    async def synthesize_segment(self, text: str, target_duration: float, voice_profile: str = None) -> Optional[AudioSegment]:
        """텍스트 세그먼트를 음성으로 변환하고 목표 기간에 맞게 속도 조절"""
        try:
            input_text = texttospeech.SynthesisInput(text=text)
            
            # 음성 프로필이 지정된 경우 해당 프로필 사용, 그렇지 않으면 기본 설정 사용
            if voice_profile:
                voice = texttospeech.VoiceSelectionParams(
                    language_code="ko-KR",
                    name=voice_profile
                )
            else:
                voice = config.VOICE_CONFIG
            
            # 기본 음성 설정 사용 (속도 조절 없음)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16
            )
            
            # 음성 합성 (한 번만 TTS API 호출)
            response = self.client.synthesize_speech(
                input=input_text,
                voice=voice,
                audio_config=audio_config
            )
            
            # 생성된 오디오를 AudioSegment으로 변환
            segment = AudioSegment.from_wav(io.BytesIO(response.audio_content))
            
            # 현재 세그먼트 길이 계산
            current_duration = len(segment) / 1000  # 밀리초 -> 초
            
            # 목표 길이와 비교하여 속도 계산
            epsilon = 1e-6  # 부동소수점 오차 보정용
            
            if abs(current_duration - target_duration) > epsilon:
                if current_duration > target_duration:
                    # 생성된 오디오가 타깃보다 길면 속도를 빠르게 조절 (pydub speedup 사용)
                    speed_factor = current_duration / target_duration
                    if speed_factor > 1.0:
                        try:
                            segment = segment.speedup(playback_speed=speed_factor)
                            print(f"오디오 속도 조절: x{speed_factor:.2f}")
                        except Exception as e:
                            print(f"오디오 속도 조절 실패: {str(e)}")
                else:
                    # 생성된 오디오가 타깃보다 짧으면 그대로 유지하고 필요시 무음 추가
                    pass
            
            # 최종 길이 확인 및 조정 (필요시)
            final_duration = len(segment) / 1000
            if final_duration < target_duration - epsilon:
                # 여전히 짧다면 무음 추가
                silence = self.generate_silence(target_duration - final_duration)
                segment += silence
            elif final_duration > target_duration + epsilon:
                # 여전히 길다면 잘라내기
                segment = segment[:int(target_duration * 1000)]
            
            return segment
            
        except Exception as e:
            print(f"음성 합성 실패: {str(e)}")
            return None

    async def process_tsv_segments(self, tsv_path: str, task_id: str) -> Optional[str]:
        """TSV 파일의 세그먼트를 처리하여 음성으로 변환"""
        try:
            tsv_filename = os.path.basename(tsv_path)  # tsv 파일명 추출
            output_filename = os.path.splitext(tsv_filename)[0] + "_ko.wav"  # 확장자 제거 후 _ko.wav 추가
            output_path = os.path.join(self.output_dir, output_filename)  # 최종 경로 생성
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
                            # 직접 target_duration으로 음성 합성 및 속도 조절
                            segment = await self.synthesize_segment(text, duration)
                            if segment is None:
                                continue
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
            
            # 최종 오디오 파일 저장 (WAV 형식)
            # -loglevel quiet 매개변수를 추가하여 ffmpeg 출력을 비활성화
            final_audio.export(output_path, format="wav", parameters=["-loglevel", "quiet"])
            print(f"TTS 처리 완료: {output_path}")
            
            return output_path
            
        except Exception as e:
            print(f"TSV 세그먼트 처리 실패: {str(e)}")
            return None

    async def process_multi_speaker_tsv(self, tsv_path: str, task_id: str) -> Optional[str]:
        """화자별 음성으로 TSV 파일 처리"""
        try:
            tsv_filename = os.path.basename(tsv_path)  # tsv 파일명 추출
            output_filename = os.path.splitext(tsv_filename)[0] + "_ko.wav"  # 출력 파일명
            output_path = os.path.join(self.output_dir, output_filename)  # 최종 경로 생성
            epsilon = 1e-6  # 부동소수점 오차 보정용
            
            # 파일 읽기
            with open(tsv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if not lines:  # 파일이 비어 있는 경우
                    print("파일이 비어 있습니다.")
                    return None
                
                # 헤더 확인 및 처리
                header_line = True if lines[0].strip().startswith('start') else False
                if header_line:
                    lines = lines[1:]  # 헤더 제외
                
                speaker_segments = {}
                all_segments = []
                
                # 모든 행을 처리하여 세그먼트 정보 추출
                for line in lines:
                    parts = line.strip().split('\t')
                    if len(parts) < 4:  # start_time, end_time, speaker_id, text가 필요
                        continue
                    
                    try:
                        start_time = float(parts[0])
                        end_time = float(parts[1])
                        speaker_id = parts[2]
                        text = parts[3]
                        
                        segment = {
                            "start": start_time,
                            "end": end_time,
                            "speaker": speaker_id,
                            "text": text
                        }
                        
                        all_segments.append(segment)
                        
                        # 화자별 세그먼트 그룹화
                        if speaker_id not in speaker_segments:
                            speaker_segments[speaker_id] = []
                        speaker_segments[speaker_id].append(segment)
                        
                    except (ValueError, IndexError) as e:
                        print(f"세그먼트 파싱 오류: {line.strip()} - {str(e)}")
                        continue
                
                # 고유 화자 ID 목록
                unique_speakers = list(speaker_segments.keys())
                print(f"발견된 화자 수: {len(unique_speakers)} - {unique_speakers}")
                
                speaker_to_voice = {}
                for idx, speaker_id in enumerate(unique_speakers):
                    if idx < 5:  # 최대 5명까지 지원
                        profile_key = f"{idx:02d}"
                        if profile_key in self.voice_profiles:
                            speaker_to_voice[speaker_id] = self.voice_profiles[profile_key]
                        else:
                            speaker_to_voice[speaker_id] = self.voice_profiles["00"]  # 기본값
                    else:
                        speaker_to_voice[speaker_id] = self.voice_profiles["00"]  # 기본 음성
                
                # 최대 종료 시간 확인하여 전체 오디오 길이 결정
                max_end_time = max([segment["end"] for segment in all_segments])
                final_duration = int(max_end_time * 1000)  # 밀리초 단위 변환
                final_audio = AudioSegment.silent(duration=final_duration)
                
                # 모든 세그먼트를 시간순으로 정렬
                all_segments.sort(key=lambda x: x["start"])
                
                # 각 세그먼트 처리
                for segment in all_segments:
                    start_time = segment["start"]
                    end_time = segment["end"]
                    speaker_id = segment["speaker"]
                    text = segment["text"]
                    
                    # 세그먼트 지속 시간
                    duration = end_time - start_time
                    
                    if text and duration > 0:
                        # 화자에 해당하는 음성으로 합성 및 속도 조절
                        voice_profile = speaker_to_voice.get(speaker_id)
                        segment_audio = await self.synthesize_segment(text, duration, voice_profile)
                        
                        if segment_audio:
                            # 해당 위치에 오디오 삽입
                            start_pos = int(start_time * 1000)  # 밀리초 단위로 변환
                            final_audio = final_audio.overlay(segment_audio, position=start_pos)
                
                final_audio.export(output_path, format="wav", parameters=["-loglevel", "quiet"])
                print(f"다중 화자 TTS 처리 완료: {output_path}")
                
                return output_path
        
        except Exception as e:
            print(f"다중 화자 TTS 처리 실패: {str(e)}")
            import traceback
            print(traceback.format_exc())
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

    async def process_text(self, task_id: str, video_path: str, multi_speaker: bool = True) -> Optional[str]:
        """전체 TTS 처리 프로세스 (8단계 완료)"""
        try:
            # 입력 파일명 추출
            input_filename = os.path.basename(video_path)
            
            # 로컬 text_ko 디렉토리에서 TSV 파일 찾기
            tsv_path = await self.find_local_tsv_file(input_filename)
            if not tsv_path:
                raise Exception("로컬 TSV 파일을 찾을 수 없습니다")
            
            # TSV 파일 처리 (다중 화자 모드 선택)
            if multi_speaker:
                output_path = await self.process_multi_speaker_tsv(tsv_path, task_id)
            else:
                output_path = await self.process_tsv_segments(tsv_path, task_id)
                
            if not output_path:
                raise Exception("TSV 세그먼트 처리 실패")
            
            return output_path
            
        except Exception as e:
            print(f"TTS 처리 실패: {str(e)}")
            return None

# 서비스 인스턴스 생성
tts_service = TTSService() 