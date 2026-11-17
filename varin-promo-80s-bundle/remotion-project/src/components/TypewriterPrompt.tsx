import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {VARIN_LIGHT} from '../theme/tokens';

export const TypewriterPrompt: React.FC<{prefix: string; highlight: string}> = ({prefix, highlight}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sec = frame / fps;
  const full = prefix + highlight;
  const count = sec < 0.12 ? 0 : Math.min(full.length, Math.floor(((sec - 0.12) / 1.85) * full.length) + 1);
  const shownPre = full.slice(0, Math.min(count, prefix.length));
  const shownHl = count > prefix.length ? full.slice(prefix.length, count) : '';
  const showCaret = count < full.length || Math.floor(sec * 5) % 2 === 0;

  return (
    <AbsoluteFill
      style={{
        background: VARIN_LIGHT.stageGradient,
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'Noto Sans CJK SC, system-ui, sans-serif',
      }}
    >
      <div style={{fontSize: 56, fontWeight: 700, display: 'flex', alignItems: 'center'}}>
        <span style={{color: '#20272a'}}>{shownPre}</span>
        <span style={{color: '#345ca2'}}>{shownHl}</span>
        {showCaret && (
          <span
            style={{
              display: 'inline-block',
              width: 6,
              height: 58,
              background: '#345ca2',
              borderRadius: 3,
              marginLeft: 8,
            }}
          />
        )}
      </div>
    </AbsoluteFill>
  );
};
