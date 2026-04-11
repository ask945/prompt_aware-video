import { AlertTriangle, RefreshCw } from 'lucide-react';

export default function RetryCard({ message, onRetry }) {
  return (
    <div className="animate-fade-in bg-card border border-red-200 rounded-xl p-6 text-center">
      <div className="w-12 h-12 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-3">
        <AlertTriangle className="w-6 h-6 text-red-500" />
      </div>
      <h3 className="text-sm font-semibold text-text mb-1">Something went wrong</h3>
      <p className="text-xs text-text-secondary mb-4">
        {message || 'The analysis could not be completed. Please try again.'}
      </p>
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-dark text-white text-sm font-medium rounded-lg transition-colors"
      >
        <RefreshCw className="w-4 h-4" />
        Try Again
      </button>
    </div>
  );
}
