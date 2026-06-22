import React, { useState, useEffect } from 'react';

// Custom useTypewriter hook
const useTypewriter = (text: string, speed: number = 38, startDelay: number = 600) => {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    let timer: any;
    let index = 0;

    const startTyping = () => {
      timer = setInterval(() => {
        if (index < text.length) {
          const char = text.charAt(index);
          setDisplayed((prev) => prev + char);
          index++;
        } else {
          clearInterval(timer);
          setDone(true);
        }
      }, speed);
    };

    const delayTimer = setTimeout(startTyping, startDelay);

    return () => {
      clearTimeout(delayTimer);
      if (timer) clearInterval(timer);
    };
  }, [text, speed, startDelay]);

  return { displayed, done };
};

interface HeroProps {
  onAuthClick: () => void;
}

export const Hero: React.FC<HeroProps> = ({ onAuthClick }) => {
  const taglineText = "Glad you stopped in. You supply the thinking. We orient it. Now, what are we building?";
  const { displayed, done } = useTypewriter(taglineText, 38, 600);
  const [showPills, setShowPills] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Show pill buttons after a 400ms delay, independent of typewriter progress
    const timer = setTimeout(() => {
      setShowPills(true);
    }, 400);
    return () => clearTimeout(timer);
  }, []);

  const handleCopyEmail = async () => {
    try {
      await navigator.clipboard.writeText('hello@wildestideas.co');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const handleScrollTo = (selector: string) => {
    const element = document.querySelector(selector);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section className="h-screen w-full flex flex-col justify-end pb-16 md:justify-center md:pb-0 px-5 sm:px-8 md:px-10 overflow-hidden relative">
      <div className="max-w-xl relative z-10 text-left">
        {/* Blurred Intro Label */}
        <div className="pointer-events-none select-none mb-5 sm:mb-6">
          <p 
            className="font-body text-black font-normal"
            style={{
              fontSize: 'clamp(18px, 4vw, 26px)',
              lineHeight: '1.3',
              filter: 'blur(3.5px)',
            }}
          >
            Hey there, meet Lodestone,
            <br />
            the coding tutor that makes you think.
          </p>
        </div>

        {/* Typewriter Text */}
        <p
          className="font-body text-black mb-5 sm:mb-6 font-normal min-h-[70px] md:min-h-[100px]"
          style={{
            fontSize: 'clamp(18px, 4vw, 26px)',
            lineHeight: '1.35',
          }}
        >
          {displayed}
          {!done && (
            <span className="inline-block w-[2px] h-[1.1em] bg-black align-middle ml-[2px] animate-blink" />
          )}
        </p>

        {/* Action Pills */}
        <div
          className={`flex flex-wrap gap-y-1 transition-all duration-500 ease-out transform ${
            showPills ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
          }`}
        >
          {/* Get Started Pill */}
          <button
            onClick={onAuthClick}
            className="inline-flex items-center justify-center bg-white text-black border border-black/10 rounded-full text-[13px] sm:text-[15px] px-4 sm:px-5 py-[0.3em] mx-[0.2em] mb-[0.4em] whitespace-nowrap hover:bg-black hover:text-white transition-colors duration-200 font-body"
          >
            Get Started
          </button>

          {/* What is it Pill */}
          <button
            onClick={() => handleScrollTo('#what-is-it')}
            className="inline-flex items-center justify-center bg-white text-black border border-black/10 rounded-full text-[13px] sm:text-[15px] px-4 sm:px-5 py-[0.3em] mx-[0.2em] mb-[0.4em] whitespace-nowrap hover:bg-black hover:text-white transition-colors duration-200 font-body"
          >
            What is it?
          </button>

          {/* Why it matters Pill */}
          <button
            onClick={() => handleScrollTo('#why-it-matters')}
            className="inline-flex items-center justify-center bg-white text-black border border-black/10 rounded-full text-[13px] sm:text-[15px] px-4 sm:px-5 py-[0.3em] mx-[0.2em] mb-[0.4em] whitespace-nowrap hover:bg-black hover:text-white transition-colors duration-200 font-body"
          >
            Why it matters
          </button>

          {/* Built by Pill */}
          <button
            onClick={() => handleScrollTo('#built-by')}
            className="inline-flex items-center justify-center bg-white text-black border border-black/10 rounded-full text-[13px] sm:text-[15px] px-4 sm:px-5 py-[0.3em] mx-[0.2em] mb-[0.4em] whitespace-nowrap hover:bg-black hover:text-white transition-colors duration-200 font-body"
          >
            Built by
          </button>

          {/* Contact Outline Pill */}
          <button
            onClick={handleCopyEmail}
            className="inline-flex items-center justify-center bg-transparent text-black border border-black/40 rounded-full text-[13px] sm:text-[15px] px-4 sm:px-5 py-[0.3em] mx-[0.2em] mb-[0.4em] whitespace-nowrap hover:bg-black hover:text-white hover:border-black transition-colors duration-200 font-body gap-2 sm:gap-3"
          >
            <span className="underline underline-offset-1">
              {copied ? 'Copied!' : 'Reach us: hello@wildestideas.co'}
            </span>
            <svg
              className="w-[12px] h-[12px] fill-none stroke-current"
              viewBox="0 0 24 24"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
        </div>
      </div>
    </section>
  );
};
