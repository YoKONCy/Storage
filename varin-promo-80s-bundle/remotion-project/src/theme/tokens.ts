export const VARIN_LIGHT = {
  background: '#f3f3f3',
  muted: '#f7f7f7',
  elevated: '#fafafa',
  foreground: '#383838',
  primary: '#4b6fac',
  stageGradient: 'radial-gradient(ellipse at 50% 45%, #f9fafc 0%, #eaeef4 100%)',
};

export const VARIN_DARK = {
  background: '#181818',
  muted: '#242424',
  elevated: '#2c2c2c',
  foreground: '#e8e8e8',
  primary: '#7aa7ef',
  stageGradient: 'radial-gradient(ellipse at 50% 45%, #1a202c 0%, #0b0e14 100%)',
};

export const easeWhip = (x: number): number => {
  const c = Math.max(0, Math.min(1, x));
  return 1 - Math.pow(1 - c, 5);
};
