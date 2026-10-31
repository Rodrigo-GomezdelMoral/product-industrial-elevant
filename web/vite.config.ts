import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const roles = ['Quote.Estimator', 'Quote.Manager'].map((val) => ({ typ: 'roles', val }))
const local = {
  target: 'http://127.0.0.1:8000',
  headers: { 'x-ms-client-principal': btoa(JSON.stringify({ claims: roles })), 'x-ms-client-principal-name': 'Local estimator' },
}

export default defineConfig({
  base: './',
  plugins: [react()],
  server: { proxy: { '/api': local } },
})
