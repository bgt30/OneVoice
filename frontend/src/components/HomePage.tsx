import React, { useState } from 'react';
import {
  Box,
  Button,
  Container,
  TextField,
  Typography,
  Paper,
  Alert,
  CircularProgress,
} from '@mui/material';
import { CloudUpload } from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import { uploadVideo, processYouTube } from '../api/client';

const Input = styled('input')({
  display: 'none',
});

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.type !== 'video/mp4') {
        setError('MP4 파일만 업로드 가능합니다.');
        return;
      }
      setFile(selectedFile);
      setError('');
      setYoutubeUrl('');
    }
  };

  const handleYoutubeUrlChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setYoutubeUrl(event.target.value);
    setFile(null);
    setError('');
  };

  const handleFileUpload = async (file: File) => {
    try {
      setIsLoading(true);
      const formData = new FormData();
      formData.append('file', file);
      const response = await uploadVideo(formData);
      navigate(`/translation/${response.task_id}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleYoutubeSubmit = async (url: string) => {
    try {
      setIsLoading(true);
      const response = await processYouTube(url);
      navigate(`/translation/${response.task_id}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async () => {
    try {
      setError('');
      if (!file && !youtubeUrl) {
        setError('파일을 업로드하거나 YouTube URL을 입력해주세요.');
        return;
      }

      if (file) {
        await handleFileUpload(file);
      } else if (youtubeUrl) {
        await handleYoutubeSubmit(youtubeUrl);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류가 발생했습니다.';
      setError(errorMessage);
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ mt: 8, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          OneVoice 비디오 더빙 서비스
        </Typography>
        <Typography variant="subtitle1" align="center" color="text.secondary" paragraph>
          영어 동영상을 한국어로 더빙하세요. MP4 파일을 업로드하거나 YouTube 링크를 입력하세요.
          (최대 10분)
        </Typography>
      </Box>

      <Paper elevation={3} sx={{ p: 4, mb: 4 }}>
        <Box sx={{ mb: 3 }}>
          <label htmlFor="video-file">
            <Input
              accept="video/mp4"
              id="video-file"
              type="file"
              onChange={handleFileChange}
              disabled={isLoading}
            />
            <Button
              variant="contained"
              component="span"
              startIcon={<CloudUpload />}
              fullWidth
              sx={{ mb: 2 }}
              disabled={isLoading}
            >
              MP4 파일 업로드
            </Button>
          </label>
          {file && (
            <Typography variant="body2" color="text.secondary" align="center">
              선택된 파일: {file.name}
            </Typography>
          )}
        </Box>

        <Typography variant="body1" align="center" sx={{ my: 2 }}>
          또는
        </Typography>

        <TextField
          fullWidth
          label="YouTube URL"
          variant="outlined"
          value={youtubeUrl}
          onChange={handleYoutubeUrlChange}
          placeholder="https://www.youtube.com/watch?v=..."
          sx={{ mb: 3 }}
          disabled={isLoading}
        />

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        <Button
          variant="contained"
          color="primary"
          fullWidth
          onClick={handleSubmit}
          disabled={(!file && !youtubeUrl) || isLoading}
        >
          {isLoading ? (
            <>
              <CircularProgress size={24} sx={{ mr: 1 }} />
              처리 중...
            </>
          ) : (
            '변환 시작'
          )}
        </Button>
      </Paper>
    </Container>
  );
};

export default HomePage; 