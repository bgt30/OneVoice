import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  LinearProgress,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { getTaskStatus } from '../api/client';

export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type ProcessingStage = 'stt' | 'translation' | 'tts';

interface TaskStatusResponse {
  status: TaskStatus;
  stage?: ProcessingStage;
  progress?: number;
  error?: string;
  result?: string;
}

const stageLabels = {
  stt: '음성을 텍스트로 변환 중...',
  translation: '텍스트 번역 중...',
  tts: '음성 합성 중...',
  complete: '처리 완료!',
};

const TranslationScreen: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse>({
    status: 'pending',
    progress: 0
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const response = await getTaskStatus(taskId || '');
        setTaskStatus(response);

        if (response.status === 'completed') {
          navigate(`/result/${taskId}`);
        } else if (response.status === 'failed') {
          setError(response.error || '처리 중 오류가 발생했습니다.');
        } else {
          setTimeout(checkStatus, 2000);
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '상태 확인 중 오류가 발생했습니다.';
        setError(errorMessage);
      }
    };

    checkStatus();
  }, [taskId, navigate]);

  const getStageProgress = () => {
    if (!taskStatus.stage || !taskStatus.progress) return 0;
    
    switch (taskStatus.stage) {
      case 'stt':
        return taskStatus.progress * 0.33;
      case 'translation':
        return 33 + (taskStatus.progress * 0.33);
      case 'tts':
        return 66 + (taskStatus.progress * 0.34);
      default:
        return 0;
    }
  };

  if (error) {
    return (
      <Container maxWidth="md">
        <Box sx={{ mt: 8, mb: 4 }}>
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="md">
      <Box sx={{ mt: 8, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          비디오 변환 중
        </Typography>
      </Box>

      <Paper elevation={3} sx={{ p: 4 }}>
        <Box sx={{ width: '100%' }}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="h6" align="center" color="primary">
              {taskStatus.stage ? stageLabels[taskStatus.stage] : '준비 중...'}
            </Typography>
          </Box>

          <Box sx={{ mb: 4 }}>
            <LinearProgress
              variant="determinate"
              value={getStageProgress()}
              sx={{ height: 10, borderRadius: 5 }}
            />
          </Box>

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
            <Typography
              variant="body2"
              color={taskStatus.stage === 'stt' ? 'primary' : 'text.secondary'}
            >
              음성 인식
            </Typography>
            <Typography
              variant="body2"
              color={taskStatus.stage === 'translation' ? 'primary' : 'text.secondary'}
            >
              번역
            </Typography>
            <Typography
              variant="body2"
              color={taskStatus.stage === 'tts' ? 'primary' : 'text.secondary'}
            >
              음성 합성
            </Typography>
          </Box>

          <Typography variant="body2" align="center" color="text.secondary">
            전체 진행률: {Math.round(getStageProgress())}%
          </Typography>
        </Box>
      </Paper>
    </Container>
  );
};

export default TranslationScreen; 