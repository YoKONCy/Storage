import React from 'react';
import {easeWhip} from '../theme/tokens';

export const CornerPill: React.FC<{
  text: string;
  dotColor: string;
  progress: number;
  align?: 'left' | 'right';
}> = ({text, dotColor, progress, align = 'left'}) => {
  const p = Math.max(0, Math.min(1, progress));
  if (p <= 0.01) return null;
  const yOff = (1 - easeWhip(p)) * -12;

  return (
    <div
      style={{
        position: 'absolute',
        top: 38 + yOff,
        left: align === 'left' ? 44 : undefined,
        right: align === 'right' ? 44 : undefined,
        height: 48,
        padding: '0 24px 0 18px',
        borderRadius: 24,
        background: 'rgba(24, 30, 36, 0.92)',
        border: '1px solid rgba(255, 255, 255, 0.18)',
        boxShadow: '0 8px 20px rgba(15, 20, 28, 0.22)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        opacity: p,
        zIndex: 20,
      }}
    >
      <span style={{width: 12, height: 12, borderRadius: '50%', background: dotColor}} />
      <span style={{color: '#f8fafc', fontSize: 20, fontWeight: 700, fontFamily: 'Noto Sans CJK SC, sans-serif'}}>
        {text}
      </span>
    </div>
  );
};
