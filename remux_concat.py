import ffmpeg
import os
from pathlib import Path
from typing import Tuple, List
from google.cloud import storage
import subprocess

def select_video_from_local(video_dir: str) -> str:
    """
    로컬에서 비디오 파일을 선택하는 함수
    
    Args:
        video_dir (str): 비디오 파일이 저장된 디렉토리 경로
        
    Returns:
        str: 선택된 비디오 파일 경로
    """
    # 비디오 파일 목록 가져오기
    video_files = list(Path(video_dir).glob('*.mp4'))
    
    if not video_files:
        raise FileNotFoundError(f"No video files found in {video_dir}")
    
    print("Available video files:")
    for i, video_file in enumerate(video_files):
        print(f"{i+1}. {video_file.name}")
    
    choice = int(input("Select a video by number: ")) - 1
    return str(video_files[choice])

def download_audio_from_gcs(bucket_name: str, audio_prefix: str, video_name: str, local_path: str) -> bool:
    """
    GCS에서 오디오 파일을 다운로드하는 함수
    
    Args:
        bucket_name (str): GCS 버킷 이름
        audio_prefix (str): 오디오 파일이 저장된 디렉토리 경로
        video_name (str): 비디오 파일명 (확장자 제외)
        local_path (str): 로컬에 저장할 파일 경로
        
    Returns:
        bool: 다운로드 성공 여부
    """
    try:
        # GCS 클라이언트 초기화
        client = storage.Client()
        
        # 버킷과 Blob 선택
        bucket = client.bucket(bucket_name)
        blob_name = f"{audio_prefix}/{video_name}_denoised_transcript.wav"
        blob = bucket.blob(blob_name)
        
        # 파일 다운로드
        blob.download_to_filename(local_path)
        print(f"오디오 파일 다운로드 완료: gs://{bucket_name}/{blob_name} -> {local_path}")
        return True
    except Exception as e:
        print(f"GCS 다운로드 오류: {str(e)}")
        return False

def get_audio_file_from_video_dir(video_path: str) -> str:
    """
    비디오 파일과 같은 디렉토리에 있는 오디오 파일을 가져오는 함수
    """
    video_dir = os.path.dirname(video_path)
    video_name = Path(video_path).stem
    audio_file = os.path.join(video_dir, f"{video_name}.wav")
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"No audio file found for {video_name} in {video_dir}")
    
    return audio_file

def separate_background_music(audio_path: str, output_dir: str) -> str:
    """
    Demucs를 사용하여 배경음악(BGM)을 분리하는 함수
    """
    try:
        subprocess.run(["demucs", "--two-stems", "vocals", audio_path, "-o", output_dir], check=True)
        bgm_path = os.path.join(output_dir, "htdemucs", os.path.basename(audio_path).replace(".wav", ""), "no_vocals.wav")
        print(f"배경음악 분리 완료: {bgm_path}")
        return bgm_path
    except subprocess.CalledProcessError as e:
        print(f"Demucs 오류: {str(e)}")
        return None

def merge_audio_files(audio1_path: str, audio2_path: str, output_path: str) -> None:
    """
    두 오디오 파일을 합치는 함수
    """
    try:
        audio1 = ffmpeg.input(audio1_path)
        audio2 = ffmpeg.input(audio2_path)
        ffmpeg.filter([audio1, audio2], 'amix', inputs=2, duration='longest').output(output_path).run(overwrite_output=True, capture_stderr=True)
        print(f"오디오 합치기 완료: {output_path}")
    except ffmpeg.Error as e:
        print(f"FFmpeg 오류: {e.stderr.decode() if e.stderr else str(e)}")

def merge_video_audio(video_path: str, audio_path: str, output_path: str) -> None:
    """
    비디오와 음성 오디오를 병합하는 함수
    
    Args:
        video_path (str): 비디오 파일 경로
        audio_path (str): 음성 오디오 파일 경로
        output_path (str): 출력 파일 경로
    """
    try:
        # 입력 스트림 설정
        video = ffmpeg.input(video_path)
        audio = ffmpeg.input(audio_path)
        
        # 출력 스트림 설정 및 병합
        stream = (
            ffmpeg
            .output(
                video['v'],                # 비디오 스트림
                audio['a'],               # 오디오 스트림
                output_path,
                vcodec='copy',            # 비디오 코덱 복사 (재인코딩 없음)
                acodec='aac',             # 오디오 코덱: AAC
                map_metadata=-1,          # 메타데이터 제거
                loglevel='error'          # 에러만 출력
            )
        )
        
        # ffmpeg 실행
        ffmpeg.run(stream, overwrite_output=True, capture_stderr=True)
        print(f"병합 완료: {output_path}")
    except ffmpeg.Error as e:
        print(f"FFmpeg 오류: {e.stderr.decode() if e.stderr else str(e)}")

def main():
    """메인 실행 함수"""
    # GCS 버킷 및 디렉토리 설정
    bucket_name = "onevoice-test-bucket"
    audio_prefix = "resources/audio"
    
    # 로컬 비디오 디렉토리 설정
    video_dir = "resources/input_videos"
    
    # 출력 디렉토리 설정
    output_dir = "resources/output_videos"
    
    # 비디오 파일 선택
    try:
        video_path = select_video_from_local(video_dir)
    except FileNotFoundError as e:
        print(str(e))
        return
    
    # 비디오 파일명에서 기본 이름 추출 (확장자 제외)
    video_name = Path(video_path).stem
    
    # 비디오 파일과 같은 디렉토리에 있는 오디오 파일 가져오기
    try:
        original_audio_path = get_audio_file_from_video_dir(video_path)
    except FileNotFoundError as e:
        print(str(e))
        return
    
    # 배경음악(BGM) 분리
    bgm_path = separate_background_music(original_audio_path, output_dir)
    if not bgm_path:
        print("배경음악 분리 실패. 프로그램을 종료합니다.")
        return
    
    # 매칭되는 오디오 파일 다운로드
    generated_audio_path = f"temp_{video_name}_denoised_transcript.wav"
    if not download_audio_from_gcs(bucket_name, audio_prefix, video_name, generated_audio_path):
        print("오디오 파일 다운로드 실패. 프로그램을 종료합니다.")
        return
    
    # 배경음악(BGM)과 생성된 오디오 합치기
    merged_audio_path = f"temp_{video_name}_merged.wav"
    merge_audio_files(bgm_path, generated_audio_path, merged_audio_path)
    
    # 비디오와 합쳐진 오디오 병합
    output_filename = f"{video_name}_dubbing.mp4"
    output_path = os.path.join(output_dir, output_filename)
    try:
        merge_video_audio(video_path, merged_audio_path, output_path)
    except Exception as e:
        print(f"병합 중 오류 발생: {str(e)}")
    
    # 임시 파일 삭제
    os.remove(generated_audio_path)
    os.remove(merged_audio_path)

if __name__ == "__main__":
    main()