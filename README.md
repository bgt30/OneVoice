# OneVoice

![OneVoice Demo](./home.gif)

OneVoice is a web application that automatically dubs English videos into Korean. You can upload YouTube links or MP4 files to translate and dub the audio.

## Features

- Upload and process local MP4 video files
- Process videos via YouTube URL input
- Extract English audio and convert to text (STT)
- Translate text from English to Korean
- Convert Korean text to speech (TTS)
- Synthesize translated Korean audio with the original video
- Real-time monitoring of task progress
- Download feature for result videos

## Upcoming Features

- **Speaker Recognition**: Automatically identify and separate different speakers in the source video
- **Speech Style and Emotion Cloning**: Reproduce speech styles, emotions, and intonation patterns from the original audio
- **Voice Cloning**: Clone and reproduce voices of specific speakers for more authentic dubbing
- **Lip-Sync Technology**: Apply advanced lip-sync algorithms to match audio with video mouth movements
- **Multi-speaker TTS**: Generate different voice profiles for each speaker in the video

## Technology Stack

### Backend
- **Python**: Implementation of main backend logic
- **FastAPI**: RESTful API server
- **Google Cloud Platform**:
  - Speech-to-Text API: Voice recognition
  - Translation API: Text translation
  - Text-to-Speech API: Speech synthesis
- **FFmpeg**: Audio/video processing
- **Redis**: Store task status and metadata
- **yt-dlp**: YouTube video download

### Frontend
- **React**: Building user interface
- **TypeScript**: Enhanced type safety
- **Material-UI**: UI components and styling
- **React Router**: Client-side routing

### Infrastructure
- **Docker**: Application containerization
- **Docker Compose**: Multi-container application orchestration
- **Google Cloud Storage**: Storage for processed media files

## System Architecture

OneVoice consists of the following main components:

1. **Frontend**: User interface and interaction handling
2. **Backend API**: File uploads, processing task coordination, status provision
3. **Task Manager**: Asynchronous task processing and status tracking
4. **Media Processor**: Audio/video extraction and synthesis
5. **AI Service Wrapper**: Google Cloud API integration

Processing pipeline:
```
Upload/YouTube link → Video download → Audio extraction → 
STT → Text translation → TTS → Audio/video synthesis → Result
```

## Installation and Execution

### Prerequisites
- Docker and Docker Compose installed
- Google Cloud Platform account and API usage setup
- GCP service account key (JSON)

### Environment Setup
1. Clone the repository
```bash
git clone https://github.com/your-username/onevoice.git
cd onevoice
```

2. Set environment variables
Create a `.env` file in the root directory and set the following variables:
```
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_LOCATION=global
```

3. Save the GCP service account key file as `backend/credentials.json`

### Running the Application
```bash
docker-compose up --build
```

The application can be accessed at the following addresses:
- Frontend: http://localhost
- Backend API: http://localhost:8000

## Project Structure

```
onevoice/
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── api/            # API client
│   │   └── utils/          # Utility functions
│   ├── Dockerfile          # Frontend docker image definition
│   └── nginx.conf          # Nginx configuration
├── backend/                # Backend API server
│   ├── src/
│   │   ├── routes/         # API endpoints
│   │   ├── services/       # Business logic
│   │   └── tests/          # Tests
│   ├── Dockerfile          # Backend docker image definition
│   └── credentials.json    # GCP service account key (needs to be added)
└── docker-compose.yml      # Container configuration
```

## Limitations

- Currently only processes videos less than 10 minutes in length
- Main language is limited to English (original) to Korean (translation)
- Processing performance depends on GCP API limitations and server performance

## License

[MIT License](LICENSE) 