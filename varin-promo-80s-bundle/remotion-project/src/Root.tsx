import React from 'react';
import {Composition} from 'remotion';
import {VarinPromo80s} from './VarinPromo80s';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="VarinPromo80s"
      component={VarinPromo80s}
      durationInFrames={2400}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
