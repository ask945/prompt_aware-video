import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, Film, X, Play } from 'lucide-react';
import toast from 'react-hot-toast';

const ACCEPTED_FORMATS = {
  'video/mp4': ['.mp4'],
  'video/x-msvideo': ['.avi'],
  'video/quicktime': ['.mov'],
  'video/webm': ['.webm'],
};

const MAX_SIZE = 100 * 1024 * 1024;

function formatSize(bytes) {
  if (!bytes) return '0 KB';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDuration(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default function UploadZone({ videoFile, videoInfo, uploading, onUpload, onRemove }) {
  const [previewOpen, setPreviewOpen] = useState(false);

  // Resolve a playable video source — prefer local File (instant, no network)
  // and fall back to the Cloudinary URL for library videos.
  const videoSrc = useMemo(() => {
    if (videoFile) {
      return URL.createObjectURL(videoFile);
    }
    return videoInfo?.url || null;
  }, [videoFile, videoInfo?.url]);

  useEffect(() => {
    // Revoke the blob URL when the component unmounts or source changes
    return () => {
      if (videoFile && videoSrc) {
        URL.revokeObjectURL(videoSrc);
      }
    };
  }, [videoFile, videoSrc]);

  // Close the preview modal on Escape
  useEffect(() => {
    if (!previewOpen) return;
    const handler = (e) => {
      if (e.key === 'Escape') setPreviewOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [previewOpen]);

  const onDrop = useCallback((acceptedFiles, rejectedFiles) => {
    if (rejectedFiles.length > 0) {
      const error = rejectedFiles[0].errors[0];
      if (error.code === 'file-too-large') {
        toast.error('File too large. Maximum size is 100MB.');
      } else if (error.code === 'file-invalid-type') {
        toast.error('Unsupported format. Please use MP4, AVI, MOV, or WebM.');
      } else {
        toast.error('Invalid file. Please try again.');
      }
      return;
    }

    if (acceptedFiles.length > 0) {
      onUpload(acceptedFiles[0]);
    }
  }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FORMATS,
    maxSize: MAX_SIZE,
    multiple: false,
    disabled: uploading,
  });

  if (videoInfo) {
    return (
      <>
        <div className="animate-fade-in bg-card border border-border rounded-xl p-4 flex items-center gap-4">
          {/* Thumbnail on the left — click to open preview */}
          <button
            type="button"
            onClick={() => setPreviewOpen(true)}
            className="relative w-24 h-16 rounded-lg overflow-hidden flex-shrink-0 bg-black group focus:outline-none focus:ring-2 focus:ring-primary"
            title="Click to preview"
          >
            {videoSrc ? (
              <video
                src={videoSrc}
                className="w-full h-full object-cover pointer-events-none"
                preload="metadata"
                muted
                playsInline
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-primary-light">
                <Film className="w-6 h-6 text-primary-dark" />
              </div>
            )}
            {/* Play icon overlay */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-80 group-hover:opacity-100 transition-opacity">
              <div className="w-8 h-8 rounded-full bg-white/90 flex items-center justify-center">
                <Play className="w-4 h-4 text-primary-dark ml-0.5" fill="currentColor" />
              </div>
            </div>
          </button>

          {/* Name + metadata on the right */}
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text truncate">{videoInfo.filename}</p>
            <div className="flex items-center gap-3 mt-1 text-xs text-text-secondary">
              <span>{formatSize(videoInfo.size || videoFile?.size || 0)}</span>
              <span>|</span>
              <span>{formatDuration(videoInfo.duration || 0)}</span>
              <span>|</span>
              <span>{(videoInfo.total_frames || 0).toLocaleString()} frames</span>
            </div>
          </div>

          <button
            onClick={onRemove}
            className="p-2 text-text-secondary hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
            title="Remove video"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Preview modal */}
        {previewOpen && (
          <VideoPreviewModal
            src={videoSrc}
            filename={videoInfo.filename}
            onClose={() => setPreviewOpen(false)}
          />
        )}
      </>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200
        ${isDragActive
          ? 'border-primary bg-primary-light/50 scale-[1.01]'
          : 'border-border hover:border-primary/50 hover:bg-primary-light/20'
        }
        ${uploading ? 'opacity-60 pointer-events-none' : ''}
      `}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-3">
        {uploading ? (
          <>
            <div className="w-12 h-12 rounded-full bg-primary-light flex items-center justify-center animate-pulse">
              <Film className="w-6 h-6 text-primary-dark" />
            </div>
            <p className="text-sm font-medium text-text">Uploading video...</p>
          </>
        ) : (
          <>
            <div className="w-12 h-12 rounded-full bg-primary-light flex items-center justify-center">
              <Upload className="w-6 h-6 text-primary-dark" />
            </div>
            <div>
              <p className="text-sm font-medium text-text">
                {isDragActive ? 'Drop your video here' : 'Drag & drop your video here'}
              </p>
              <p className="text-xs text-text-secondary mt-1">
                or click to browse | MP4, AVI, MOV, WebM | Max 100MB
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}


function VideoPreviewModal({ src, filename, onClose }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm animate-fade-in p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl bg-card rounded-2xl shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <p className="text-sm font-medium text-text truncate pr-4">{filename}</p>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-secondary hover:text-text hover:bg-bg transition-colors flex-shrink-0"
            title="Close (Esc)"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="bg-black">
          {src ? (
            <video
              src={src}
              className="w-full max-h-[70vh] object-contain"
              controls
              autoPlay
              playsInline
            />
          ) : (
            <div className="aspect-video flex items-center justify-center text-white/60 text-sm">
              Video source unavailable
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
