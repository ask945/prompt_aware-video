import { Search, Sparkles } from 'lucide-react';

const EXAMPLE_CHIPS = [
  "Is there a dog?",
  "Find red objects",
  "What text is on screen?",
  "How many people?",
  "When does someone fall?",
];

export default function QueryInput({ query, onQueryChange, onAnalyze, disabled, canAnalyze }) {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (canAnalyze) onAnalyze();
  };

  return (
    <div className="space-y-3">
      <form onSubmit={handleSubmit} className="relative">
        <div className="flex items-center gap-2 bg-card border border-border rounded-xl px-4 py-3 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 transition-all">
          <Search className="w-4 h-4 text-text-secondary flex-shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Ask a question about your video..."
            className="flex-1 bg-transparent outline-none text-sm text-text placeholder:text-text-secondary/60"
            disabled={disabled}
          />
          <button
            type="submit"
            disabled={!canAnalyze}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
              ${canAnalyze
                ? 'bg-primary hover:bg-primary-dark text-white shadow-sm hover:shadow-md active:scale-[0.98]'
                : 'bg-border text-text-secondary cursor-not-allowed'
              }
            `}
          >
            <Sparkles className="w-4 h-4" />
            Analyze
          </button>
        </div>
      </form>

      <div className="flex flex-wrap gap-2">
        {EXAMPLE_CHIPS.map((chip) => (
          <button
            key={chip}
            onClick={() => onQueryChange(chip)}
            disabled={disabled}
            className="px-3 py-1.5 text-xs font-medium bg-primary-light/60 text-primary-dark rounded-full hover:bg-primary-light transition-colors disabled:opacity-50"
          >
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
