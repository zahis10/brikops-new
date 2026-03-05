import React, { useRef, useEffect, useState, useCallback } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Camera, X, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';

const ERROR_MESSAGES = {
  NotAllowedError: 'לא ניתן לגשת למצלמה — יש לאשר הרשאה',
  NotReadableError: 'המצלמה בשימוש אפליקציה אחרת',
  NotFoundError: 'לא נמצאה מצלמה במכשיר',
  OverconstrainedError: 'לא ניתן לבחור מצלמה אחורית — מנסה מצלמה רגילה',
};

const CameraModal = ({ isOpen, onCapture, onClose }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(null);
  const [errorCode, setErrorCode] = useState(null);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setReady(false);
  }, []);

  const attachStream = useCallback((stream) => {
    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      videoRef.current.onloadedmetadata = () => {
        videoRef.current.play().then(() => setReady(true)).catch(() => setReady(true));
      };
    }
  }, []);

  const startCamera = useCallback(async () => {
    setError(null);
    setErrorCode(null);
    setReady(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      attachStream(stream);
    } catch (err) {
      console.error(`[CameraModal] err.name=${err.name} err.message=${err.message}`);

      if (err.name === 'OverconstrainedError') {
        try {
          const fallbackStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
          attachStream(fallbackStream);
          return;
        } catch (fallbackErr) {
          console.error(`[CameraModal] fallback err.name=${fallbackErr.name} err.message=${fallbackErr.message}`);
          const msg = ERROR_MESSAGES[fallbackErr.name] || 'שגיאה בגישה למצלמה';
          setError(msg);
          setErrorCode(fallbackErr.name);
          toast.error(msg);
          return;
        }
      }

      const msg = ERROR_MESSAGES[err.name] || 'שגיאה בגישה למצלמה';
      setError(msg);
      setErrorCode(err.name);
      toast.error(msg);
    }
  }, [attachStream]);

  useEffect(() => {
    if (isOpen) {
      startCamera();
    }
    return () => stopStream();
  }, [isOpen, startCamera, stopStream]);

  const handleCapture = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          stopStream();
          onCapture(blob);
        }
      },
      'image/jpeg',
      0.8
    );
  }, [onCapture, stopStream]);

  const handleClose = useCallback(() => {
    stopStream();
    onClose();
  }, [stopStream, onClose]);

  if (!isOpen) return null;

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => { if (!open) handleClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/80 z-[9998]" />
        <Dialog.Content
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center"
          onPointerDownOutside={(e) => e.preventDefault()}
        >
          <div className="relative w-full h-full flex flex-col bg-black">
            <div className="absolute top-4 right-4 z-10">
              <button
                onClick={handleClose}
                className="bg-black/50 text-white rounded-full p-2 hover:bg-black/70 transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="flex-1 flex items-center justify-center overflow-hidden">
              {error ? (
                <div className="text-center p-6 max-w-sm">
                  <Camera className="w-16 h-16 text-slate-400 mx-auto mb-4" />
                  <p className="text-white text-lg mb-2">{error}</p>
                  {errorCode && (
                    <p className="text-slate-500 text-xs font-mono mb-4">camera_error={errorCode}</p>
                  )}

                  <div className="text-slate-400 text-sm text-right space-y-2 mb-6 bg-white/5 rounded-lg p-4" dir="rtl">
                    <p className="text-slate-300 text-xs font-medium mb-2">איך לאפשר מצלמה:</p>
                    <p className="text-xs">Safari: aA → Website Settings → Camera → Allow</p>
                    <p className="text-xs">iOS: Settings → Safari → Camera → Allow/Ask</p>
                    <p className="text-xs text-slate-500">Reset: Settings → Safari → Advanced → Website Data → delete brikops</p>
                  </div>

                  <button
                    onClick={startCamera}
                    className="flex items-center gap-2 mx-auto px-4 py-2 bg-amber-500 text-white rounded-lg"
                  >
                    <RotateCcw className="w-4 h-4" />
                    נסה שוב
                  </button>
                </div>
              ) : (
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-contain"
                />
              )}
            </div>

            {!error && (
              <div className="absolute bottom-8 left-0 right-0 flex justify-center">
                <button
                  onClick={handleCapture}
                  disabled={!ready}
                  className={`w-20 h-20 rounded-full border-4 border-white flex items-center justify-center transition-all ${
                    ready
                      ? 'bg-white/20 hover:bg-white/40 active:scale-90'
                      : 'bg-white/5 opacity-50'
                  }`}
                >
                  <div className={`w-16 h-16 rounded-full ${ready ? 'bg-white' : 'bg-white/30'}`} />
                </button>
              </div>
            )}

            <canvas ref={canvasRef} className="hidden" />
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
};

export default CameraModal;
