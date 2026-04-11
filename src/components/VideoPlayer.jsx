import { useRef, useState, useEffect } from 'react';
import { Play, Pause, Volume2, VolumeX, Maximize } from 'lucide-react';

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default function VideoPlayer({ videoFile, remoteUrl, detections = [], seekTo, duration = 60 }) {
  const videoRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(duration);
  const [muted, setMuted] = useState(false);
  const [videoUrl, setVideoUrl] = useState(null);

  useEffect(() => {
    if (videoFile) {
      const url = URL.createObjectURL(videoFile);
      setVideoUrl(url);
      return () => URL.revokeObjectURL(url);
    }
    // Fall back to Cloudinary URL for library videos
    setVideoUrl(remoteUrl || null);
  }, [videoFile, remoteUrl]);

  useEffect(() => {
    if (seekTo?.time !== null && seekTo?.time !== undefined && videoRef.current) {
      videoRef.current.currentTime = seekTo.time;
      setCurrentTime(seekTo.time);
    }
  }, [seekTo?.key]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (playing) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setPlaying(!playing);
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setVideoDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percent = x / rect.width;
    const time = percent * videoDuration;
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleFullscreen = () => {
    if (videoRef.current?.requestFullscreen) {
      videoRef.current.requestFullscreen();
    }
  };

  const progress = videoDuration > 0 ? (currentTime / videoDuration) * 100 : 0;

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="relative bg-black aspect-video">
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            className="w-full h-full object-contain"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onEnded={() => setPlaying(false)}
            muted={muted}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-white/40">
            <Play className="w-12 h-12" />
          </div>
        )}
      </div>

      <div className="p-3 space-y-2">
        <div
          className="relative h-1.5 bg-bg rounded-full cursor-pointer group"
          onClick={handleSeek}
        >
          <div
            className="absolute top-0 left-0 h-full bg-primary rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
          {detections.map((det) => {
            const pos = videoDuration > 0 ? (det.timestamp / videoDuration) * 100 : 0;
            return (
              <div
                key={det.id}
                className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 bg-primary rounded-full border-2 border-white shadow-sm hover:scale-150 transition-transform z-10"
                style={{ left: `${pos}%`, marginLeft: '-5px' }}
                title={`${det.label} at ${formatTime(det.timestamp)}`}
              />
            );
          })}
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={togglePlay}
              className="p-1.5 hover:bg-bg rounded-md transition-colors text-text"
              disabled={!videoUrl}
            >
              {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <button
              onClick={() => setMuted(!muted)}
              className="p-1.5 hover:bg-bg rounded-md transition-colors text-text-secondary"
            >
              {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
            </button>
            <span className="text-xs text-text-secondary tabular-nums">
              {formatTime(currentTime)} / {formatTime(videoDuration)}
            </span>
          </div>
          <button
            onClick={handleFullscreen}
            className="p-1.5 hover:bg-bg rounded-md transition-colors text-text-secondary"
            disabled={!videoUrl}
          >
            <Maximize className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
