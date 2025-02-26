from google.cloud import translate_v2 as translate
import os
from pathlib import Path
from datetime import datetime  # datetime 모듈 임포트
import subprocess
import re
from textblob import TextBlob
import spacy

# SpaCy 영어 모델 로드
nlp = spacy.load("en_core_web_sm")

def upload_to_gcs(local_path: str, gcs_path: str) -> bool:
    """
    로컬 파일을 GCS 버킷에 업로드하는 함수
    
    Args:
        local_path (str): 로컬 파일 경로
        gcs_path (str): GCS 버킷 경로
        
    Returns:
        bool: 업로드 성공 여부
    """
    try:
        subprocess.run(["gcloud", "storage", "cp", local_path, gcs_path], check=True)
        print(f"파일 업로드 완료: {local_path} -> {gcs_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"GCS 업로드 오류: {str(e)}")
        return False

def simplify_sentence(text: str) -> str:
    """반복적 표현 생략 및 문장 구조 간소화"""
    # 불필요한 접속사/부사 제거
    text = re.sub(r'(그리고|또한|그러나|그런데|그래서|그럼에도)[,]?\s*', '', text)
    
    # 불필요한 관형어 축약
    text = re.sub(r'매우\s+', '', text)
    text = re.sub(r'아주\s+', '', text)
    
    # 반복적인 표현 제거
    text = re.sub(r'(\w+)\s+\1', r'\1', text)  # 예: "좋아 좋아" → "좋아"
    
    # 불필요한 문장 부호 정리
    text = re.sub(r'[.,]{2,}', '.', text)  # 연속된 마침표/쉼표 제거
    text = re.sub(r'\s+([.,!?])', r'\1', text)  # 부호 앞 공백 제거
    
    # 불필요한 공백 제거
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# def correct_spelling(text: str) -> str:
#     """
#     TextBlob을 사용하여 철자 교정
#     """
#     blob = TextBlob(text)
#     corrected_text = str(blob.correct())
#     return corrected_text

def is_punctuation_appropriate(token):
    """
    구두점이 적절한 위치에 있는지 판단
    """
    # 문장 끝에 마침표가 없는 경우
    if token.text == '.' and token.i == len(token.sent) - 1:
        return True
    # 문장 중간에 마침표가 있는 경우 (예: 약어 제외)
    if token.text == '.' and token.i != len(token.sent) - 1:
        return False
    # 중복된 구두점 (예: "..", "!!")
    if token.text in ['.', '!', '?']:
        # 마지막 토큰인지 확인
        if token.i == len(token.doc) - 1:
            return True
        # 다음 토큰이 같은 구두점인지 확인
        if token.nbor(1).text in ['.', '!', '?']:
            return False
    # 그 외의 경우는 적절하다고 판단
    return True

def correct_punctuation(text: str) -> str:
    """
    구두점의 적절성을 판단하고, 적절하지 않다면 제거 또는 수정
    """
    doc = nlp(text)
    corrected_text = []
    
    for sent in doc.sents:
        for token in sent:
            # 구두점인 경우
            if token.is_punct:
                if is_punctuation_appropriate(token):
                    corrected_text.append(token.text)
                else:
                    continue  # 적절하지 않은 구두점 제거
            else:
                corrected_text.append(token.text_with_ws)
    
    return "".join(corrected_text).strip()

def split_long_sentences(text: str, max_length: int = 40) -> str:
    """
    긴 문장을 짧은 문장으로 분리하는 함수
    
    Args:
        text (str): 입력 텍스트
        max_length (int): 문장의 최대 길이 (기본값: 40)
        
    Returns:
        str: 분리된 텍스트
    """
    doc = nlp(text)
    sentences = [sent.text for sent in doc.sents]
    result = []
    
    for sent in sentences:
        if len(sent) > max_length:
            # 문장을 의미 단위로 분리
            sub_sentences = [sub_sent.text for sub_sent in nlp(sent).sents]
            result.extend(sub_sentences)
        else:
            result.append(sent)
    
    return " ".join(result)

def preprocess_text(text: str) -> str:
    """
    번역 전 텍스트 전처리 (문장 분리 + 소문자 변환 + 철자 교정 + 구두점 보정)
    """
    # 문장 분리
    text = split_long_sentences(text)
    # 소문자 변환
    # text = text.lower()
    # 철자 교정
    # text = correct_spelling(text)
    # 구두점 보정
    text = correct_punctuation(text)
    return text

def translate_text(text: str) -> str:
    """개선된 번역 함수"""
    # 번역 전 텍스트 전처리
    text = preprocess_text(text)
    
    client = translate.Client()
    result = client.translate(
        text,
        source_language='en',
        target_language='ko',
        model='nmt',
        format_='text'
    )
    
    translated = result['translatedText']
    
    # 번역 후처리 파이프라인
    translated = simplify_sentence(translated)
    # translated = replace_synonyms(translated)
    
    return translated

def process_transcript(input_path: str) -> None:
    """
    타임스탬프가 포함된 트랜스크립트 파일을 읽어서 번역하고 TSV 형식으로 저장하는 함수
    
    Args:
        input_path (str): 입력 파일 경로
    """
    start_time = datetime.now()  # 시작 시간 기록
    
    # 입력 파일 읽기
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    translated_lines = []
    total_lines = len(lines)
    
    # 각 줄을 처리
    for i, line in enumerate(lines):
        # 타임스탬프와 텍스트 분리
        if '[' in line and ']' in line:
            timestamp, text = line.split(']', 1)
            timestamp += ']'  # ']' 포함
            text = text.strip()  # 텍스트 앞뒤 공백 제거
            
            # 번역
            translated_text = translate_text(text)
            
            # 타임스탬프에서 시작 시간과 종료 시간 추출
            time_range = timestamp.strip('[]').split('s - ')
            start_time_str = time_range[0]
            end_time_str = time_range[1].replace('s', '')
            
            # TSV 형식으로 데이터 저장 (시작 시간, 종료 시간, 번역된 텍스트)
            translated_lines.append(f"{start_time_str}\t{end_time_str}\t{translated_text}\n")
        
        # 10줄 단위로 진행률 출력
        if (i + 1) % 10 == 0 or (i + 1) == total_lines:
            progress = (i + 1) / total_lines * 100
            print(f"진행률: {progress:.2f}% ({i + 1}/{total_lines} 줄 완료)")
    
    # 출력 디렉토리 설정 및 생성
    output_dir = "resources/text_ko"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 출력 파일 경로 설정 (확장자를 .tsv로 변경)
    filename = os.path.basename(input_path)
    base_name = os.path.splitext(filename)[0]  # 확장자 제거
    output_path = os.path.join(output_dir, f"{base_name}.tsv")
    
    # TSV 파일 헤더 추가 및 번역된 텍스트 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("start_time\tend_time\ttranslated_text\n")  # 헤더 수정
        f.writelines(translated_lines)
    
    # 전체 소요 시간 계산
    elapsed_time = datetime.now() - start_time
    print(f"번역 완료: {output_path}")
    print(f"전체 소요 시간: {elapsed_time.total_seconds():.2f}초")
    
    # GCS에 업로드
    gcs_bucket = "gs://onevoice-test-bucket/resources/text_ko"
    upload_to_gcs(output_path, gcs_bucket)

def select_transcript_from_directory(directory: str) -> str:
    """text_en 디렉토리에서 번역할 스크립트 파일을 선택합니다."""
    files = [f for f in os.listdir(directory) if f.endswith('.txt')]
    if not files:
        raise FileNotFoundError(f"No transcript files found in {directory}")
    
    print("Available transcript files:")
    for i, file in enumerate(files):
        print(f"{i+1}. {file}")
    
    choice = int(input("Select a file by number: ")) - 1
    return os.path.join(directory, files[choice])

def main():
    """메인 실행 함수"""
    text_en_dir = "resources/text_en"
    input_path = select_transcript_from_directory(text_en_dir)
    process_transcript(input_path)

if __name__ == "__main__":
    main()





# # 동의어 치환 매핑 테이블
# SYNONYM_MAP = {
#     r'\b경험치\b': 'XP',
#     r'\b레벨 업\b': '레벨업',
#     r'\b사용자 인터페이스\b': 'UI',
#     r'\b경제적 자원\b': '자금',
#     r'\b최적화된\b': '간소화된'
# }

# def replace_synonyms(text: str) -> str:
#     """동의어 치환"""
#     for pattern, replacement in SYNONYM_MAP.items():
#         text = re.sub(pattern, replacement, text)
#     return text