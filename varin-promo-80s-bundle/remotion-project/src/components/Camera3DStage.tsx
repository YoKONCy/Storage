import React from 'react';
import {AbsoluteFill} from 'remotion';
import {VARIN_DARK, VARIN_LIGHT} from '../theme/tokens';

export interface Camera3DProps {
  fx: number;
  fy: number;
  zoom: number;
  yawDeg?: number;
  pitchDeg?: number;
  rollDeg?: number;
  dark?: boolean;
  children: React.ReactNode;
}

export const Camera3DStage: React.FC<Camera3DProps> = ({
  fx,
  fy,
  zoom,
  yawDeg = 0,
  pitchDeg = 0,
  rollDeg = 0,
  dark = false,
  children,
}) => {
  const scale = (1332 / 2220) * zoom;
  const theme = dark ? VARIN_DARK : VARIN_LIGHT;

  return (
    <AbsoluteFill
      style={{
        background: theme.stageGradient,
        perspective: 2450,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '50%',
          width: 2220,
          height: 1410,
          transformOrigin: `${fx}px ${fy}px`,
          transform: `translate(${-fx}px, ${-fy}px) scale(${scale}) rotateZ(${rollDeg}deg) rotateX(${pitchDeg}deg) rotateY(${yawDeg}deg)`,
          borderRadius: 22,
          boxShadow: dark
            ? '0 32px 84px rgba(0, 0, 0, 0.62)'
            : '0 24px 64px rgba(18, 24, 34, 0.18)',
          overflow: 'hidden',
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};
