import React from 'react'
import ReactDOM from 'react-dom/client'
// Import OpenBridge CSS variables FIRST
import "@oicl/openbridge-webcomponents/src/palettes/variables.css";
import App from './App.js'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
