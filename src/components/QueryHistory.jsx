import { Clock, CheckCircle, XCircle, Search } from 'lucide-react';

export default function QueryHistory({ history, onSelectQuery }) {
  if (!history || history.length === 0) return null;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-text-secondary" />
        <h3 className="text-sm font-medium text-text-secondary">Query History</h3>
      </div>
      <div className="space-y-2">
        {history.map((item, index) => (
          <button
            key={index}
            onClick={() => onSelectQuery(item.query)}
            className="w-full flex items-center gap-3 bg-card border border-border rounded-lg px-4 py-3 hover:border-primary/40 hover:shadow-sm transition-all text-left group"
          >
            <Search className="w-3.5 h-3.5 text-text-secondary flex-shrink-0" />
            <span className="flex-1 text-sm text-text truncate">{item.query}</span>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              {item.found ? (
                <>
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  <span className="text-xs text-green-600 font-medium">{item.count} found</span>
                </>
              ) : (
                <>
                  <XCircle className="w-3.5 h-3.5 text-text-secondary" />
                  <span className="text-xs text-text-secondary">No results</span>
                </>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
