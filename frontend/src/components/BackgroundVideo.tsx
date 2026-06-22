import React, { useEffect, useRef } from 'react';

export const BackgroundVideo: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const prevXRef = useRef<number | null>(null);
  const targetTimeRef = useRef<number>(0);
  const isSeekingRef = useRef<boolean>(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!video.duration || isNaN(video.duration)) return;

      const currentX = e.clientX;
      if (prevXRef.current === null) {
        prevXRef.current = currentX;
        return;
      }

      const delta = currentX - prevXRef.current;
      prevXRef.current = currentX;

      const SENSITIVITY = 0.8;
      const timeDelta = (delta / window.innerWidth) * SENSITIVITY * video.duration;

      let nextTargetTime = targetTimeRef.current + timeDelta;
      nextTargetTime = Math.max(0, Math.min(video.duration, nextTargetTime));
      targetTimeRef.current = nextTargetTime;

      if (!isSeekingRef.current) {
        isSeekingRef.current = true;
        video.currentTime = nextTargetTime;
      }
    };

    const handleSeeked = () => {
      isSeekingRef.current = false;
      const v = videoRef.current;
      if (!v) return;

      if (Math.abs(v.currentTime - targetTimeRef.current) > 0.05) {
        isSeekingRef.current = true;
        v.currentTime = targetTimeRef.current;
      }
    };

    const handleLoadedMetadata = () => {
      targetTimeRef.current = 0;
    };

    window.addEventListener('mousemove', handleMouseMove);
    video.addEventListener('seeked', handleSeeked);
    video.addEventListener('loadedmetadata', handleLoadedMetadata);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      video.removeEventListener('seeked', handleSeeked);
      video.removeEventListener('loadedmetadata', handleLoadedMetadata);
    };
  }, []);

  return (
    <video
      ref={videoRef}
      className="fixed inset-0 z-0 object-cover"
      style={{
        width: '100vw',
        height: '100vh',
        objectPosition: '70% center',
      }}
      src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260530_042513_df96a13b-6155-4f6e-8b93-c9dee66fba08.mp4"
      muted
      aria-hidden="true"
      playsInline
      preload="auto"
    />
  );
};
