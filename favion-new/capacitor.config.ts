import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.brikops.app',
  appName: 'BrikOps',
  webDir: 'dist',
  bundledWebRuntime: false,
  // Splash + icon config consumed by @capacitor/assets / cordova-res
  backgroundColor: '#323A4EFF',
  plugins: {
    SplashScreen: {
      launchShowDuration: 1500,
      backgroundColor: '#323A4E',
      androidScaleType: 'CENTER_CROP',
      showSpinner: false,
    },
  },
};

export default config;
