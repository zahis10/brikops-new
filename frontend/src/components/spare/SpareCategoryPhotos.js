import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Camera, Loader2, Trash2, X } from 'lucide-react';
import { toast } from 'sonner';
import sparePhotoService from '../../services/sparePhotoService';
import { compressImage } from '../../utils/imageCompress';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../ui/alert-dialog';
const dateCaption = value => {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ''
    : `${date.getDate()}.${date.getMonth() + 1}.${date.getFullYear()}`;
};
const SpareCategoryPhotos = ({
  unitId, category, photos = [], canWrite, canDeleteAny, currentUserId, onChanged,
}) => {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [lightboxPhoto, setLightboxPhoto] = useState(null);
  const [deletePhoto, setDeletePhoto] = useState(null);
  useEffect(() => {
    if (!lightboxPhoto) return undefined;
    const close = event => event.key === 'Escape' && setLightboxPhoto(null);
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [lightboxPhoto]);
  const handleUpload = async event => {
    const file = event.target.files?.[0];
    if (!file) {
      event.target.value = '';
      return;
    }
    try {
      setUploading(true);
      const compressed = await compressImage(file);
      await sparePhotoService.upload(unitId, category, compressed);
      toast.success('התמונה נשמרה');
      await onChanged?.();
    } catch (err) {
      if (err?.code === 'UNSUPPORTED_FORMAT') {
        toast.error('פורמט התמונה לא נתמך במכשיר זה');
      } else {
        toast.error(err.response?.data?.detail || 'שגיאה בהעלאת התמונה');
      }
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };
  const handleDelete = async event => {
    event.preventDefault();
    if (!deletePhoto || deleting) return;
    try {
      setDeleting(true);
      await sparePhotoService.remove(unitId, deletePhoto.id);
      toast.success('התמונה נמחקה');
      await onChanged?.();
      setDeletePhoto(null);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'שגיאה במחיקת התמונה');
    } finally {
      setDeleting(false);
    }
  };
  if (photos.length === 0 && !canWrite) return null;
  const canDelete = photo => canWrite && (canDeleteAny || photo.uploaded_by === currentUserId);
  return (
    <>
      <div className="flex items-center gap-2 flex-wrap mt-1 mb-1.5" dir="rtl">
        {photos.map(photo => (
          <button key={photo.id} type="button"
            onClick={() => setLightboxPhoto(photo)}
            className="w-11 h-11 rounded-lg overflow-hidden border border-slate-200"
            aria-label={`תיעוד ריצוף — ${category}`}
          >
            <img src={photo.url} alt={`תיעוד ריצוף — ${category}`} className="w-full h-full object-cover" />
          </button>
        ))}
        {canWrite && photos.length < 3 && (
          <>
            <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleUpload} />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="min-h-[36px] flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-amber-600 disabled:opacity-50"
            >
              {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Camera className="w-3.5 h-3.5" />}
              {uploading ? 'מעלה...' : photos.length === 0 ? 'צלם ריצוף' : 'הוסף תמונה'}
            </button>
          </>
        )}
        {photos.length === 3 && <span className="text-xs text-slate-400">3/3</span>}
      </div>
      {lightboxPhoto && createPortal(
        <div
          role="dialog"
          aria-label={`תיעוד ריצוף — ${category}`}
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4"
          tabIndex="-1"
          autoFocus
          onClick={() => setLightboxPhoto(null)}
        >
          <button type="button" className="absolute top-4 end-4 text-white p-2" onClick={() => setLightboxPhoto(null)} aria-label="סגור">
            <X className="w-6 h-6" />
          </button>
          <div className="max-w-full text-center">
            <img src={lightboxPhoto.url} alt={`תיעוד ריצוף — ${category}`} className="max-h-[85vh] max-w-full object-contain" />
            <p className="text-sm text-white mt-2">
              {lightboxPhoto.uploaded_by_name} · {dateCaption(lightboxPhoto.uploaded_at)}
            </p>
            {canDelete(lightboxPhoto) && (
              <button type="button"
                className="min-h-[44px] border border-red-400 text-red-200 px-4 rounded-lg mt-3 inline-flex items-center gap-2"
                onClick={event => {
                  event.stopPropagation();
                  setLightboxPhoto(null);
                  setDeletePhoto(lightboxPhoto);
                }}
              >
                <Trash2 className="w-4 h-4" />
                מחק תמונה
              </button>
            )}
          </div>
        </div>,
        document.body
      )}
      <AlertDialog open={!!deletePhoto} onOpenChange={open => !open && !deleting && setDeletePhoto(null)}>
        <AlertDialogContent dir="rtl">
          <AlertDialogHeader>
            <AlertDialogTitle>למחוק את התמונה?</AlertDialogTitle>
            <AlertDialogDescription>התמונה תימחק לצמיתות</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>ביטול</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={deleting} className="bg-red-600 hover:bg-red-700">
              {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'מחק'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
export default SpareCategoryPhotos;
