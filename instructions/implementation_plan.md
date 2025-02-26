**Phase 1: Environment Setup** [완료]

1.  Create the project directory structure with two main folders: `/frontend` for the React app and `/backend` for the FastAPI service. *(PRD Section 1: Project Overview)* [완료]
2.  Initialize a Git repository in the project root and create two branches: `main` and `dev`. *(PRD Section 1: Project Overview)* [완료]
3.  Ensure the development environment has Python (recommended 3.11.x) installed and set up VS Code with Python and JavaScript extensions. *(Tech Stack: Backend, VS Code)* [완료]
4.  Install ffmpeg on the local machine to be used for audio extraction and merging. *(PRD Section 2: Video Validation and Audio Extraction)* [완료]
5.  **Validation**: Run `ffmpeg -version` to confirm ffmpeg installation. [완료]

**Phase 2: Frontend Development** [완료]

1.  Initialize a React.js project in the `/frontend` folder using Create React App. *(PRD Section 3: User Flow | Frontend Technologies)* [완료]

2.  Install Material-UI components in the React project for clean and minimalist design. *(frontend_guidelines_document)* [완료]

3.  Create a `HomePage.js` component in `/frontend/src/components/` that includes:

    *   An MP4 video file upload button with client-side validation for file type.
    *   A text input for YouTube links with instructions on the 10-minute limit. *(PRD Section 3: Video Input and Validation)* [완료]

4.  **Validation**: Run `npm start` in the `/frontend` folder and manually verify the home page renders with proper input fields. [완료]

5.  Create a `TranslationScreen.js` component in `/frontend/src/components/` that displays a segmented progress bar representing the stages: STT, translation, and TTS. Use Material-UI's progress bar and include text labels below (e.g., "Converting speech to text", "Translating text", "Synthesizing speech"). *(PRD Section 4: Real-Time Progress Updates)* [완료]

6.  **Validation**: Manually test the progress indicator by simulating stage changes. [완료]

7.  Create a `ResultPage.js` component in `/frontend/src/components/` that allows users to play the dubbed video, download the result, and provide feedback via a simple rating system and optional text input. *(PRD Section 4: Feedback and Re-processing)* [완료]

8.  **Validation**: Open the Result Page in the browser; ensure the video player, download button, and feedback form are functional. [완료]

**Phase 3: Backend Development** [완료]

1.  Initialize a Python virtual environment in the `/backend` folder and install FastAPI and Uvicorn. *(Tech Stack: FastAPI, Python)* [완료]
2.  Create a main FastAPI file (`main.py`) in `/backend/` that initializes the app and configures CORS to allow requests from the frontend (typically `http://localhost:3000`). *(PRD Section 3: User Flow & Error Handling)* [완료]
3.  **Validation**: Run `uvicorn main:app --reload` and verify the API server is accessible at `http://localhost:8000`. [완료]
4.  Create an API endpoint `POST /api/process` in `/backend/routes/process.py` that accepts either an uploaded MP4 file or a YouTube link. *(PRD Section 2: Video Input Options)* [완료]
5.  Within the `/api/process` endpoint, implement input validation to ensure:
    *   Only MP4 files are processed.
    *   For YouTube links, the video duration is checked to be under 10 minutes before processing. *(PRD Section 2: Video Validation)* [완료]
6.  **Validation**: Write a simple test script or use Postman to send a sample MP4 file and a YouTube link to `/api/process` and check for proper validation responses. [완료]
7.  Create helper functions under `/backend/services/` to interface with Google Cloud Services:
    *   `stt.py` for converting audio to text using Google STT. [완료]
    *   `nmt.py` for translating text using Google NMT. [완료]
    *   `tts.py` for converting translated text to audio using Google TTS. Use Python's `subprocess` module to call ffmpeg commands for audio extraction from both uploaded files and YouTube downloads, as well as merging TTS audio back into the video. *(PRD Section 2: Audio Extraction and Merging)* [완료]
8.  Add error handling in each service module using try-catch blocks. Log errors and return user-friendly error messages for failed API calls. *(PRD Section 4: Error Handling)* [완료]
9.  **Validation**: Write unit tests in `/backend/tests/` to simulate failures in each service and check that errors are captured and logged appropriately. [완료]
10. Implement task status management using Redis to track processing progress and store results. *(PRD Section 4: Real-Time Progress Updates)* [완료]

**Phase 4: Integration**

1.  In the React frontend, add API calls using Axios to send video data from the `HomePage.js` to the `/api/process` endpoint on the backend. *(PRD Section 3: User Flow)* [완료]
2.  Set up endpoints in the React app to poll or receive real-time updates from the backend for processing progress (consider using WebSockets or long polling for updates to the progress bar in `TranslationScreen.js`). *(PRD Section 4: Real-Time Progress Updates)* [완료]
3.  **Validation**: Upload a test video and verify that the frontend progress bar receives and displays updates from the backend. [완료]
4.  Integrate Google Analytics tracking code in the React application to monitor page interactions and user activity. *(PRD Section 4: Analytics & Monitoring)*

**Phase 5: Deployment**

1.  Prepare deployment configurations by creating Dockerfiles for the backend service using Python and for the frontend build. *(PRD Section 7: Non-Functional Requirements)* [완료]
2.  For the backend, write a Dockerfile in `/backend/Dockerfile` that defines the environment to run FastAPI with Uvicorn. [완료]
3.  **Validation**: Build the backend Docker image and run it locally to ensure the container starts correctly using `docker build -t video-dubbing-backend .` and `docker run -p 8000:8000 video-dubbing-backend`. [완료]
4.  Create a production build for the React frontend using `npm run build` in the `/frontend` directory. *(PRD Section 7: Scalability & Storage)* [완료]
5.  **Validation**: Confirm build output by verifying the contents of the `/frontend/build` directory. [완료]
6.  For storage of processed videos, configure Google Cloud Storage by setting up a bucket (e.g., `video-dubbing-mvp-<unique-id>`) in the appropriate region. Update the backend to upload final dubbed videos to this bucket. *(PRD Section 4: Scalability & Storage)* [완료]
7.  **Validation**: Use the Google Cloud Console to verify files are uploaded into the designated bucket after processing a video. [완료]
8.  Set up CI/CD integration using GitHub Actions to automate tests, builds, and deployments for both frontend and backend. *(PRD Section 7: Non-Functional Requirements)* [완료]
9.  **Validation**: Run end-to-end tests (manual or using a tool like Cypress) on the deployed environment to ensure the complete flow functions as expected. [진행 중]

**Notes**:

*   The FastAPI backend (and supporting scripts like those interfacing with ffmpeg and Google Cloud Services) must be written entirely in Python.
*   The React frontend will leverage Material-UI for rapid UI development and a clean, professional design.
*   Robust error handling is essential throughout the backend to ensure clear and user-friendly error messages in case of failure in the STT, NMT, or TTS processes.
*   The re-processing option and feedback mechanism on the Result Page in the frontend need to be easily extendable for future enhancements.

This plan covers the full implementation from environment setup through deployment to ensure the MVP meets the functional requirements for the video dubbing service.
