from google.cloud import texttospeech, storage
import os
import re
from datetime import datetime
import time
from pydub import AudioSegment
import io
import wave
from google.api_core.client_options import ClientOptions

def delete_existing_file(gcs_uri: str) -> bool:
    """
    GCS에 파일이 존재하면 삭제하는 함수
    
    Args:
        gcs_uri (str): GCS 파일 URI (예: gs://your-bucket-name/your-file.wav)
        
    Returns:
        bool: 파일 삭제 성공 여부
    """
    try:
        # GCS 클라이언트 초기화
        client = storage.Client()
        
        # GCS URI에서 버킷 이름과 파일 이름 추출
        bucket_name = gcs_uri.split('/')[2]
        blob_name = '/'.join(gcs_uri.split('/')[3:])
        
        # 버킷과 Blob 선택
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # 파일이 존재하면 삭제
        if blob.exists():
            blob.delete()
            print(f"기존 파일 삭제 완료: {gcs_uri}")
            return True
        else:
            print(f"기존 파일 없음: {gcs_uri}")
            return False
    except Exception as e:
        print(f"파일 삭제 실패: {str(e)}")
        return False

def select_file_from_gcs(bucket_name: str, prefix: str) -> str:
    """
    GCS에서 파일을 선택하는 함수
    
    Args:
        bucket_name (str): GCS 버킷 이름
        prefix (str): 파일을 선택할 디렉토리 경로
        
    Returns:
        str: 선택된 파일의 GCS URI
    """    
    # GCS 클라이언트 초기화
    client = storage.Client()

    # 버킷과 Blob 선택
    bucket = client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=prefix))
    
    # 폴더 제외하고 파일만 필터링
    files = [blob for blob in blobs if not blob.name.endswith('/')]
    
    if not files:
        raise FileNotFoundError(f"No files found in gs://{bucket_name}/{prefix}")
    
    print("Available files:")
    for i, file in enumerate(files):
        # 파일명만 추출하여 출력
        file_name = os.path.basename(file.name)
        print(f"{i+1}. {file_name}")
    
    choice = int(input("Select a file by number: ")) - 1
    return f"gs://{bucket_name}/{files[choice].name}"

def download_from_gcs(gcs_uri: str, local_path: str) -> bool:
    """
    GCS에서 로컬로 파일을 다운로드하는 함수
    
    Args:
        gcs_uri (str): GCS 파일 URI (예: gs://your-bucket-name/your-text-file.txt)
        local_path (str): 로컬 파일 경로
        
    Returns:
        bool: 다운로드 성공 여부
    """
    try:
        # GCS 클라이언트 초기화
        client = storage.Client()

        # GCS URI에서 버킷 이름과 파일 이름 추출
        bucket_name = gcs_uri.split('/')[2]
        blob_name = '/'.join(gcs_uri.split('/')[3:])
        
        # 버킷과 Blob 선택
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # 파일 다운로드
        blob.download_to_filename(local_path)
        print(f"파일 다운로드 완료: {gcs_uri} -> {local_path}")
        return True
    except Exception as e:
        print(f"GCS 다운로드 오류: {str(e)}")
        return False

def generate_silence(duration_sec: float) -> AudioSegment:
    """무음 세그먼트 생성"""
    return AudioSegment.silent(duration=int(duration_sec * 1000))  # 밀리초 단위 변환

def synthesize_segment(text: str, client: texttospeech.TextToSpeechClient, 
                       voice: texttospeech.VoiceSelectionParams, 
                       audio_config: texttospeech.AudioConfig) -> AudioSegment:
    """개별 세그먼트 음성 합성"""
    synthesis_input = texttospeech.SynthesisInput(text=text)
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    return AudioSegment.from_wav(io.BytesIO(response.audio_content))

def remove_timestamps(text: str) -> str:
    """
    TSV 파일에서 타임스탬프를 제거하고 텍스트만 추출
    """
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        parts = line.split('\t')
        if len(parts) >= 3:  # 타임스탬프와 텍스트가 있는 경우
            cleaned_lines.append(parts[2])  # 텍스트 부분만 추가
    return '\n'.join(cleaned_lines)

def calculate_speaking_rate(
    text: str, 
    target_duration: float, 
    client: texttospeech.TextToSpeechClient, 
    voice: texttospeech.VoiceSelectionParams
) -> float:
    """
    TTS 속도를 계산하여 타겟 지속 시간에 맞춤
    """
    # 기본 속도(1.0)로 TTS 생성
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        speaking_rate=1.0  # 기본 속도
    )
    synthesis_input = texttospeech.SynthesisInput(text=text)
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    segment = AudioSegment.from_wav(io.BytesIO(response.audio_content))
    
    # 현재 지속 시간과 타겟 지속 시간 비교
    current_duration = len(segment) / 1000  # 밀리초 -> 초
    if current_duration > target_duration:
        # 타임스탬프 시간보다 길다면 속도를 빠르게 조절
        speaking_rate = current_duration / target_duration
    else:
        # 타임스탬프 시간보다 짧다면 속도는 1.0으로 유지
        speaking_rate = 1.0
    return speaking_rate

def process_tsv_segments(
    tsv_path: str, 
    output_path: str, 
    client: texttospeech.TextToSpeechClient, 
    voice: texttospeech.VoiceSelectionParams
) -> None:
    """TSV 파일을 세그먼트 단위로 처리"""
    final_audio = AudioSegment.empty()
    epsilon = 1e-6  # 부동소수점 오차 보정용
    
    with open(tsv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if not lines:  # 파일이 비어 있는 경우
            print("파일이 비어 있습니다.")
            return
        
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
            start, end, text = parts
            try:
                start = float(start)
                end = float(end)
            except ValueError:
                print(f"잘못된 타임스탬프 형식: {line.strip()}")
                continue
            
            # 이전 세그먼트와 현재 세그먼트 사이의 빈 시간 처리 (부동소수점 오차 보정)
            time_gap = start - previous_end_time
            if time_gap > epsilon:  # 0보다 큰 경우에만 처리
                silence_duration = time_gap
                silence = generate_silence(silence_duration)
                final_audio += silence
            
            # 현재 세그먼트 처리
            duration = end - start
            if text.strip():  # 텍스트가 있는 경우
                # 속도 조절 계산
                speaking_rate = calculate_speaking_rate(text, duration, client, voice)
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                    speaking_rate=speaking_rate
                )
                segment = synthesize_segment(text, client, voice, audio_config)
                
                # 타임스탬프 시간보다 짧다면 무음 추가 (부동소수점 오차 보정)
                segment_duration = len(segment) / 1000  # 밀리초 -> 초
                if segment_duration < duration - epsilon:
                    silence = AudioSegment.silent(duration=int((duration - segment_duration) * 1000))
                    segment += silence
            else:  # 텍스트 없는 경우 무음
                segment = generate_silence(duration)
            
            final_audio += segment
            previous_end_time = end  # 이전 세그먼트의 종료 시간 업데이트
            
            # 5초마다 진행률 체크
            current_time = time.time()
            if current_time - last_check_time >= 5:
                progress = (i / total_lines) * 100
                print(f"진행률: {progress:.2f}% ({i}/{total_lines})")
                last_check_time = current_time
    
    # 최종 오디오 저장
    final_audio.export(output_path, format="wav")
    print(f"생성 완료: {output_path}")

def upload_to_gcs(local_path: str, gcs_uri: str) -> bool:
    """
    로컬 파일을 GCS에 업로드하는 함수
    """
    try:
        client = storage.Client()
        bucket_name = gcs_uri.split('/')[2]
        blob_name = '/'.join(gcs_uri.split('/')[3:])
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_path)
        print(f"파일 업로드 완료: {local_path} -> {gcs_uri}")
        return True
    except Exception as e:
        print(f"파일 업로드 실패: {str(e)}")
        return False

def main():
    """메인 실행 함수"""
    # TTS 클라이언트 및 음성 설정 초기화
    client = texttospeech.TextToSpeechClient()
    voice = texttospeech.VoiceSelectionParams(
        language_code='ko-KR',
        name='ko-KR-Neural2-C'
    )
    
    # GCS 버킷 및 디렉토리 설정
    bucket_name = "onevoice-test-bucket"
    prefix = "resources/text_ko"
    
    # 파일 선택
    gcs_uri = select_file_from_gcs(bucket_name, prefix)
    
    # 로컬 파일 경로 설정
    local_path = "temp.tsv"
    
    # GCS에서 파일 다운로드
    if not download_from_gcs(gcs_uri, local_path):
        print("파일 다운로드 실패. 프로그램을 종료합니다.")
        return
    
    # 결과 오디오 파일 저장 위치 설정
    filename = os.path.basename(gcs_uri).replace('.tsv', '.wav')
    output_local_path = os.path.join("resources", "audio", filename)  # resources/audio 디렉토리에 저장
    output_gcs_uri = f"gs://{bucket_name}/resources/audio/{filename}"
    
    # TSV 파일 처리
    process_tsv_segments(local_path, output_local_path, client, voice)
    
    # GCS 업로드
    upload_to_gcs(output_local_path, output_gcs_uri)
    
    # 임시 파일 삭제
    os.remove(local_path)

if __name__ == "__main__":
    main()
