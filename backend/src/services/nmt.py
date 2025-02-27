from google.cloud import translate_v2 as translate
from google.cloud import storage
import os
from pathlib import Path
import subprocess
import re
from typing import Optional
import spacy
import pandas as pd
from . import config

class NMTService:
    def __init__(self):
        self.client = config.translate_client
        self.storage_client = storage.Client()
        self.bucket_name = "onevoice-test-bucket"
        self.output_dir = os.path.join(config.TEMP_DIR, "text_ko")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        # SpaCy 영어 모델 로드
        self.nlp = spacy.load("en_core_web_sm")

    async def _upload_to_gcs(self, local_path: str, gcs_path: str) -> bool:
        """GCS에 파일 업로드"""
        try:
            # GCS 경로 파싱 (gs://bucket-name/path/to/file)
            gcs_parts = gcs_path.replace("gs://", "").split("/", 1)
            bucket_name = gcs_parts[0]
            blob_name = gcs_parts[1] if len(gcs_parts) > 1 else os.path.basename(local_path)
            
            # 스토리지 클라이언트 사용
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # 파일 업로드
            print(f"파일 업로드 시작: {local_path} -> {gcs_path}")
            blob.upload_from_filename(local_path)
            print(f"파일 업로드 완료: {local_path} -> {gcs_path}")
            
            return True
        except Exception as e:
            print(f"GCS 업로드 오류: {str(e)}")
            return False

    def _simplify_sentence(self, text: str) -> str:
        """반복적 표현 생략 및 문장 구조 간소화"""
        # 불필요한 접속사/부사 제거
        text = re.sub(r'(그리고|또한|그러나|그런데|그래서|그럼에도)[,]?\s*', '', text)
        
        # 불필요한 관형어 축약
        text = re.sub(r'매우\s+', '', text)
        text = re.sub(r'아주\s+', '', text)
        
        # 반복적인 표현 제거
        text = re.sub(r'(\w+)\s+\1', r'\1', text)
        
        # 불필요한 문장 부호 정리
        text = re.sub(r'[.,]{2,}', '.', text)
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        
        # 불필요한 공백 제거
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _is_punctuation_appropriate(self, token) -> bool:
        """구두점이 적절한 위치에 있는지 판단"""
        if token.text == '.' and token.i == len(token.sent) - 1:
            return True
        if token.text == '.' and token.i != len(token.sent) - 1:
            return False
        if token.text in ['.', '!', '?']:
            if token.i == len(token.doc) - 1:
                return True
            if token.nbor(1).text in ['.', '!', '?']:
                return False
        return True

    def _correct_punctuation(self, text: str) -> str:
        """구두점의 적절성을 판단하고 수정"""
        doc = self.nlp(text)
        corrected_text = []
        
        for sent in doc.sents:
            for token in sent:
                if token.is_punct:
                    if self._is_punctuation_appropriate(token):
                        corrected_text.append(token.text)
                    else:
                        continue
                else:
                    corrected_text.append(token.text_with_ws)
        
        return "".join(corrected_text).strip()

    def _split_long_sentences(self, text: str, max_length: int = 40) -> str:
        """긴 문장을 짧은 문장으로 분리"""
        doc = self.nlp(text)
        sentences = [sent.text for sent in doc.sents]
        result = []
        
        for sent in sentences:
            if len(sent) > max_length:
                sub_sentences = [sub_sent.text for sub_sent in self.nlp(sent).sents]
                result.extend(sub_sentences)
            else:
                result.append(sent)
        
        return " ".join(result)

    def _preprocess_text(self, text: str) -> str:
        """번역 전 텍스트 전처리"""
        text = self._split_long_sentences(text)
        text = self._correct_punctuation(text)
        return text

    async def translate_text(self, text: str) -> str:
        """텍스트 번역"""
        try:
            # 번역 전 텍스트 전처리
            text = self._preprocess_text(text)
            
            # 번역 수행
            result = self.client.translate(
                text,
                source_language='en',
                target_language='ko',
                model='nmt',
                format_='text'
            )
            
            translated = result['translatedText']
            
            # 번역 후처리
            translated = self._simplify_sentence(translated)
            
            return translated
            
        except Exception as e:
            print(f"번역 실패: {str(e)}")
            return None

    async def process_transcript(self, text: str, task_id: str, input_filename: str) -> Optional[str]:
        """
        타임스탬프가 포함된 텍스트를 번역
        
        Args:
            text (str): 번역할 텍스트
            task_id (str): 작업 ID
            input_filename (str): 입력 파일명
        """
        try:
            translated_lines = []
            lines = text.split('\n')
            total_lines = len(lines)
            
            # 각 줄을 처리
            for i, line in enumerate(lines):
                # 타임스탬프와 텍스트 분리
                if '[' in line and ']' in line:
                    timestamp, text = line.split(']', 1)
                    timestamp += ']'
                    text = text.strip()
                    
                    # 번역
                    translated_text = await self.translate_text(text)
                    if not translated_text:
                        continue
                    
                    # 타임스탬프에서 시작 시간과 종료 시간 추출
                    time_range = timestamp.strip('[]').split('s - ')
                    start_time = time_range[0]
                    end_time = time_range[1].replace('s', '')
                    
                    # TSV 형식으로 데이터 저장
                    translated_lines.append(f"{start_time}\t{end_time}\t{translated_text}")
            
            # 입력 파일명에서 확장자를 제거하고 .tsv 확장자 추가
            base_filename = os.path.splitext(input_filename)[0]
            output_filename = f"{base_filename}.tsv"
            
            # TSV 파일로 저장
            output_path = os.path.join(self.output_dir, output_filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("start_time\tend_time\ttranslated_text\n")
                f.write('\n'.join(translated_lines))
            
            # GCS에 업로드
            gcs_bucket = "gs://onevoice-test-bucket/resources/text_ko"
            await self._upload_to_gcs(output_path, f"{gcs_bucket}/{output_filename}")
            
            return '\n'.join(translated_lines)
            
        except Exception as e:
            print(f"트랜스크립트 처리 실패: {str(e)}")
            return None

# 서비스 인스턴스 생성
nmt_service = NMTService() 