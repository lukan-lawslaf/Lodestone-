import React, { useState } from 'react';

interface NavbarProps {
  onAuthClick: () => void;
  user: any;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onAuthClick, user, onLogout }) => {
  const [isOpen, setIsOpen] = useState(false);

  const toggleMenu = () => setIsOpen(!isOpen);

  const handleNavClick = (selector: string) => {
    setIsOpen(false);
    const element = document.querySelector(selector);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <>
      <nav className="fixed top-0 left-0 w-full z-40 px-5 sm:px-8 py-4 sm:py-5 flex justify-between items-center bg-transparent select-none">
        {/* Logo */}
        <a href="/" className="flex items-center gap-3 text-black transition-opacity hover:opacity-60">
          <span className="font-heading text-[21px] sm:text-[26px] tracking-tight font-medium">
            Lodestone®
          </span>
          <span className="text-[25px] sm:text-[30px] leading-none select-none tracking-tighter -ml-1 text-black">
            ✳︎
          </span>
        </a>

        {/* Desktop nav links */}
        <div className="hidden md:flex items-center text-[23px] text-black">
          <button
            onClick={() => handleNavClick('#what-is-it')}
            className="hover:opacity-60 transition-opacity"
          >
            What is it
          </button>
          <span className="mx-1 select-none font-light">, </span>
          <button
            onClick={() => handleNavClick('#why-it-matters')}
            className="hover:opacity-60 transition-opacity"
          >
            Why it matters
          </button>
          <span className="mx-1 select-none font-light">, </span>
          <button
            onClick={() => handleNavClick('#built-by')}
            className="hover:opacity-60 transition-opacity"
          >
            Built by
          </button>
        </div>

        {/* Desktop CTA */}
        <div className="hidden md:block">
          {user ? (
            <div className="flex items-center gap-4 text-[23px] text-black">
              <a href="/dashboard" className="underline underline-offset-2 hover:opacity-60 transition-opacity">
                Dashboard
              </a>
              <span className="opacity-40">/</span>
              <button onClick={onLogout} className="underline underline-offset-2 hover:opacity-60 transition-opacity">
                Sign Out
              </button>
            </div>
          ) : (
            <button
              onClick={onAuthClick}
              className="text-[23px] text-black underline underline-offset-2 hover:opacity-60 transition-opacity"
            >
              Get started
            </button>
          )}
        </div>

        {/* Mobile Hamburger */}
        <button
          onClick={toggleMenu}
          aria-label="Toggle navigation menu"
          className="md:hidden flex flex-col justify-center items-center w-8 h-8 gap-[5px] z-50 focus:outline-none"
        >
          <span
            className={`w-6 h-[2px] bg-black transition-all duration-300 ${
              isOpen ? 'rotate-45 translate-y-[7px]' : ''
            }`}
          />
          <span
            className={`w-6 h-[2px] bg-black transition-all duration-300 ${
              isOpen ? 'opacity-0' : 'opacity-100'
            }`}
          />
          <span
            className={`w-6 h-[2px] bg-black transition-all duration-300 ${
              isOpen ? '-rotate-45 -translate-y-[7px]' : ''
            }`}
          />
        </button>
      </nav>

      {/* Mobile Overlay Menu */}
      <div
        className={`fixed inset-0 bg-white/95 backdrop-blur-sm z-30 flex flex-col justify-center px-8 gap-8 transition-all duration-300 md:hidden ${
          isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      >
        <button
          onClick={() => handleNavClick('#what-is-it')}
          className="text-left text-[32px] font-medium text-black hover:opacity-60 transition-opacity"
        >
          What is it
        </button>
        <button
          onClick={() => handleNavClick('#why-it-matters')}
          className="text-left text-[32px] font-medium text-black hover:opacity-60 transition-opacity"
        >
          Why it matters
        </button>
        <button
          onClick={() => handleNavClick('#built-by')}
          className="text-left text-[32px] font-medium text-black hover:opacity-60 transition-opacity"
        >
          Built by
        </button>
        
        {user ? (
          <>
            <a
              href="/dashboard"
              className="text-left text-[32px] font-medium text-black underline underline-offset-4 hover:opacity-60 transition-opacity"
            >
              Go to Dashboard
            </a>
            <button
              onClick={() => {
                setIsOpen(false);
                onLogout();
              }}
              className="text-left text-[32px] font-medium text-black underline underline-offset-4 hover:opacity-60 transition-opacity"
            >
              Sign Out
            </button>
          </>
        ) : (
          <button
            onClick={() => {
              setIsOpen(false);
              onAuthClick();
            }}
            className="text-left text-[32px] font-medium text-black underline underline-offset-4 hover:opacity-60 transition-opacity"
          >
            Get started
          </button>
        )}
      </div>
    </>
  );
};
