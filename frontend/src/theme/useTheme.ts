import { useColorScheme } from 'react-native';
import { useSettingsStore } from '@/store/useSettingsStore';
import { palettes, priorityColors, priorityColorsDark, radius, spacing, typography } from './tokens';

export function useTheme() {
  const system = useColorScheme();
  const themeMode = useSettingsStore((s) => s.themeMode);

  const scheme = themeMode === 'system' ? system ?? 'light' : themeMode;
  const isDark = scheme === 'dark';
  const colors = palettes[isDark ? 'dark' : 'light'];

  return {
    isDark,
    colors,
    priority: isDark ? priorityColorsDark : priorityColors,
    spacing,
    radius,
    typography,
  };
}

export type Theme = ReturnType<typeof useTheme>;
