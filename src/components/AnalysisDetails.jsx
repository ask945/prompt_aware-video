import { useState } from 'react';
import { ChevronDown, ChevronUp, BarChart3, Layers, Cpu, Crosshair, Target } from 'lucide-react';

export default function AnalysisDetails({ stats }) {
  const [open, setOpen] = useState(false);

  if (!stats) return null;

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-bg/50 transition-colors"
      >
        <span className="text-sm font-medium text-text">Analysis Details</span>
        {open ? (
          <ChevronUp className="w-4 h-4 text-text-secondary" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-secondary" />
        )}
      </button>

      {open && (
        <div className="px-5 pb-4 border-t border-border pt-4 animate-fade-in">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <DetailRow
              icon={<BarChart3 className="w-4 h-4" />}
              label="Frames"
              value={`${stats.processed_frames} of ${stats.total_frames.toLocaleString()} processed`}
            />
            <DetailRow
              icon={<Layers className="w-4 h-4" />}
              label="Reduction"
              value={`${stats.reduction_percent}% frames skipped`}
            />
            <DetailRow
              icon={<Crosshair className="w-4 h-4" />}
              label="Strategy"
              value={stats.strategy}
            />
            <DetailRow
              icon={<Target className="w-4 h-4" />}
              label="Intent / Target"
              value={`${stats.intent} → "${stats.target}"`}
            />
          </div>

          <div className="mt-4">
            <div className="flex items-center gap-2 text-text-secondary mb-2">
              <Cpu className="w-4 h-4" />
              <span className="text-xs font-medium uppercase tracking-wide">Active Modules</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {stats.modules?.map((mod) => (
                <span
                  key={mod}
                  className="px-2.5 py-1 text-xs font-medium bg-primary-light text-primary-dark rounded-md"
                >
                  {mod}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({ icon, label, value }) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="text-text-secondary mt-0.5">{icon}</div>
      <div>
        <p className="text-[11px] font-medium text-text-secondary uppercase tracking-wide">{label}</p>
        <p className="text-sm text-text">{value}</p>
      </div>
    </div>
  );
}
