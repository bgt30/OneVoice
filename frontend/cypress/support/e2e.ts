// ***********************************************************
// This example support/e2e.ts is processed and
// loaded automatically before your test files.
//
// This is a great place to put global configuration and
// behavior that modifies Cypress.
//
// You can change the location of this file or turn off
// automatically serving support files with the
// 'supportFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/configuration
// ***********************************************************

// Import commands.js using ES2015 syntax:
import './commands'
import 'cypress-file-upload';

// 커스텀 명령어 추가
declare global {
  namespace Cypress {
    interface Chainable {
      // 여기에 커스텀 명령어 타입 정의 추가
    }
  }
}

// 기본 동작 설정
beforeEach(() => {
  // 실패한 요청에 대한 로그 비활성화
  Cypress.on('uncaught:exception', (err, runnable) => {
    return false;
  });
});