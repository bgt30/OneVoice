/// <reference types="vite/client" />

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface TaskStatusResponse {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  stage?: 'stt' | 'translation' | 'tts';
  progress?: number;
  error?: string;
  result?: string;
  gcs_url?: string;
}

export const getTaskStatus = async (taskId: string): Promise<TaskStatusResponse> => {
  const response = await fetch(`${API_BASE_URL}/api/process/status/${taskId}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '상태 조회에 실패했습니다.');
  }

  return response.json();
};

export const uploadVideo = async (formData: FormData): Promise<{ task_id: string }> => {
  const response = await fetch(`${API_BASE_URL}/api/process`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '비디오 업로드에 실패했습니다.');
  }

  return response.json();
};

export const processYouTube = async (url: string): Promise<{ task_id: string }> => {
  const response = await fetch(`${API_BASE_URL}/api/process/youtube`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'YouTube 비디오 처리에 실패했습니다.');
  }

  return response.json();
};

export const downloadVideo = async (taskId: string): Promise<Blob> => {
  const response = await fetch(`${API_BASE_URL}/api/process/download/${taskId}`);
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '비디오 다운로드에 실패했습니다.');
  }

  return response.blob();
};

export const submitFeedback = async (taskId: string, rating: number): Promise<void> => {
  const response = await fetch(`${API_BASE_URL}/api/process/feedback/${taskId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ rating }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '피드백 제출에 실패했습니다.');
  }
}; 