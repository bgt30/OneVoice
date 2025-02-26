## Project Overview

*   **Type:** cursor_project_rules
*   **Description:** This MVP is a video dubbing service that focuses on translating English videos into Korean. Users can either upload an MP4 video file or provide a YouTube link (with a 10-minute duration limit) for dubbing. The service uses Google Cloud Services (STT, NMT, TTS) to extract, translate, and synthesize audio, with ffmpeg handling both audio extraction and merging.
*   **Primary Goal:** Deliver a seamless video dubbing experience with real-time progress updates and a modular, scalable architecture that ensures accurate translations and natural-sounding dubbed audio while enabling future support for additional languages and integrations.

## Project Structure

### Framework-Specific Routing

*   **Directory Rules:**

    *   **React Router 6:** Projects built with React.js should use the `src/routes/` directory to manage route-based component mapping. For instance, the Home Page, Translation Screen, and Result Page can be managed as separate route components within `src/routes/`.
    *   Example: `src/routes/home.jsx` for the home page; `src/routes/translate.jsx` for the translation progress screen; `src/routes/result.jsx` for the results and feedback page.

### Core Directories

*   **Versioned Structure:**

    *   **frontend:** Contains the React.js application with all UI components, routes, and Material-UI theming.

        *   Example: `src/App.js` – Main application component integrating React Router.
        *   Example: `src/components/` – Reusable UI components (e.g., progress bar, notifications).

    *   **backend:** Hosts the FastAPI (Python) application with API endpoints, error handling, and integration logic for Google Cloud Services.

        *   Example: `app/main.py` – FastAPI entry point.
        *   Example: `app/routers/` – API route modules for handling video upload, processing, and feedback.

### Key Files

*   **Stack-Versioned Patterns:**

    *   **Frontend Key File:**

        *   `src/App.js`: Acts as the root component. Implements React Router 6 for client-side navigation.

    *   **Backend Key File:**

        *   `app/main.py`: Contains the FastAPI application instance and route inclusions.

### Tech Stack Rules

*   **Version Enforcement:**

    *   **React.js (with React Router 6):** Ensure usage of the latest stable version and maintain a clear folder structure within the `src/` directory.
    *   **FastAPI & Python:** Use Python 3.x with FastAPI, enforcing best practices in error handling (try-catch mechanisms) and API endpoint structuring.
    *   **ffmpeg:** Commands must be robust, handling both audio extraction from input videos and merging synthesized audio with proper error checking.
    *   **Material-UI:** Utilize Material-UI for consistent styling and responsive design; adhere to accessibility practices.

### PRD Compliance

*   **Non-Negotiable:**

    *   "Users can either upload an MP4 video file or provide a YouTube link (with a 10-minute maximum duration) for processing."

        *   This constraint must be strictly followed in both frontend validation and backend processing.

### App Flow Integration

*   **Stack-Aligned Flow:**

    *   Example: The Translation Screen in the React application (`src/routes/translate.jsx`) should display a segmented progress bar showing the status for STT, translation (NMT), and TTS processes. Each segment updates in real time with color changes and accompanying textual messages (e.g., "Converting speech to text", "Translating text", "Synthesizing speech").

## Best Practices

*   **React.js**

    *   Maintain modular and reusable components.
    *   Leverage React Router 6 for clear and functional routing.
    *   Ensure the UI is accessible, responsive, and minimalist using Material-UI.

*   **FastAPI & Python**

    *   Use proper error handling with try-catch blocks and dependency injection.
    *   Follow PEP-8 standards and implement type hints for maintainability.
    *   Structure API endpoints to clearly separate concerns (e.g., video validation, processing, feedback).

*   **Google Cloud Services (STT, NMT, TTS)**

    *   Secure API keys and handle quotas/rate limits with retry logic.
    *   Log API responses for monitoring and diagnostics.
    *   Ensure data integrity between each processing stage.

*   **ffmpeg**

    *   Build robust command-line calls with error checking and logging.
    *   Validate outputs at each stage of audio extraction and merging.

*   **VS Code**

    *   Utilize extensions for linting, formatting, and debugging (e.g., Pylint, Prettier).
    *   Maintain consistent workspace settings across the team.

*   **Material-UI**

    *   Leverage theme customization to maintain a professional, minimalist design.
    *   Ensure components adhere to accessibility guidelines.

## Rules

*   Derive folder/file patterns directly from the tech stack documentation and enforce consistency across the project directories.
*   For the React frontend using React Router 6: enforce the `src/routes/` structure; avoid mixing patterns like Next.js app or pages directories.
*   The FastAPI backend should structure its routes and error handling consistently, with all API logic placed under an intuitive directory (e.g., `app/routers/`).
*   Ensure that versioned patterns and practices are not mixed (e.g., do not implement Next.js App Router patterns in the React project).
*   Maintain clear separation of concerns between frontend and backend codebases to facilitate scalability, testing, and future extensibility.
