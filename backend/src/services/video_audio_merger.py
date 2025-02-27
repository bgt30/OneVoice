import ffmpeg
import os
from pathlib import Path
from typing import Optional
from google.cloud import storage
import subprocess
from . import config

class VideoAudioMerger:
    def __init__(self):
        self.output_dir = os.path.join(config.TEMP_DIR, "output_videos")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.storage_client = storage.Client()
        self.bucket_name = "onevoice-test-bucket"

    async def separate_background_music(self, audio_path: str) -> Optional[str]:
        """Demucs를 사용하여 배경음악(BGM) 분리"""
        try:
            temp_output_dir = os.path.join(self.output_dir, "temp_demucs")
            Path(temp_output_dir).mkdir(parents=True, exist_ok=True)
            
            subprocess.run(["demucs", "--two-stems", "vocals", audio_path, "-o", temp_output_dir], 
                         check=True, capture_output=True)
            
            # 분리된 오디오 디렉토리 경로
            base_dir = os.path.join(temp_output_dir, "htdemucs", 
                                   os.path.basename(audio_path).replace(".wav", ""))
            
            print(f"분리된 오디오 디렉토리: {base_dir}")
            
            # 디렉토리 내용 확인
            if os.path.exists(base_dir):
                print(f"디렉토리 내용: {os.listdir(base_dir)}")
                
                # no_vocals.wav 파일 찾기 (Demucs의 실제 출력)
                no_vocals_path = os.path.join(base_dir, "no_vocals.wav")
                if os.path.exists(no_vocals_path):
                    print(f"배경음악 파일 찾음 (no_vocals.wav): {no_vocals_path}")
                    return no_vocals_path
            
            raise FileNotFoundError("배경음악 파일(no_vocals.wav)을 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"배경음악 분리 실패: {str(e)}")
            return None

    async def merge_audio_files(self, audio1_path: str, audio2_path: str, volume_factor: float = 0.5) -> Optional[str]:
        """두 오디오 파일을 합성 (볼륨 조절 가능)"""
        try:
            # 원본 오디오 파일 이름에 '_merged' 접미사 추가
            audio_basename = os.path.basename(audio2_path)
            audio_name = os.path.splitext(audio_basename)[0]
            audio_ext = os.path.splitext(audio_basename)[1]
            output_path = os.path.join(self.output_dir, f"{audio_name}_merged{audio_ext}")
            
            # 배경음악 볼륨 조절
            audio1 = ffmpeg.input(audio1_path).filter('volume', volume_factor)
            audio2 = ffmpeg.input(audio2_path)
            
            ffmpeg.filter([audio1, audio2], 'amix', inputs=2, duration='longest')\
                  .output(output_path)\
                  .run(overwrite_output=True, capture_stderr=True)
            
            print(f"오디오 합성 완료: {output_path}")
            return output_path
            
        except ffmpeg.Error as e:
            print(f"오디오 합성 실패: {e.stderr.decode() if e.stderr else str(e)}")
            return None

    async def merge_video_audio(self, video_path: str, audio_path: str) -> Optional[str]:
        """비디오와 오디오 합성"""
        try:
            output_path = os.path.join(self.output_dir, f"dubbed_{os.path.basename(video_path)}")
            
            video = ffmpeg.input(video_path)
            audio = ffmpeg.input(audio_path)
            
            stream = (
                ffmpeg
                .output(
                    video['v'],
                    audio['a'],
                    output_path,
                    vcodec='copy',
                    acodec='aac',
                    map_metadata=-1,
                    loglevel='error'
                )
            )
            
            ffmpeg.run(stream, overwrite_output=True, capture_stderr=True)
            print(f"비디오 합성 완료: {output_path}")
            
            # GCS에 결과물 업로드
            destination_blob_name = f"resources/output_videos/{os.path.basename(output_path)}"
            if await self._upload_to_gcs(output_path, destination_blob_name):
                print(f"결과물 업로드 완료: gs://{self.bucket_name}/{destination_blob_name}")
            
            return output_path
            
        except ffmpeg.Error as e:
            print(f"비디오 합성 실패: {e.stderr.decode() if e.stderr else str(e)}")
            return None

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

    async def process_video(self, task_id: str, video_path: str, tts_audio_path: str, original_audio_path: str = None) -> Optional[str]:
        """전체 비디오 처리 프로세스"""
        try:
            # 원본 오디오 경로 확인
            if not original_audio_path or not os.path.exists(original_audio_path):
                # 원본 오디오 파일이 없는 경우에만 추출
                print("원본 오디오 파일이 제공되지 않아 직접 추출합니다.")
                original_audio_path = os.path.join(self.output_dir, f"{Path(video_path).stem}.wav")
                stream = ffmpeg.input(video_path)
                stream = ffmpeg.output(stream, original_audio_path,
                                     acodec='pcm_s16le',
                                     ac=2,
                                     ar='44.1k')
                ffmpeg.run(stream, overwrite_output=True)
            else:
                print(f"제공된 원본 오디오 파일을 사용합니다: {original_audio_path}")

            # 배경음악 분리
            bgm_path = await self.separate_background_music(original_audio_path)
            if not bgm_path:
                raise Exception("배경음악 분리 실패")

            # 배경음악과 TTS 오디오 합성 (배경음악 볼륨 50%로 설정)
            merged_audio_path = await self.merge_audio_files(bgm_path, tts_audio_path, volume_factor=0.5)
            if not merged_audio_path:
                raise Exception("오디오 합성 실패")

            # 비디오와 합성된 오디오 병합
            output_path = await self.merge_video_audio(video_path, merged_audio_path)
            if not output_path:
                raise Exception("비디오 합성 실패")

            return output_path

        except Exception as e:
            print(f"비디오 처리 실패: {str(e)}")
            return None

# 서비스 인스턴스 생성
video_audio_merger = VideoAudioMerger() 