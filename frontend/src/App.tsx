import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import HomePage from './components/HomePage';
import ResultPage from './components/ResultPage';
import TranslationScreen from './components/TranslationScreen';

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/translation/:taskId" element={<TranslationScreen />} />
        <Route path="/result/:taskId" element={<ResultPage />} />
      </Routes>
    </Router>
  );
};

export default App; 