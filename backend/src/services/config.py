import os
from google.cloud import speech, translate_v2 as translate, texttospeech
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Google Cloud 클라이언트 초기화
speech_client = speech.SpeechClient()
translate_client = translate.Client()
tts_client = texttospeech.TextToSpeechClient()

# 프로젝트 설정
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION')

# 임시 파일 저장 경로
TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'temp')
os.makedirs(TEMP_DIR, exist_ok=True)

# 지원하는 언어 설정
SOURCE_LANGUAGE = 'en-US'
TARGET_LANGUAGE = 'ko-KR'

# 음성 설정
VOICE_CONFIG = texttospeech.VoiceSelectionParams(
    language_code=TARGET_LANGUAGE,
    name='ko-KR-Standard-A',
    ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
)

# 오디오 설정
AUDIO_CONFIG = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=1.0,
    pitch=0.0
) 