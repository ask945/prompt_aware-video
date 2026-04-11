import { Clock3, Film, HardDrive, Layers3 } from 'lucide-react';

function formatDuration(seconds) {
  const mins = Math.floor(Number(seconds || 0) / 60);
  const secs = Math.floor(Number(seconds || 0) % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }

  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export default function VideoLibrary({ videos, selectedVideoId, onSelect }) {
  return (
    <section className="bg-card border border-border rounded-2xl p-5 animate-fade-in">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-text">Your uploaded videos</h3>
          <p className="text-sm text-text-secondary mt-1">
            Pick any previous upload and use it immediately for analysis.
          </p>
        </div>
        <div className="rounded-full bg-primary-light px-3 py-1 text-xs font-medium text-primary-dark">
          {videos.length} saved
        </div>
      </div>

      {videos.length === 0 ? (
        <div className="mt-4 rounded-xl border border-dashed border-border bg-bg px-4 py-6 text-sm text-text-secondary">
          No videos yet. Upload your first one and it will appear here for reuse.
        </div>
      ) : (
        <div className="mt-4 grid gap-3">
          {videos.map((video) => {
            const isSelected = video.video_id === selectedVideoId;

            return (
              <button
                key={video.video_id}
                type="button"
                onClick={() => onSelect(video)}
                className={`w-full rounded-xl border px-4 py-4 text-left transition ${
                  isSelected
                    ? 'border-primary bg-primary-light/50 shadow-sm'
                    : 'border-border bg-white hover:border-primary/50 hover:bg-primary-light/20'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Film className="w-4 h-4 text-primary-dark flex-shrink-0" />
                      <p className="truncate text-sm font-semibold text-text">{video.filename}</p>
                    </div>
                    <p className="mt-2 text-xs text-text-secondary">
                      Uploaded {new Date(video.uploaded_at).toLocaleString()}
                    </p>
                  </div>
                  {isSelected ? (
                    <span className="rounded-full bg-primary px-2.5 py-1 text-xs font-medium text-white">
                      Selected
                    </span>
                  ) : null}
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-text-secondary">
                  <span className="inline-flex items-center gap-1.5">
                    <Clock3 className="w-3.5 h-3.5" />
                    {formatDuration(video.duration)}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <HardDrive className="w-3.5 h-3.5" />
                    {formatBytes(video.size)}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Layers3 className="w-3.5 h-3.5" />
                    {video.total_frames.toLocaleString()} frames
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
