import { useState, useEffect } from 'react';
import { supabase } from './lib/supabase';
import { BackgroundVideo } from './components/BackgroundVideo';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { WhatIsLodestone } from './components/WhatIsLodestone';
import { WhyItMatters } from './components/WhyItMatters';
import { BuiltBy } from './components/BuiltBy';
import { AuthModal } from './components/AuthModal';
import { DashboardPlaceholder } from './components/DashboardPlaceholder';

function App() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [path, setPath] = useState(window.location.pathname);

  // Setup path change listener for client-side routing
  useEffect(() => {
    const handleLocationChange = () => {
      setPath(window.location.pathname);
    };

    window.addEventListener('popstate', handleLocationChange);
    return () => window.removeEventListener('popstate', handleLocationChange);
  }, []);

  const navigate = (to: string) => {
    window.history.pushState(null, '', to);
    setPath(to);
  };

  // Listen to Supabase Auth State changes
  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // Listen to changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setUser(null);
    navigate('/');
  };

  const handleAuthSuccess = (_userId: string) => {
    setShowAuthModal(false);
    // user will be updated via onAuthStateChange listener
    navigate('/dashboard');
  };

  if (loading) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-white text-black font-body">
        <div className="flex flex-col items-center gap-3">
          <svg className="animate-spin h-8 w-8 text-black" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-sm font-mono tracking-widest uppercase">Initializing Lodestone...</span>
        </div>
      </div>
    );
  }

  // Dashboard Page Route
  if (path === '/dashboard') {
    if (!user) {
      // If not logged in, redirect to home page and trigger auth modal
      setTimeout(() => {
        navigate('/');
        setShowAuthModal(true);
      }, 0);
      return null;
    }

    return (
      <DashboardPlaceholder 
        userId={user.id} 
        userEmail={user.email ?? ''} 
        onLogout={handleLogout} 
      />
    );
  }

  // Home Page Landing Route
  return (
    <div className="relative min-h-screen w-full overflow-x-hidden bg-transparent">
      {/* Background Interactive Video */}
      <BackgroundVideo />

      {/* Landing Layout Container */}
      <div className="relative z-10 w-full flex flex-col">
        {/* Navigation Bar */}
        <Navbar 
          onAuthClick={() => setShowAuthModal(true)} 
          user={user} 
          onLogout={handleLogout} 
        />

        {/* Hero Section */}
        <Hero onAuthClick={() => setShowAuthModal(true)} />

        {/* Socratic Comparison Section */}
        <WhatIsLodestone />

        {/* Problem & Socratic Framework Section */}
        <WhyItMatters />

        {/* Team & University Credentials Section */}
        <BuiltBy />

        {/* Footer info (optional visual polish) */}
        <footer className="relative z-10 w-full py-8 text-center text-xs font-mono text-black/40 border-t border-black/5 bg-white/95">
          Lodestone &copy; 2026. Made with passion by Team WildestIdeas.
        </footer>
      </div>

      {/* Supabase Authentication Modal Overlay */}
      <AuthModal 
        isOpen={showAuthModal} 
        onClose={() => setShowAuthModal(false)} 
        onSuccess={handleAuthSuccess} 
      />
    </div>
  );
}

export default App;
