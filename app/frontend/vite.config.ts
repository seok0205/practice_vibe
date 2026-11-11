// =============================================================================
// [파일 목적]
// Vite 프론트엔드 번들러 설정 파일입니다.
// 로컬 개발 시 `/api` 요청을 FastAPI 백엔드(`http://localhost:8000`)로 프록시하며,
// 프로덕션 빌드 결과물은 `dist/`에 생성됩니다.
// =============================================================================
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});

