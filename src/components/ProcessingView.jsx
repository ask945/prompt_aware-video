import { FileVideo, X, Cpu, Layers, Clock, BarChart3 } from 'lucide-react';

export default function ProcessingView({ query, videoInfo, progress, stats, onCancel }) {
  return (
    <div className="animate-fade-in space-y-6">
      <div className="bg-card border border-border rounded-xl p-5">
        <div className="flex items-center gap-4 mb-5">
          <div className="w-12 h-12 bg-primary-light rounded-lg flex items-center justify-center flex-shrink-0">
            <FileVideo className="w-6 h-6 text-primary-dark" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text truncate">{videoInfo?.filename}</p>
            <p className="text-xs text-text-secondary mt-0.5 truncate">"{query}"</p>
          </div>
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors flex items-center gap-1.5"
          >
            <X className="w-3.5 h-3.5" />
            Cancel
          </button>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-secondary font-medium">Analyzing video...</span>
            <span className="text-primary-dark font-semibold">{progress}%</span>
          </div>
          <div className="h-2.5 bg-bg rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary to-primary-dark rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 animate-slide-up">
          <StatCard
            icon={<BarChart3 className="w-4 h-4" />}
            label="Frames Processed"
            value={`${stats.processed_frames} / ${stats.total_frames}`}
          />
          <StatCard
            icon={<Layers className="w-4 h-4" />}
            label="Strategy"
            value={stats.strategy?.split('+')[0]?.trim() || '—'}
          />
          <StatCard
            icon={<Cpu className="w-4 h-4" />}
            label="Modules Active"
            value={stats.modules?.length || 0}
          />
          <StatCard
            icon={<Clock className="w-4 h-4" />}
            label="Time Elapsed"
            value={`${stats.time_elapsed || 0}s`}
          />
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value }) {
  return (
    <div className="bg-card border border-border rounded-lg p-3">
      <div className="flex items-center gap-2 text-text-secondary mb-1">
        {icon}
        <span className="text-[11px] font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-sm font-semibold text-text truncate">{value}</p>
    </div>
  );
}
