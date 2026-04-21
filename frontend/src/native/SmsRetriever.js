import { registerPlugin } from '@capacitor/core';

/**
 * In-house JS bridge to the Android-only SmsRetrieverPlugin (Kotlin).
 *
 * On non-Android platforms (iOS, web) the proxy returned by registerPlugin
 * forwards calls to a no-op web fallback that resolves harmlessly.
 *
 * API:
 *   await SmsRetriever.start()                          → starts the 5-min listener
 *   await SmsRetriever.stop()                           → cancels the listener
 *   SmsRetriever.addListener('smsReceived', ({message}) => ...)
 *   SmsRetriever.addListener('smsTimeout', () => ...)
 */
const SmsRetriever = registerPlugin('SmsRetriever', {
  web: {
    async start() {
      return { started: false, reason: 'web-noop' };
    },
    async stop() {
      return { stopped: false, reason: 'web-noop' };
    },
  },
});

export default SmsRetriever;
export { SmsRetriever };
