import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    allowedHosts: ['localhost', '127.0.0.1'],
    cors: false,
    proxy: { '/api/collection': { target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false } },
  },
  preview: { host: '127.0.0.1', strictPort: true, allowedHosts: ['localhost', '127.0.0.1'], cors: false },
});
