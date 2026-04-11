import { LogOut, UserRound, Video } from 'lucide-react';

export default function Header({ user, onLogout }) {
  return (
    <header className="bg-card border-b border-border px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-primary rounded-lg flex items-center justify-center">
            <Video className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-text leading-tight">Prompt-Aware Video Analysis</h1>
            <p className="text-xs text-text-secondary">Intelligent video understanding powered by AI</p>
          </div>
        </div>

        {user ? (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 rounded-full border border-border bg-bg px-3 py-2 text-sm text-text-secondary">
              <UserRound className="w-4 h-4 text-primary-dark" />
              <span>{user.email}</span>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-2 text-sm font-medium text-text hover:border-primary/50 hover:bg-primary-light/30"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
