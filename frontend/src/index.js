import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { Capacitor } from '@capacitor/core';
import { SocialLogin } from '@capgo/capacitor-social-login';

if (Capacitor.isNativePlatform()) {
  SocialLogin.initialize({
    google: {
      webClientId: '394294810491-u5q1t9vabqpumvuue42241sajbghchvh.apps.googleusercontent.com',
      iOSClientId: '394294810491-jdlacmban1h476g531u3s1huslmhl62h.apps.googleusercontent.com',
      mode: 'online',
    },
  }).catch((err) => console.error('[SocialLogin] init failed:', err));
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
