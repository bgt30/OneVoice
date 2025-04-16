import os
import asyncio
import argparse
from dotenv import load_dotenv
from src.services.stt_with_diarization import stt_with_diarization_service

# 환경 변수 로드
load_dotenv()

async def process_audio_file(audio_path: str, use_merger: bool = False, min_speakers: int = 2, max_speakers: int = 6):
    """
    오디오 파일 처리 및 화자 분리 수행
    
    Args:
        audio_path (str): 처리할 오디오 파일 경로
        use_merger (bool): diarization_stt_merger 형식으로 출력할지 여부
        min_speakers (int): 최소 화자 수
        max_speakers (int): 최대 화자 수
    """
    if not os.path.exists(audio_path):
        print(f"파일이 존재하지 않습니다: {audio_path}")
        return
    
    print(f"오디오 파일 처리 시작: {audio_path}")
    print(f"화자 분리 설정: 최소 {min_speakers}명, 최대 {max_speakers}명")
    
    try:
        if use_merger:
            # diarization_stt_merger 형식으로 출력
            result_path = await stt_with_diarization_service.merge_with_diarization_stt_merger(
                audio_path, min_speakers, max_speakers
            )
            if result_path:
                print(f"처리 완료! 결과 파일: {result_path}")
                
                # 결과 파일 내용 출력
                with open(result_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    print("\n처리 결과 샘플 (처음 10줄):")
                    print("\n".join(lines[:min(10, len(lines))]))
            else:
                print("처리 실패!")
        else:
            # 일반 화자 분리 처리
            result = await stt_with_diarization_service.transcribe_with_diarization(
                audio_path, min_speakers, max_speakers
            )
            if result:
                print("처리 완료!")
                print(f"감지된 화자 수: {len(result['speakers'])}")
                print(f"세그먼트 수: {len(result['segments'])}")
                
                # 세그먼트 샘플 출력
                print("\n처리 결과 샘플 (처음 5개 세그먼트):")
                for i, segment in enumerate(result['segments'][:min(5, len(result['segments']))]):
                    print(f"[{segment['start_time']:.2f}s - {segment['end_time']:.2f}s] 화자 {segment['speaker']}: {segment['text']}")
            else:
                print("처리 실패!")
    
    except Exception as e:
        print(f"처리 중 오류 발생: {str(e)}")
        import traceback
        print(traceback.format_exc())

async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="STT와 화자 분리 테스트 스크립트")
    parser.add_argument("audio_path", help="처리할 오디오 파일 경로")
    parser.add_argument("--merger", action="store_true", help="diarization_stt_merger 형식으로 출력")
    parser.add_argument("--min-speakers", type=int, default=2, help="최소 화자 수 (기본값: 2)")
    parser.add_argument("--max-speakers", type=int, default=6, help="최대 화자 수 (기본값: 6)")
    
    args = parser.parse_args()
    
    await process_audio_file(args.audio_path, args.merger, args.min_speakers, args.max_speakers)

if __name__ == "__main__":
    asyncio.run(main()) 