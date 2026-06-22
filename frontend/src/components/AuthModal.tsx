import React, { useState } from 'react';
import { supabase } from '../lib/supabase';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (userId: string) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    setLoading(true);

    if (!email || !password) {
      setErrorMsg('Please enter both email and password.');
      setLoading(false);
      return;
    }

    if (password.length < 6) {
      setErrorMsg('Password must be at least 6 characters.');
      setLoading(false);
      return;
    }

    try {
      if (isSignUp) {
        // Sign Up
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
        });

        if (error) throw error;
        
        if (data?.user && data.session) {
          // Immediately log in on sign up if auto-confirm is enabled
          onSuccess(data.user.id);
        } else {
          setSuccessMsg('Check your email for the confirmation link!');
        }
      } else {
        // Sign In
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });

        if (error) throw error;

        if (data?.user) {
          onSuccess(data.user.id);
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'An error occurred during authentication.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal Content */}
      <div className="relative w-full max-w-md bg-white rounded-[28px] border border-black/10 p-8 sm:p-10 shadow-2xl z-10 text-left">
        {/* Close Button */}
        <button 
          onClick={onClose}
          className="absolute top-6 right-6 text-black/40 hover:text-black hover:bg-black/5 p-1 rounded-full transition-all"
          aria-label="Close modal"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Header */}
        <div className="mb-8">
          <span className="text-[25px] text-black font-heading tracking-tight select-none">
            ✳︎
          </span>
          <h2 className="font-heading text-3xl text-black tracking-tight mt-3">
            {isSignUp ? 'Create your account' : 'Welcome back'}
          </h2>
          <p className="font-body text-sm text-black/55 mt-1">
            {isSignUp 
              ? 'Get started by creating a secure account.' 
              : 'Sign in to access your Lodestone sessions.'
            }
          </p>
        </div>

        {/* Error/Success banners */}
        {errorMsg && (
          <div className="mb-5 p-3.5 bg-rose-50 text-rose-700 text-sm font-body rounded-xl border border-rose-200">
            {errorMsg}
          </div>
        )}
        {successMsg && (
          <div className="mb-5 p-3.5 bg-emerald-50 text-emerald-700 text-sm font-body rounded-xl border border-emerald-200">
            {successMsg}
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-widest text-black/50 font-mono mb-2" htmlFor="email">
              Email Address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@domain.com"
              disabled={loading}
              className="w-full bg-black/[0.03] border border-black/10 rounded-xl px-4 py-3 text-black font-body text-base placeholder-black/30 focus:outline-none focus:border-black/30 focus:bg-transparent transition-all"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-widest text-black/50 font-mono mb-2" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              disabled={loading}
              className="w-full bg-black/[0.03] border border-black/10 rounded-xl px-4 py-3 text-black font-body text-base placeholder-black/30 focus:outline-none focus:border-black/30 focus:bg-transparent transition-all"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black text-white py-3 px-4 rounded-xl font-heading font-medium tracking-tight text-base hover:bg-black/80 active:scale-[0.98] transition-all disabled:opacity-50 disabled:pointer-events-none mt-2 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span>Processing...</span>
              </>
            ) : (
              isSignUp ? 'Sign Up' : 'Sign In'
            )}
          </button>
        </form>

        {/* Toggle link */}
        <div className="mt-6 text-center">
          <button
            type="button"
            onClick={() => {
              setIsSignUp(!isSignUp);
              setErrorMsg(null);
              setSuccessMsg(null);
            }}
            className="font-body text-sm text-black/60 hover:text-black underline underline-offset-2 transition-colors"
          >
            {isSignUp ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
          </button>
        </div>
      </div>
    </div>
  );
};
