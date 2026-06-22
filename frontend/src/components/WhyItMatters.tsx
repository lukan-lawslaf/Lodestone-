import React from 'react';

export const WhyItMatters: React.FC = () => {
  const steps = [
    {
      number: '01',
      title: 'The AI Copy Trap',
      description: 'You get a coding task, you ask ChatGPT/Copilot, you copy the block, paste it, compile. Rinse and repeat. You think you are building software, but you are just building a dependency on a chatbot.',
    },
    {
      number: '02',
      title: 'The Midterm Freeze',
      description: 'When the internet is cut, when the interviewer asks you to live-code, or when a production bug hits at 2 AM—you freeze. Because you never actually figured out how the code works.',
    },
    {
      number: '03',
      title: 'The Socratic Shift',
      description: 'Lodestone forces you to do the hard work of reasoning while keeping you on the right path. You write the code. You debug the errors. You own the skill. Forever.',
    },
  ];

  return (
    <section 
      id="why-it-matters" 
      className="relative z-10 w-full min-h-screen flex flex-col justify-center py-20 px-5 sm:px-8 md:px-12 bg-black text-white"
    >
      <div className="max-w-4xl mx-auto text-left">
        <h2 className="font-heading text-[32px] sm:text-[48px] md:text-[56px] text-white tracking-tight leading-none mb-6">
          Why it matters
        </h2>
        
        <p className="font-body text-[18px] sm:text-[22px] text-white/70 max-w-2xl mb-12 sm:mb-16 leading-relaxed">
          The next generation of programmers is learning to paste, not program. 
          We are fixing that before it becomes an epidemic.
        </p>

        {/* 3-Step Grid */}
        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((step, idx) => (
            <div 
              key={idx} 
              className="border border-white/10 rounded-[20px] p-6 sm:p-8 bg-white/[0.02] flex flex-col justify-between hover:border-white/30 transition-all duration-300"
            >
              <div>
                <span className="font-heading text-4xl sm:text-5xl font-light text-white/20 block mb-6">
                  {step.number}
                </span>
                <h3 className="font-heading text-[20px] sm:text-[22px] text-white tracking-tight mb-3">
                  {step.title}
                </h3>
                <p className="font-body text-[15px] sm:text-[16px] text-white/70 leading-relaxed">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
