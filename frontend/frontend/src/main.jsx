import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/landing.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/dashboard.css';
import './styles/extras.css';
import './styles/pages.css';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>);
