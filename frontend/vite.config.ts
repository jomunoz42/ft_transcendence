import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { readFileSync } from 'node:fs'

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000'
const certificateFile = process.env.VITE_DEV_TLS_CERT
const privateKeyFile = process.env.VITE_DEV_TLS_KEY
const https = certificateFile && privateKeyFile
  ? { cert: readFileSync(certificateFile), key: readFileSync(privateKeyFile) }
  : undefined

export default defineConfig({
  plugins: [react()],
  server: {
    https,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: apiProxyTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
