# OneVoice API 명세서

OneVoice API는 영어 비디오를 한국어로 자동 더빙하는 서비스를 제공합니다. 이 문서는 사용 가능한 모든 엔드포인트, 요청 형식, 응답 구조에 대한 상세 정보를 제공합니다.

## 기본 정보

- **기본 URL**: `http://localhost:8000` (개발 환경) 또는 배포된 서버 주소
- **응답 형식**: JSON
- **인증 방식**: 현재 인증 기능은 구현되어 있지 않습니다 (향후 구현 예정)

## 엔드포인트

### 1. 파일 업로드

로컬 MP4 비디오 파일을 업로드하여 처리를 시작합니다.

- **URL**: `/api/process/upload`
- **메소드**: `POST`
- **콘텐츠 타입**: `multipart/form-data`

**요청 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| file | File | 예 | MP4 형식의 비디오 파일 (최대 150MB) |

**응답**:
```json
{
  "task_id": "string",
  "status": "INITIATED",
  "message": "Video upload successful, processing started"
}
```

**상태 코드**:
- 202: 요청 성공, 처리 시작됨
- 400: 잘못된 요청 (파일 형식, 크기 등)
- 500: 서버 오류

### 2. YouTube 처리

YouTube URL을 제출하여 처리를 시작합니다.

- **URL**: `/api/process/youtube`
- **메소드**: `POST`
- **콘텐츠 타입**: `application/json`

**요청 본문**:
```json
{
  "url": "string"
}
```

**응답**:
```json
{
  "task_id": "string",
  "status": "INITIATED",
  "message": "YouTube video download initiated"
}
```

**상태 코드**:
- 202: 요청 성공, 처리 시작됨
- 400: 잘못된 요청 (유효하지 않은 URL 등)
- 500: 서버 오류

### 3. 작업 상태 확인

작업의 현재 상태와 진행률을 확인합니다.

- **URL**: `/api/process/status/{task_id}`
- **메소드**: `GET`

**경로 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| task_id | string | 예 | 처리 작업 ID |

**응답**:
```json
{
  "task_id": "string",
  "status": "string",
  "progress": {
    "step": "string",
    "percentage": number,
    "message": "string"
  },
  "result": {
    "video_url": "string",
    "download_url": "string"
  }
}
```

**상태 유형**:
- `INITIATED`: 작업이 시작됨
- `DOWNLOADING`: YouTube 비디오 다운로드 중
- `EXTRACTING_AUDIO`: 오디오 추출 중
- `STT_PROCESSING`: 음성-텍스트 변환 중
- `TRANSLATING`: 텍스트 번역 중
- `TTS_PROCESSING`: 텍스트-음성 변환 중
- `MERGING`: 비디오와 오디오 병합 중
- `COMPLETED`: 작업 완료됨
- `FAILED`: 작업 실패

**상태 코드**:
- 200: 성공
- 404: 작업 ID를 찾을 수 없음
- 500: 서버 오류

### 4. 결과 비디오 다운로드

처리된 비디오를 다운로드합니다.

- **URL**: `/api/process/download/{task_id}`
- **메소드**: `GET`

**경로 파라미터**:
| 이름 | 타입 | 필수 | 설명 |
|------|------|------|------|
| task_id | string | 예 | 처리 작업 ID |

**응답**:
- 성공 시: 비디오 파일 스트림 (MP4)
- 실패 시: JSON 오류 메시지

**상태 코드**:
- 200: 성공
- 404: 작업 ID를 찾을 수 없음 또는 결과 파일 없음
- 500: 서버 오류

### 5. 피드백 제출

처리된 비디오에 대한 사용자 피드백을 제출합니다.

- **URL**: `/api/process/feedback`
- **메소드**: `POST`
- **콘텐츠 타입**: `application/json`

**요청 본문**:
```json
{
  "task_id": "string",
  "rating": number,
  "comment": "string"
}
```

**응답**:
```json
{
  "success": true,
  "message": "Feedback submitted successfully"
}
```

**상태 코드**:
- 200: 성공
- 400: 잘못된 요청
- 404: 작업 ID를 찾을 수 없음
- 500: 서버 오류

## 오류 응답

오류가 발생하는 경우, API는 다음과 같은 형식으로 오류 정보를 반환합니다:

```json
{
  "error": true,
  "code": "string",
  "message": "string",
  "details": {}
}
```

## 제한 사항

- 처리 가능한 최대 비디오 길이: 10분
- 최대 파일 크기: 150MB
- 지원되는 비디오 형식: MP4
- 지원되는 YouTube 영상: 최대 10분, 공개 또는 비공개 해제된 영상만 처리 가능

## API 변경 이력

| 날짜 | 버전 | 변경 사항 |
|------|------|----------|
| 2024-03-20 | 0.1.0 | 초기 API 설계 | 