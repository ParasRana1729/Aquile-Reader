import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Bundled reader fonts for Linux and cross-platform native parity (SIL OFL-1.1)
import '@fontsource/inter/400.css';
import '@fontsource/inter/400-italic.css';
import '@fontsource/inter/700.css';
import '@fontsource/inter/700-italic.css';

import '@fontsource/merriweather/400.css';
import '@fontsource/merriweather/400-italic.css';
import '@fontsource/merriweather/700.css';
import '@fontsource/merriweather/700-italic.css';

import '@fontsource/literata/400.css';
import '@fontsource/literata/400-italic.css';
import '@fontsource/literata/700.css';
import '@fontsource/literata/700-italic.css';

import '@fontsource/gelasio/400.css';
import '@fontsource/gelasio/400-italic.css';
import '@fontsource/gelasio/700.css';
import '@fontsource/gelasio/700-italic.css';

import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/400-italic.css';
import '@fontsource/jetbrains-mono/700.css';
import '@fontsource/jetbrains-mono/700-italic.css';

import '@fontsource/opendyslexic/400.css';
import '@fontsource/opendyslexic/400-italic.css';
import '@fontsource/opendyslexic/700.css';
import '@fontsource/opendyslexic/700-italic.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
