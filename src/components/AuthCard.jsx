import { LockKeyhole, Mail, ShieldCheck } from 'lucide-react';

export default function AuthCard({
  mode,
  email,
  password,
  loading,
  onModeChange,
  onEmailChange,
  onPasswordChange,
  onSubmit,
}) {
  const isLogin = mode === 'login';

  return (
    <section className="max-w-md mx-auto bg-card border border-border rounded-2xl p-6 sm:p-8 shadow-sm animate-slide-up">
      <div className="text-center">
        <div className="w-14 h-14 rounded-2xl bg-primary-light mx-auto flex items-center justify-center">
          <ShieldCheck className="w-7 h-7 text-primary-dark" />
        </div>
        <h2 className="mt-4 text-2xl font-semibold text-text">
          {isLogin ? 'Sign in to your workspace' : 'Create your workspace'}
        </h2>
        <p className="mt-2 text-sm text-text-secondary">
          Save videos under your account and reuse them for analysis anytime.
        </p>
      </div>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-text">Email</span>
          <div className="mt-2 flex items-center gap-3 rounded-xl border border-border bg-bg px-4 py-3">
            <Mail className="w-4 h-4 text-text-secondary" />
            <input
              type="email"
              value={email}
              onChange={(event) => onEmailChange(event.target.value)}
              placeholder="you@example.com"
              className="w-full bg-transparent text-sm text-text outline-none"
              disabled={loading}
            />
          </div>
        </label>

        <label className="block">
          <span className="text-sm font-medium text-text">Password</span>
          <div className="mt-2 flex items-center gap-3 rounded-xl border border-border bg-bg px-4 py-3">
            <LockKeyhole className="w-4 h-4 text-text-secondary" />
            <input
              type="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              placeholder="At least 6 characters"
              className="w-full bg-transparent text-sm text-text outline-none"
              disabled={loading}
            />
          </div>
        </label>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-70"
        >
          {loading ? 'Please wait...' : isLogin ? 'Sign In' : 'Create Account'}
        </button>
      </form>

      <div className="mt-5 flex items-center justify-center gap-2 text-sm text-text-secondary">
        <span>{isLogin ? 'Need an account?' : 'Already have an account?'}</span>
        <button
          type="button"
          onClick={() => onModeChange(isLogin ? 'signup' : 'login')}
          className="font-medium text-primary-dark hover:text-primary"
          disabled={loading}
        >
          {isLogin ? 'Create one' : 'Sign in'}
        </button>
      </div>
    </section>
  );
}
