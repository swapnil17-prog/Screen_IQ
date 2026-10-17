import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './hooks/useTheme' // applies the saved theme before first paint
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
