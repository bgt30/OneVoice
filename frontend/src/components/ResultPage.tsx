import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Button,
  Rating,
  TextField,
  Alert,
  CircularProgress,
} from '@mui/material';
import { Download, Home } from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { getTaskStatus, downloadVideo, submitFeedback } from '../api/client';

// API 기본 URL 가져오기
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const ResultPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [rating, setRating] = useState<number | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [status, setStatus] = useState<string>('pending');
  const [progress, setProgress] = useState<number>(0);
  const [stage, setStage] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;
    
    // 작업 상태를 주기적으로 확인
    const checkStatus = async () => {
      try {
        const response = await getTaskStatus(taskId);
        setStatus(response.status);
        setProgress(response.progress || 0);
        setStage(response.stage || null);
        
        if (response.status === 'completed') {
          // 완료된 경우 다운로드 URL 설정
          setVideoUrl(`${API_BASE_URL}/api/process/download/${taskId}`);
          setIsLoading(false);
        } else if (response.status === 'failed') {
          setError(response.error || '처리 중 오류가 발생했습니다.');
          setIsLoading(false);
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '상태 확인 중 오류가 발생했습니다.';
        setError(errorMessage);
        setIsLoading(false);
      }
    };
    
    // 초기 상태 확인
    checkStatus();
    
    // 완료되지 않은 경우 3초마다 상태 확인
    const intervalId = setInterval(() => {
      if (status !== 'completed' && status !== 'failed') {
        checkStatus();
      } else {
        clearInterval(intervalId);
      }
    }, 3000);
    
    return () => clearInterval(intervalId);
  }, [taskId, status]);

  const handleDownload = async () => {
    if (!taskId) return;
    
    try {
      setIsDownloading(true);
      const blob = await downloadVideo(taskId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dubbed_video_${taskId}.mp4`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '다운로드 중 오류가 발생했습니다.';
      setError(errorMessage);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleReprocess = () => {
    navigate('/');
  };

  const handleFeedbackSubmit = async () => {
    if (!taskId || rating === null) return;
    
    try {
      await submitFeedback(taskId, rating);
      alert('피드백을 보내주셔서 감사합니다!');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '피드백 제출 중 오류가 발생했습니다.';
      setError(errorMessage);
    }
  };

  // 로딩 중이거나 처리 중인 경우 진행 상태 표시
  if (isLoading || status === 'pending' || status === 'processing') {
    return (
      <Container maxWidth="md">
        <Box sx={{ mt: 8, mb: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom align="center">
            {status === 'pending' ? '처리 대기 중...' : '처리 중...'}
          </Typography>
        </Box>
        
        <Paper elevation={3} sx={{ p: 4, mb: 4 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
            <CircularProgress variant="determinate" value={progress} size={80} />
            <Typography variant="h6">
              {progress}% 완료
            </Typography>
            {stage && (
              <Typography variant="body1">
                현재 단계: {stage === 'stt' ? '음성 인식' : stage === 'translation' ? '번역' : '음성 합성'}
              </Typography>
            )}
          </Box>
        </Paper>
      </Container>
    );
  }

  return (
    <Container maxWidth="md">
      <Box sx={{ mt: 8, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          변환 완료!
        </Typography>
      </Box>

      <Paper elevation={3} sx={{ p: 4, mb: 4 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        {videoUrl && (
          <Box sx={{ mb: 4 }}>
            <video
              controls
              width="100%"
              src={videoUrl}
              style={{ borderRadius: '4px' }}
            />
          </Box>
        )}

        <Box sx={{ display: 'flex', gap: 2, mb: 4 }}>
          <Button
            variant="contained"
            color="primary"
            fullWidth
            startIcon={<Download />}
            onClick={handleDownload}
            disabled={isDownloading}
          >
            {isDownloading ? '다운로드 중...' : '비디오 다운로드'}
          </Button>

          <Button
            variant="outlined"
            color="primary"
            fullWidth
            startIcon={<Home />}
            onClick={handleReprocess}
          >
            새로운 비디오 변환하기
          </Button>
        </Box>

        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" gutterBottom>
            피드백
          </Typography>
          <Box sx={{ mb: 2 }}>
            <Typography component="legend">변환 품질은 어떠셨나요?</Typography>
            <Rating
              value={rating}
              onChange={(_, newValue) => setRating(newValue)}
              size="large"
            />
          </Box>
          <TextField
            fullWidth
            multiline
            rows={4}
            variant="outlined"
            placeholder="추가 의견이 있으시다면 자유롭게 작성해주세요."
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            sx={{ mb: 2 }}
          />
          <Button
            variant="contained"
            color="primary"
            onClick={handleFeedbackSubmit}
            disabled={rating === null}
          >
            피드백 보내기
          </Button>
        </Box>
      </Paper>
    </Container>
  );
};

export default ResultPage; 