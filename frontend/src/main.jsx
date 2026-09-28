import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { AuthProvider } from './AuthContext.jsx'
import App from './App.jsx'
import './index.css'
import './skeleton.css'
import './model-lab-overrides.css'
import './model-lab-prediction-fix.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HashRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </HashRouter>
  </React.StrictMode>,
)
