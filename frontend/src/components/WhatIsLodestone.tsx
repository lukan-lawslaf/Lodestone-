import React from 'react';

export const WhatIsLodestone: React.FC = () => {
  return (
    <section 
      id="what-is-it" 
      className="relative z-10 w-full min-h-screen flex flex-col justify-center py-20 px-5 sm:px-8 md:px-12 bg-white/90 backdrop-blur-md border-t border-black/5"
    >
      <div className="max-w-4xl mx-auto text-left">
        <h2 className="font-heading text-[32px] sm:text-[48px] md:text-[56px] text-black tracking-tight leading-none mb-6">
          What is Lodestone?
        </h2>
        
        <p className="font-body text-[18px] sm:text-[22px] text-black/70 max-w-2xl mb-12 sm:mb-16 leading-relaxed">
          It is an AI coding tutor that does not treat you like a copy-paste machine. 
          Most AI tools make you lazy. Lodestone is designed to make you sharp.
        </p>

        {/* The Contrast Grid */}
        <div className="grid md:grid-cols-2 gap-8 sm:gap-12 mt-4">
          {/* Traditional AI column */}
          <div className="border border-black/10 rounded-[24px] p-6 sm:p-8 bg-black/[0.02] flex flex-col justify-between">
            <div>
              <span className="font-heading text-xs uppercase tracking-widest text-black/40 block mb-4">
                Other AI
              </span>
              <h3 className="font-heading text-[22px] sm:text-[26px] text-black/50 tracking-tight mb-4">
                The Cheat Sheet Loop
              </h3>
              <p className="font-body text-[16px] sm:text-[18px] text-black/50 leading-relaxed">
                Type a question, get a block of code, paste it. It breaks. Ask again, copy-paste again. It works (sometimes), but you learned zero. Next time you have to debug it yourself? You're completely stuck.
              </p>
            </div>
            <div className="mt-8 text-black/40 font-mono text-sm">
              &gt; Copying code is not coding.
            </div>
          </div>

          {/* Lodestone column */}
          <div className="border-2 border-black rounded-[24px] p-6 sm:p-8 bg-black text-white flex flex-col justify-between shadow-xl">
            <div>
              <span className="font-heading text-xs uppercase tracking-widest text-white/60 block mb-4">
                Lodestone
              </span>
              <h3 className="font-heading text-[22px] sm:text-[26px] text-white tracking-tight mb-4">
                The Socratic Guide
              </h3>
              <p className="font-body text-[16px] sm:text-[18px] text-white/90 leading-relaxed">
                Type a question, and we don't hand out the answer. We analyze your code, find the gap, and ask you the exact right question to nudge your brain in the right direction. You write the code, you fix the bug, you build the muscle.
              </p>
            </div>
            <div className="mt-8 text-white/60 font-mono text-sm flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>&gt; You supply the thinking. We orient it.</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
