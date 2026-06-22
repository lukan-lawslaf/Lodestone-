import React from 'react';

export const BuiltBy: React.FC = () => {
  const team = [
    {
      name: 'Garv',
      role: 'Lead Developer',
      tag: 'Architect',
    },
    {
      name: 'Rohin',
      role: 'Core Engineering',
      tag: 'Algorithms',
    },
    {
      name: 'Nakul',
      role: 'Core Engineering',
      tag: 'Fullstack',
    },
  ];

  return (
    <section 
      id="built-by" 
      className="relative z-10 w-full min-h-screen flex flex-col justify-center py-20 px-5 sm:px-8 md:px-12 bg-white/95 backdrop-blur-md border-t border-black/5"
    >
      <div className="max-w-4xl mx-auto text-left w-full">
        <h2 className="font-heading text-[32px] sm:text-[48px] md:text-[56px] text-black tracking-tight leading-none mb-6">
          Built by
        </h2>
        
        <p className="font-body text-[18px] sm:text-[22px] text-black/70 max-w-2xl mb-12 sm:mb-16 leading-relaxed">
          Lodestone is created by <strong className="text-black font-medium">Team WildestIdeas</strong>, 
          representing BML Munjal University and IPU University.
          Designed and built for the Bharat Academix CodeQuest hackathon.
        </p>

        {/* Team cards grid */}
        <div className="grid sm:grid-cols-3 gap-6 sm:gap-8">
          {team.map((member, idx) => (
            <div 
              key={idx}
              className="border border-black/10 rounded-[20px] p-6 sm:p-8 bg-black/[0.01] hover:bg-black/5 hover:border-black transition-all duration-300 flex flex-col justify-between"
            >
              <div>
                <span className="font-mono text-xs text-black/40 block mb-4 uppercase tracking-widest">
                  {member.tag}
                </span>
                <h3 className="font-heading text-[22px] sm:text-[26px] text-black font-medium tracking-tight mb-1">
                  {member.name}
                </h3>
                <p className="font-body text-[14px] sm:text-[16px] text-black/60">
                  {member.role}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Hackathon details */}
        <div className="mt-16 sm:mt-24 border-t border-black/10 pt-8 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
          <div>
            <h4 className="font-heading text-[18px] text-black font-medium">
              Bharat Academix CodeQuest
            </h4>
            <p className="font-body text-sm text-black/50">
              National Hackathon Showcase — Orienting India's tech education.
            </p>
          </div>
          <div className="flex gap-4">
            <span className="font-mono text-xs border border-black/20 rounded-full px-3 py-1 text-black/70">
              BML Munjal University
            </span>
            <span className="font-mono text-xs border border-black/20 rounded-full px-3 py-1 text-black/70">
              IPU University
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};
