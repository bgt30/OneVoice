describe('OneVoice E2E Tests', () => {
  beforeEach(() => {
    cy.visit('http://localhost');
  });

  it('홈페이지가 정상적으로 로드되는지 확인', () => {
    cy.contains('OneVoice 비디오 더빙 서비스');
    cy.contains('MP4 파일 업로드');
    cy.contains('YouTube URL');
  });

  it('MP4 파일 업로드 테스트', () => {
    cy.get('input[type="file"]').attachFile('test.mp4');
    cy.contains('선택된 파일: test.mp4');
    cy.contains('변환 시작').click();
    cy.url().should('include', '/translation/');
  });

  it('YouTube URL 입력 테스트', () => {
    cy.get('input[placeholder*="YouTube"]').type('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
    cy.contains('변환 시작').click();
    cy.url().should('include', '/translation/');
  });

  it('변환 진행 상태 확인', () => {
    cy.visit('http://localhost/translation/test-task-id');
    cy.contains('비디오 변환 중');
    cy.get('.MuiLinearProgress-root').should('exist');
    cy.contains('음성 인식');
    cy.contains('번역');
    cy.contains('음성 합성');
  });

  it('결과 페이지 확인', () => {
    cy.visit('http://localhost/result/test-task-id');
    cy.contains('변환 완료!');
    cy.get('video').should('exist');
    cy.contains('비디오 다운로드');
    cy.contains('새로운 비디오 변환하기');
    cy.contains('피드백');
  });

  it('피드백 제출 테스트', () => {
    cy.visit('http://localhost/result/test-task-id');
    cy.get('.MuiRating-root').click(4);
    cy.get('textarea').type('테스트 피드백 메시지');
    cy.contains('피드백 보내기').click();
    cy.contains('피드백을 보내주셔서 감사합니다!');
  });
}); 