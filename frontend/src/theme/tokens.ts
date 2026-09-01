export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const radius = {
  sm: 6,
  md: 10,
  lg: 16,
  pill: 999,
} as const;

export const typography = {
  fontFamily: undefined, // system default per platform
  title: { fontSize: 28, fontWeight: '700' as const, letterSpacing: -0.4 },
  heading: { fontSize: 20, fontWeight: '700' as const, letterSpacing: -0.2 },
  subheading: { fontSize: 16, fontWeight: '600' as const },
  body: { fontSize: 15, fontWeight: '400' as const },
  bodyStrong: { fontSize: 15, fontWeight: '600' as const },
  caption: { fontSize: 13, fontWeight: '400' as const },
  small: { fontSize: 11, fontWeight: '600' as const },
} as const;

export const priorityColors = {
  low: { fg: '#0F9D58', bg: '#E4F7EC' },
  medium: { fg: '#B7791F', bg: '#FDF3D9' },
  high: { fg: '#D64545', bg: '#FBE4E4' },
} as const;

export const priorityColorsDark = {
  low: { fg: '#4ADE80', bg: '#123321' },
  medium: { fg: '#FACC15', bg: '#332C10' },
  high: { fg: '#F87171', bg: '#3A1616' },
} as const;

const lightPalette = {
  background: '#F4F5F8',
  surface: '#FFFFFF',
  surfaceAlt: '#ECEEF3',
  border: '#E1E4EA',
  text: '#14161A',
  textMuted: '#6B7280',
  textFaint: '#9AA1AC',
  primary: '#6366F1',
  primaryText: '#FFFFFF',
  danger: '#DC2626',
  overlay: 'rgba(15, 17, 21, 0.45)',
  shadow: '#000000',
};

const darkPalette = {
  background: '#0E1014',
  surface: '#191B21',
  surfaceAlt: '#22252C',
  border: '#2B2F38',
  text: '#F2F3F5',
  textMuted: '#9AA1AC',
  textFaint: '#6B7280',
  primary: '#818CF8',
  primaryText: '#0E1014',
  danger: '#F87171',
  overlay: 'rgba(0, 0, 0, 0.6)',
  shadow: '#000000',
};

export type Palette = typeof lightPalette;

export const palettes = {
  light: lightPalette,
  dark: darkPalette,
};
