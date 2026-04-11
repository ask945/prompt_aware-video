import { Eye, Clock, Target } from 'lucide-react';

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function confidenceColor(confidence) {
  if (confidence >= 0.9) return 'text-green-600 bg-green-50';
  if (confidence >= 0.7) return 'text-yellow-600 bg-yellow-50';
  return 'text-orange-600 bg-orange-50';
}

export default function DetectionCard({ detection, index, onClick }) {
  const conf = Math.round(detection.confidence * 100);

  return (
    <button
      onClick={() => onClick(detection.timestamp)}
      className="animate-slide-up bg-card border border-border rounded-xl p-4 text-left hover:border-primary/50 hover:shadow-md transition-all duration-200 group w-full"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <div className="flex items-start gap-3">
        <div className="w-16 h-16 bg-gradient-to-br from-primary-light to-bg rounded-lg flex items-center justify-center flex-shrink-0 group-hover:from-primary-light group-hover:to-primary-light/60 transition-colors">
          <Eye className="w-6 h-6 text-primary-dark" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold text-text truncate">{detection.label}</h4>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${confidenceColor(detection.confidence)}`}>
              {conf}%
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-xs text-text-secondary">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTime(detection.timestamp)}
            </span>
            <span className="flex items-center gap-1">
              <Target className="w-3 h-3" />
              Frame {detection.frame}
            </span>
          </div>
        </div>
      </div>
    </button>
  );
}
