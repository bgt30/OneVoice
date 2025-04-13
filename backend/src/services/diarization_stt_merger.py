import os
import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from . import config

class DiarizationSTTMerger:
    """STT 결과와 화자 분리 결과를 통합하는 클래스"""
    
    def __init__(self):
        self.output_dir = os.path.join(config.TEMP_DIR, "merged_results")
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    async def merge_results(self, 
                           stt_transcript: str, 
                           diarization_result: Dict[str, Any], 
                           audio_path: str) -> Optional[str]:
        """
        STT 트랜스크립트와 화자 분리 결과를 병합
        
        Args:
            stt_transcript (str): STT 서비스에서 생성된 타임스탬프가 포함된 트랜스크립트
            diarization_result (Dict[str, Any]): PyAnnote.ai에서 반환된 화자 분리 결과
            audio_path (str): 오디오 파일 경로
            
        Returns:
            Optional[str]: 병합된 결과 파일 경로
        """
        try:
            # 오디오 파일명 추출 (확장자 제외)
            base_filename = os.path.splitext(os.path.basename(audio_path))[0]
            print(f"결과 병합 시작 - 파일: {base_filename}")
            
            # 1. STT 트랜스크립트 파싱
            stt_segments = self._parse_stt_transcript(stt_transcript)
            if not stt_segments:
                print("STT 트랜스크립트를 파싱할 수 없습니다.")
                return None
                
            # 2. 화자 분리 결과 파싱
            diarization_segments = self._parse_diarization_result(diarization_result)
            if not diarization_segments:
                print("화자 분리 결과를 파싱할 수 없습니다.")
                return None
                
            # 3. 두 결과 통합 (세그먼트별 화자 할당)
            merged_segments = self._align_segments(stt_segments, diarization_segments)
            
            # 4. 세그먼트를 문장 단위로 병합
            sentence_segments = self._merge_segments_into_sentences(merged_segments)
            
            # 5. 텍스트 형식으로 결과 저장
            output_file = os.path.join(self.output_dir, f"{base_filename}_merged.txt")
            with open(output_file, "w", encoding="utf-8") as f:
                for segment in sentence_segments:
                    start_time = segment["start"]
                    end_time = segment["end"]
                    speaker = segment["speaker"]
                    text = segment["text"]
                    f.write(f"[{start_time:.2f}s - {end_time:.2f}s] 화자 {speaker}: {text}\n")
            
            print(f"결과 병합 완료: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"결과 병합 중 오류 발생: {str(e)}")
            return None
    
    def _parse_stt_transcript(self, transcript: str) -> List[Dict[str, Any]]:
        """
        STT 트랜스크립트를 파싱하여 세그먼트 목록으로 변환
        
        예시 입력:
        [0.00s - 2.50s] 안녕하세요, 여러분.
        [2.70s - 4.50s] 오늘은 좋은 날씨입니다.
        
        Returns:
            List[Dict[str, Any]]: 세그먼트 목록
        """
        segments = []
        
        try:
            lines = transcript.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line or not line.startswith('['):
                    continue
                    
                # 타임스탬프와 텍스트 분리
                timestamp_end = line.find(']')
                if timestamp_end == -1:
                    continue
                    
                timestamp_part = line[1:timestamp_end]
                text_part = line[timestamp_end+1:].strip()
                
                # 타임스탬프 파싱 (예: 0.00s - 2.50s)
                time_parts = timestamp_part.replace('s', '').split(' - ')
                if len(time_parts) != 2:
                    continue
                    
                start_time = float(time_parts[0])
                end_time = float(time_parts[1])
                
                # 세그먼트 추가
                segments.append({
                    "start": start_time,
                    "end": end_time,
                    "text": text_part,
                    "speaker": None  # 초기에는 화자 정보 없음
                })
                
            return segments
            
        except Exception as e:
            print(f"STT 트랜스크립트 파싱 오류: {str(e)}")
            return []
    
    def _parse_diarization_result(self, diarization_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        PyAnnote.ai의 화자 분리 결과를 파싱하여 세그먼트 목록으로 변환
        
        Returns:
            List[Dict[str, Any]]: 세그먼트 목록
        """
        segments = []
        
        try:
            # 결과 구조 확인
            print(f"화자 분리 결과 키: {list(diarization_result.keys())}")
            
            # "diarization" 키가 있는 경우 처리
            if "diarization" in diarization_result:
                print(f"화자 분리 결과 형식: 'diarization' 키 사용 (세그먼트 수: {len(diarization_result['diarization'])})")
                for segment in diarization_result["diarization"]:
                    start_time = segment.get("start")
                    end_time = segment.get("end")
                    speaker = segment.get("speaker")
                    
                    if start_time is not None and end_time is not None and speaker is not None:
                        segments.append({
                            "start": float(start_time),
                            "end": float(end_time),
                            "speaker": speaker.replace("SPEAKER_", "")  # SPEAKER_00, SPEAKER_01 등에서 번호만 추출
                        })
            else:
                # diarization 키가 없는 경우
                print(f"경고: 화자 분리 결과에서 'diarization' 키를 찾을 수 없습니다. 사용 가능한 키: {list(diarization_result.keys())}")
            
            # 결과 요약 출력
            if segments:
                print(f"파싱된 화자 분리 세그먼트 수: {len(segments)}")
                print(f"첫 번째 세그먼트 예시: {segments[0]}")
            else:
                print("파싱된 화자 분리 세그먼트가 없습니다.")
            
            return segments
            
        except Exception as e:
            print(f"화자 분리 결과 파싱 오류: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []
    
    def _align_segments(self, 
                       stt_segments: List[Dict[str, Any]], 
                       diarization_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        STT 세그먼트와 화자 분리 세그먼트를 시간 기준으로 정렬
        
        Args:
            stt_segments (List[Dict[str, Any]]): STT 세그먼트 목록
            diarization_segments (List[Dict[str, Any]]): 화자 분리 세그먼트 목록
            
        Returns:
            List[Dict[str, Any]]: 병합된 세그먼트 목록
        """
        try:
            # STT 세그먼트에 화자 정보 할당
            for stt_segment in stt_segments:
                start_time = stt_segment["start"]
                end_time = stt_segment["end"]
                
                # 가장 많이 겹치는 화자 찾기
                speaker_overlaps = {}
                
                for diar_segment in diarization_segments:
                    diar_start = diar_segment["start"]
                    diar_end = diar_segment["end"]
                    diar_speaker = diar_segment["speaker"]
                    
                    # 겹치는 시간 계산
                    overlap_start = max(start_time, diar_start)
                    overlap_end = min(end_time, diar_end)
                    
                    if overlap_end >= overlap_start:  # 겹치는 구간이 있을 때 (같은 지점도 포함)
                        overlap_duration = overlap_end - overlap_start
                        
                        if diar_speaker not in speaker_overlaps:
                            speaker_overlaps[diar_speaker] = 0
                        
                        speaker_overlaps[diar_speaker] += overlap_duration
                
                # 가장 많이 겹치는 화자 선택
                if speaker_overlaps:
                    dominant_speaker = max(speaker_overlaps.items(), key=lambda x: x[1])[0]
                    stt_segment["speaker"] = dominant_speaker
                else:
                    # 겹치는 구간이 없는 경우, 가장 가까운 화자 찾기
                    min_distance = float('inf')
                    closest_speaker = None
                    
                    for diar_segment in diarization_segments:
                        diar_start = diar_segment["start"]
                        diar_end = diar_segment["end"]
                        diar_speaker = diar_segment["speaker"]
                        
                        # 거리 계산 (세그먼트 중심점 간 거리)
                        stt_center = (start_time + end_time) / 2
                        diar_center = (diar_start + diar_end) / 2
                        distance = abs(stt_center - diar_center)
                        
                        if distance < min_distance:
                            min_distance = distance
                            closest_speaker = diar_speaker
                    
                    # 항상 가장 가까운 화자 적용 (1초 제한 없음)
                    if closest_speaker:
                        stt_segment["speaker"] = closest_speaker
                    else:
                        # 화자 정보가 없는 경우 "unknown" 화자로 표시
                        stt_segment["speaker"] = "unknown"
            
            return stt_segments
            
        except Exception as e:
            print(f"세그먼트 정렬 중 오류 발생: {str(e)}")
            return stt_segments  # 오류 발생 시 원본 STT 세그먼트 반환
    
    def _merge_segments_into_sentences(self, 
                                     aligned_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        화자 정보가 있는 세그먼트를 화자 변경 또는 구두점 기준으로 문장 단위로 병합
        
        Args:
            aligned_segments (List[Dict[str, Any]]): 화자 정보가 포함된 세그먼트 목록
            
        Returns:
            List[Dict[str, Any]]: 문장 단위로 병합된 세그먼트 목록
        """
        try:
            if not aligned_segments:
                return []
                
            # 시간순으로 정렬
            sorted_segments = sorted(aligned_segments, key=lambda x: x["start"])
            
            sentences = []
            current_sentence_text = ""
            current_speaker = None
            sentence_start_time = None
            sentence_end_time = None
            
            for i, segment in enumerate(sorted_segments):
                # 첫 번째 세그먼트인 경우 초기화
                if i == 0:
                    current_sentence_text = segment["text"]
                    current_speaker = segment["speaker"]
                    sentence_start_time = segment["start"]
                    sentence_end_time = segment["end"]
                    continue
                
                # 화자가 변경되었거나 현재 세그먼트 텍스트에 구두점이 있는 경우
                prev_segment_text = sorted_segments[i-1]["text"]
                has_punctuation = any(punct in prev_segment_text for punct in ['.', '!', '?'])
                
                if segment["speaker"] != current_speaker or has_punctuation:
                    # 현재까지의 문장 저장
                    sentences.append({
                        "start": sentence_start_time,
                        "end": sentence_end_time,
                        "speaker": current_speaker,
                        "text": current_sentence_text
                    })
                    
                    # 새 문장 시작
                    current_sentence_text = segment["text"]
                    current_speaker = segment["speaker"]
                    sentence_start_time = segment["start"]
                    sentence_end_time = segment["end"]
                else:
                    # 같은 화자의 문장이 계속되는 경우
                    current_sentence_text += " " + segment["text"]
                    sentence_end_time = segment["end"]
            
            # 마지막 문장 추가
            if current_sentence_text:
                sentences.append({
                    "start": sentence_start_time,
                    "end": sentence_end_time,
                    "speaker": current_speaker,
                    "text": current_sentence_text
                })
            
            return sentences
            
        except Exception as e:
            print(f"문장 병합 중 오류 발생: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return aligned_segments  # 오류 발생 시 원본 세그먼트 반환

# 서비스 인스턴스 생성
diarization_stt_merger = DiarizationSTTMerger() 