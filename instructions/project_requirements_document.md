# Project Requirements Document (PRD)

## 1. Project Overview

This project is an MVP for a video dubbing service that enables English video content creators to expand their reach by dubbing their videos into Korean. The service allows users to either upload an MP4 video file directly or provide a YouTube link (with a 10-minute maximum duration) for processing. Using Google Cloud Services—specifically Speech-to-Text (STT), Neural Machine Translation (NMT), and Text-to-Speech (TTS)—the system extracts the audio from the video, translates it, and then synthesizes new audio that is merged back with the video. Video processing is managed through ffmpeg and the final dubbed video is then made available for download.

The project is being built to simplify the process for content creators looking to access the Korean market. The key objectives are to deliver a seamless video dubbing experience with real-time progress updates and a modular architecture that can easily be extended to support additional languages and integrations in the future. Success is measured by the accuracy and natural flow of the dubbed audio, robust error handling, and ease of use that encourages user satisfaction and positive feedback.

## 2. In-Scope vs. Out-of-Scope

### In-Scope:

*   **Video Input Options**: Users can either upload an MP4 file or provide a YouTube link (with a 10-minute duration limit).

*   **Video Validation**: Immediate validation of video format (only MP4 allowed) and duration.

*   **Audio Extraction and Processing**: Using ffmpeg to extract audio from uploaded or linked videos.

*   **Translation Pipeline**:

    *   Convert English audio to text (Google STT).
    *   Translate text from English to Korean (Google NMT).
    *   Convert translated text back to audio (Google TTS).

*   **User Interface**:

    *   Home Page with video upload and YouTube link input.
    *   Translation Screen with a real-time progress bar and step-by-step status updates.
    *   Result Page where users can review, download the dubbed video, and provide feedback.

*   **Feedback Mechanisms**: A simple rating system or text feedback option for dubbing quality and re-processing feature.

*   **Analytics and Monitoring**: Integration with Google Analytics and Google Cloud Monitoring for tracking usage, performance, and error occurrences.

*   **File Management**: Manage processed videos using Google Cloud Storage for scalability.

### Out-of-Scope:

*   **User Account System**: The service will be open to all users without login or registration requirements.
*   **Unsupported Video Formats**: Only MP4 videos are supported; other formats will not be processed.
*   **Overly Complex UI/UX Design**: Advanced branding, animations, or overly custom design elements are deferred in favor of a clean, minimalist, and functional design.
*   **Additional Language Support**: Initially, only English-to-Korean dubbing is supported. Future language support is planned but not part of this MVP.
*   **Extended Video Duration**: Videos longer than 10 minutes will not be processed in the first version.

## 3. User Flow

When a user lands on the home page of the service, they are greeted with a clean, minimal interface that offers two primary options: upload an MP4 video file or enter a YouTube link (with the understanding that videos must be less than 10 minutes). Once the user selects an option, the system immediately validates the input. For direct uploads, the file is checked to ensure it is in MP4 format and within the acceptable duration. For YouTube links, the system uses ffmpeg to extract the audio after verifying the duration constraint. Should any errors be detected (such as unsupported formats or exceeding duration limits), the user receives a prompt notification to correct the issue.

After the video or audio extraction phase, the user is taken to the Translation Screen where clear, real-time feedback is provided via a progress bar segmented into the three main stages: Speech-to-Text (STT), translation (NMT), and Text-to-Speech (TTS). As each processing stage is completed, the progress bar fills with a new color and text messages (such as “Converting speech to text,” “Translating text,” and “Synthesizing speech”) inform the user about the current operation. Upon completion, the user is redirected to the Result Page where they can watch the dubbed video, download the final output, and provide feedback or choose to re-process the video if necessary.

## 4. Core Features

*   **Video Input and Validation**

    *   Upload an MP4 video file or input a YouTube URL (10-minute limit).
    *   Validate file format and video duration immediately.
    *   Provide real-time user notifications if input errors occur.

*   **Audio Extraction and Merging**

    *   Use ffmpeg to extract audio from both uploaded files and YouTube videos.
    *   Merge synthesized TTS audio back into the final video using ffmpeg.

*   **Translation Workflow**

    *   Convert English audio to text using Google Cloud Services STT.
    *   Translate the extracted text to Korean using Google Cloud Services NMT.
    *   Convert the translated text back to audio using Google Cloud Services TTS.

*   **Real-Time Progress Updates**

    *   Display a segmented progress bar indicating status for STT, translation, and TTS.
    *   Accompany progress bar with clear textual status messages.

*   **Feedback and Re-processing**

    *   Enable users to rate the dubbed audio quality and provide textual feedback.
    *   Offer an option to re-process the video if the initial results are unsatisfactory.

*   **Analytics & Monitoring**

    *   Integrate Google Analytics to track user interactions.
    *   Use Google Cloud Monitoring to track backend performance and error incidents.

*   **Scalability & Storage**

    *   Store processed videos in Google Cloud Storage for scalability as user volume grows.

## 5. Tech Stack & Tools

*   **Frontend Technologies**:

    *   React.js for building the user interface.
    *   Material-UI to ensure a clean, minimalist, and responsive design.
    *   V0 by Vercel for AI-powered frontend component building (optional enhancement).

*   **Backend Technologies**:

    *   FastAPI in Python for building the backend APIs.
    *   Python as the main language for backend development.
    *   Integration with Google Cloud Services (STT, NMT, TTS) for dubbing processes.
    *   ffmpeg for audio extraction and merging.

*   **Additional Tools & Integrations**:

    *   VS Code and the Cursor IDE for a modern development experience.
    *   Deepseek, Claude AI, and ChatGPT for potential code generation and intelligent code assistance.
    *   Google Analytics and Google Cloud Monitoring for tracking and performance measurement.

## 6. Non-Functional Requirements

*   **Performance**:

    *   The dubbing process should provide real-time feedback with minimal delay in the progress bar updates.
    *   API response times should be optimized, especially during the STT, translation, and TTS stages, to ensure a smooth user experience.

*   **Security**:

    *   Implement proper error handling and input validation to prevent malformed data or potential exploits.
    *   Ensure secure API communication between the FastAPI backend and Google Cloud Services.

*   **Usability**:

    *   The frontend must be user-friendly, with clear instructions and responsive design.
    *   Feedback mechanisms and error notifications should be intuitive and assist users in correcting issues quickly.

*   **Compliance**:

    *   Adhere to best practices for data privacy and ensure that any user data processed is managed securely.

*   **Scalability**:

    *   The system design should support horizontal scaling, particularly for backend processing and cloud storage.
    *   Consider future integration with additional languages and video sources without significant rework.

## 7. Constraints & Assumptions

*   The system only supports MP4 video files and YouTube links with videos up to 10 minutes long.
*   It is assumed that there is reliable availability of Google Cloud Services (STT, NMT, and TTS) for the MVP.
*   ffmpeg is assumed to be properly installed and configured on the deployment environment for both audio extraction and merging.
*   The service will initially be open to all users without any login or user account requirements.
*   The English-to-Korean translation is the sole focus for this version, with future extensions planned for additional languages.
*   The MVP prioritizes functionality and reliability, so advanced design or branding features are not a focus at this stage.

## 8. Known Issues & Potential Pitfalls

*   **API Limitations and Failures**:

    *   There is a risk of failing API calls to Google Cloud Services. Use robust try-catch mechanisms in FastAPI and implement logging for diagnostics.
    *   Consider implementing retries for transient failures and inform the user with clear, user-friendly error messages if an API call fails.

*   **Video Processing Challenges**:

    *   Handling edge cases such as slight format variations in uploaded MP4 files might be a potential pitfall.
    *   Ensure ffmpeg commands are robust and handle errors gracefully during audio extraction and merging.

*   **Performance Bottlenecks**:

    *   Processing time for audio extraction, transcription, translation, and synthesis might vary. Setting user expectations with a real-time progress bar is crucial.
    *   Monitor backend performance actively using Google Cloud Monitoring to identify and address bottlenecks.

*   **User Experience Hiccups**:

    *   Immediate notifications and error handling on the frontend must be clear to avoid confusing the user, particularly during high load or process failures.
    *   Testing should be thorough on various network conditions to ensure that real-time feedback remains accurate and timely.

*   **Scalability Concerns**:

    *   As the service scales, managing storage (Google Cloud Storage) and processing load will become critical. Modular design and clear APIs will help in incremental scaling.

This document serves as a comprehensive guide for the AI-driven generation of further technical documents and subsequent development tasks. It outlines every significant detail to ensure there is no ambiguity regarding what must be built in the MVP for this video dubbing service.
