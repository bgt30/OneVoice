import os
import requests
import json
import time
import subprocess
from pathlib import Path

# PyAnnote.ai API 키 설정
API_KEY = os.getenv("PYANNOTE_API_KEY")
API_URL = "https://api.pyannote.ai/v1"

def download_youtube_video(youtube_url, output_dir="temp"):
    """유튜브 영상을 다운로드하고 16kHz 모노 오디오 파일(.mp3)로 저장 (yt-dlp 사용)"""
    try:
        # 출력 디렉토리 생성
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # 영상 정보 가져오기(제목만)
        info_cmd = [
            "yt-dlp",
            "--skip-download",
            "--print", "title",
            youtube_url
        ]
        info_process = subprocess.run(info_cmd, capture_output=True, text=True)
        video_title = info_process.stdout.strip()
        
        # 영상 제목에서 첫 10글자만 추출하고 특수문자/공백을 '_'로 변경
        if video_title:
            import re
            # 첫 10글자 추출 (또는 더 짧은 경우 전체)
            short_title = video_title[:10]
            # 특수문자와 공백을 '_'로 대체
            safe_title = re.sub(r'[^a-zA-Z0-9가-힣]', '_', short_title)
            # 연속된 '_'를 하나로 줄임
            safe_title = re.sub(r'_+', '_', safe_title)
            # 앞뒤 '_' 제거
            safe_title = safe_title.strip('_')
            
            print(f"원래 제목: {video_title}")
            print(f"변환된 파일명: {safe_title}")
        else:
            # 제목을 가져오지 못한 경우 기본값 사용
            safe_title = f"video_{int(time.time())}"
            print(f"제목을 가져올 수 없어 기본값 사용: {safe_title}")
        
        # 임시 출력 파일 형식 설정 (변환된 제목 사용)
        temp_output_template = os.path.join(output_dir, f"temp_{safe_title}.%(ext)s")
        
        # yt-dlp 명령어 구성
        cmd = [
            "yt-dlp",
            "-x",                       # 오디오 추출
            "--audio-format", "mp3",    # mp3 형식으로 변환
            "--audio-quality", "0",     # 최고 품질
            "-o", temp_output_template, # 출력 경로 템플릿
            youtube_url                 # 유튜브 URL
        ]
        
        print(f"유튜브 영상 다운로드 중: {youtube_url}")
        
        # 명령어 실행
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode != 0:
            print(f"다운로드 오류: {process.stderr}")
            return None
        
        # 출력에서 임시 파일 경로 찾기
        output_lines = process.stdout.split('\n')
        temp_file_path = None
        
        for line in output_lines:
            if "[ExtractAudio] Destination:" in line:
                temp_file_path = line.split("Destination: ")[1].strip()
            elif "Destination:" in line and line.endswith(".mp3"):
                temp_file_path = line.split("Destination: ")[1].strip()
            elif "[download] " in line and " has already been downloaded" in line:
                file_name = line.split("[download] ")[1].split(" has already")[0]
                temp_file_path = os.path.join(output_dir, file_name)
            elif "Merging formats into" in line:
                temp_file_path = line.split("Merging formats into \"")[1].split("\"")[0]
        
        # 파일 경로를 찾지 못한 경우 디렉토리에서 가장 최근 파일 선택
        if not temp_file_path:
            files = list(Path(output_dir).glob(f"temp_{safe_title}.mp3"))
            if not files:
                files = list(Path(output_dir).glob("temp_*.mp3"))
            if files:
                files.sort(key=os.path.getmtime, reverse=True)
                temp_file_path = str(files[0])
        
        if not temp_file_path or not os.path.exists(temp_file_path):
            print("다운로드된 파일을 찾을 수 없습니다.")
            return None
        
        # 최종 파일 경로 (16kHz_mono_ 접두사 추가)
        final_file_path = os.path.join(output_dir, f"16kHz_mono_{safe_title}.mp3")
        
        # FFmpeg를 사용하여 16kHz 모노로 변환
        print(f"오디오를 16kHz 모노로 변환 중...")
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", temp_file_path,       # 입력 파일
            "-ac", "1",                 # 모노 채널 (1)
            "-ar", "16000",             # 샘플링 레이트 16kHz
            "-y",                       # 기존 파일 덮어쓰기
            final_file_path             # 출력 파일 (변환 후에도 mp3 유지)
        ]
        
        # FFmpeg 명령 실행
        ffmpeg_process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        if ffmpeg_process.returncode != 0:
            print(f"오디오 변환 오류: {ffmpeg_process.stderr}")
            return temp_file_path  # 변환 실패 시 원본 파일 반환
            
        # 임시 파일 삭제
        try:
            os.remove(temp_file_path)
        except Exception as e:
            print(f"임시 파일 삭제 실패: {e}")
        
        print(f"다운로드 및 변환 완료: {final_file_path}")
        return final_file_path
    
    except Exception as e:
        print(f"유튜브 다운로드 오류: {e}")
        import traceback
        print(f"상세 오류 정보:\n{traceback.format_exc()}")
        return None

def upload_file_to_pyannote(file_path):
    """오디오 파일을 PyAnnote.ai에 업로드 (공식 API 문서 기반)"""
    try:
        # 1. 파일 이름 가져오기 및 길이 제한
        file_name = os.path.basename(file_path)
        if len(file_name) > 100:
            base, ext = os.path.splitext(file_name)
            file_name = f"{base[:90]}{ext}"  # 확장자 포함 100자 이내로 줄임
            
        # 2. media:// 고유식별자 URL 생성 (타임스탬프 + 파일명)
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
        
        # 3. 임시 저장소 생성 요청 (pre-signed URL 얻기)
        create_url = f"{API_URL}/media/input"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        body = {
            "url": media_url
        }
        
        print(f"임시 저장소 위치 생성 중...")
        print(f"요청 본문: {json.dumps(body, ensure_ascii=False)}")
        
        response = requests.post(create_url, json=body, headers=headers)
        
        print(f"응답 코드: {response.status_code}")
        print(f"응답 내용: {response.text}")
        
        if response.status_code not in [200, 201]:
            print(f"임시 저장소 생성 실패: {response.status_code} - {response.text}")
            return None
        
        # 4. 응답에서 pre-signed URL 가져오기
        response_data = response.json()
        presigned_url = response_data.get("url")
        
        if not presigned_url:
            print(f"pre-signed URL을 찾을 수 없음: {response_data}")
            return None
            
        print(f"pre-signed URL 생성됨: {presigned_url}")
        
        # 5. pre-signed URL에 파일 업로드
        # Content-Type 설정
        content_type = "audio/mpeg" if file_path.lower().endswith('.mp3') else "audio/wav"
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
            
        print(f"파일 업로드 중: {file_path} -> {presigned_url}")
        
        # PUT 요청으로 파일 업로드
        upload_headers = {"Content-Type": content_type}
        upload_response = requests.put(presigned_url, headers=upload_headers, data=file_data)
        
        if upload_response.status_code not in [200, 201]:
            print(f"파일 업로드 실패: {upload_response.status_code} - {upload_response.text}")
            return None
            
        print(f"파일 업로드 성공")
        
        # 6. 원래 media:// URL 반환 (create_diarization_job에서 사용)
        return media_url
        
    except Exception as e:
        print(f"파일 업로드 오류: {e}")
        import traceback
        print(f"상세 오류 정보:\n{traceback.format_exc()}")
        return None

def create_diarization_job(media_url, numSpeakers=None):
    """화자 분리 작업 생성 (공식 API 문서 기반)"""
    try:
        # 작업 생성 요청 URL
        job_url = f"{API_URL}/diarize"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 기본 요청 본문
        body = {
            "url": media_url
        }
        
        # 화자 수가 지정된 경우 설정 추가
        if numSpeakers:
            body["numSpeakers"] = numSpeakers
            body["confidence"] = False
        
        # 요청 데이터 출력
        print(f"요청 데이터: {json.dumps(body, indent=2, ensure_ascii=False)}")
                    
        response = requests.post(job_url, headers=headers, json=body)
        
        print(f"응답 코드: {response.status_code}")
        print(f"응답 내용: {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            job_id = result.get("jobId")
            print(f"화자 분리 작업 생성 성공: Job ID = {job_id}")
            return job_id
        else:
            print(f"화자 분리 작업 생성 실패: {response.status_code} - {response.text}")
            # 상세 에러 메시지 제공
            try:
                error_json = response.json()
                print(f"에러 상세: {json.dumps(error_json, indent=2, ensure_ascii=False)}")
            except:
                pass
            return None
    
    except Exception as e:
        print(f"화자 분리 작업 생성 오류: {e}")
        return None

def get_job_status(job_id):
    """작업 상태 확인"""
    try:
        status_url = f"{API_URL}/jobs/{job_id}"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        
        response = requests.get(status_url, headers=headers)
        
        print(f"상태 응답 코드: {response.status_code}")
        print(f"상태 응답 내용: {response.text[:500]}")  # 응답 내용의 일부만 출력
        
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

def get_diarization_result(job_id):
    """화자 분리 결과 가져오기"""
    try:
        result_url = f"{API_URL}/jobs/{job_id}"
        headers = {"Authorization": f"Bearer {API_KEY}"}
        
        response = requests.get(result_url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            print("Diarization 결과를 성공적으로 가져왔습니다.")
            return result
        else:
            print(f"Diarization 결과 가져오기 실패: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        print(f"Diarization 결과 가져오기 오류: {e}")
        return None

def save_diarization_result(result, output_file="diarization_result.json"):
    """화자 분리 결과를 파일로 저장"""
    try:
        print(f"결과 키 목록: {list(result.keys())}")
        
        # JSON 형식으로 저장
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # CSV 형식으로 저장
        if "diarization" in result:
            print(f"세그먼트 수: {len(result['diarization'])}")
            print(f"첫 번째 세그먼트 예시: {result['diarization'][0]}")
            
            csv_file = output_file.replace(".json", ".csv")
            with open(csv_file, "w", encoding="utf-8") as f:
                # CSV 헤더 작성
                f.write("start_time,end_time,speaker\n")
                
                for segment in result["diarization"]:
                    start = segment.get("start", 0)
                    end = segment.get("end", 0)
                    speaker = segment.get("speaker", "SPEAKER_UNK")
                    
                    # CSV 형식으로 데이터 작성
                    f.write(f"{start:.3f},{end:.3f},{speaker}\n")
            
            print(f"CSV 형식 결과가 {csv_file}에 저장되었습니다.")
        else:
            print("\n경고: 결과에 'diarization' 키가 없습니다.")
    
    except Exception as e:
        print(f"결과 저장 오류: {e}")
        import traceback
        print(f"상세 오류 정보:\n{traceback.format_exc()}")

def process_youtube_video(youtube_url):
    """유튜브 영상을 다운로드하고 화자 분리 수행"""
    try:
        print("\n====== 1. 유튜브 영상 다운로드 시작 ======")
        audio_file = download_youtube_video(youtube_url)
        if not audio_file:
            print("오류: 유튜브 영상 다운로드에 실패했습니다.")
            return False
        print(f"다운로드 완료: {audio_file}")
        
        print("\n====== 2. PyAnnote.ai에 파일 업로드 시작 ======")
        media_url = upload_file_to_pyannote(audio_file)
        if not media_url:
            print("오류: 파일 업로드에 실패했습니다.")
            return False
        print(f"미디어 URL: {media_url}")
        
        print("\n====== 3. 화자 분리 작업 생성 시작 ======")
        job_id = create_diarization_job(media_url, numSpeakers=None)  # 화자 수를 2명으로 설정
        if not job_id:
            print("오류: 화자 분리 작업 생성에 실패했습니다.")
            return False
        print(f"작업 생성 완료: Job ID = {job_id}")
        
        print("\n====== 4. 작업 완료 대기 중 ======")
        max_attempts = 60  # 최대 60번 시도 (약 10분)
        attempt = 0
        while attempt < max_attempts:
            status_result = get_job_status(job_id)
            if not status_result:
                print("작업 상태 확인 실패")
                return False
                
            status = status_result.get("status")
            print(f"현재 작업 상태: {status}")
            
            if status == "succeeded":  # API 응답 상태가 succeeded로 변경됨
                break
            elif status in ["failed", "error"]:
                print("작업 처리 중 오류가 발생했습니다.")
                return False
            
            attempt += 1
            print(f"작업 완료 대기 중... ({attempt}/{max_attempts})")
            time.sleep(10)  # 10초 대기
        
        if attempt >= max_attempts:
            print("작업 시간 초과")
            return False
        
        print("\n====== 5. 결과 가져오기 시작 ======")
        result = get_diarization_result(job_id)
        if not result:
            print("오류: 화자 분리 결과를 가져오는데 실패했습니다.")
            return False
            
        # 결과에 output이 있는지 확인
        if "output" in result:
            result = result["output"]  # output 내부의 결과를 사용
        
        print("결과 가져오기 완료")
        
        print("\n====== 6. 결과 저장 시작 ======")
        output_file = f"diarization_{os.path.basename(audio_file).split('.')[0]}.json"
        save_diarization_result(result, output_file)
        print(f"결과 저장 완료: {output_file}")
        
        print("\n====== 화자 분리 과정이 성공적으로 완료되었습니다 ======")
        return True
    
    except Exception as e:
        print(f"\n====== 처리 중 오류 발생 ======")
        print(f"오류 메시지: {e}")
        import traceback
        print(f"상세 오류 정보:\n{traceback.format_exc()}")
        return False

# 사용 예제
if __name__ == "__main__":
    # 유튜브 URL 입력
    youtube_url = input("화자 분리할 유튜브 URL을 입력하세요: ")
    
    # 처리 시작
    process_youtube_video(youtube_url)