import { Eye, Clock, Target, Users } from 'lucide-react';

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

  // Only show text content when this is actually an OCR result
  const isOcr = detection.object_class === 'text' && detection.text_content;
  const isClipMatch = detection.object_class === 'clip_match';

  let title;
  if (isOcr) {
    title = 'Text Found';
  } else if (isClipMatch) {
    title = 'Scene Match';
  } else if (detection.color && detection.label) {
    title = `${detection.color} ${detection.label}`;
  } else {
    title = detection.label;
  }

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
            <h4 className="text-sm font-semibold text-text truncate">
              {title}
            </h4>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${confidenceColor(detection.confidence)}`}>
              {conf}%
            </span>
          </div>
          {isOcr && (
            <p className="mt-1.5 text-xs text-text bg-bg rounded-lg px-3 py-2 font-mono leading-relaxed line-clamp-3">
              {detection.text_content}
            </p>
          )}
          <div className="flex items-center gap-3 mt-1.5 text-xs text-text-secondary flex-wrap">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTime(detection.timestamp)}
            </span>
            <span className="flex items-center gap-1">
              <Target className="w-3 h-3" />
              Frame {detection.frame_number}
            </span>
            {typeof detection.count === 'number' && detection.count > 0 && (
              <span className="flex items-center gap-1 text-primary-dark font-semibold">
                <Users className="w-3 h-3" />
                {detection.count} {detection.label || 'object'}{detection.count !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
}
