/**
 * PiNaCoLlAda — Pineapple colour theme
 *
 * Palette inspired by a fresh pineapple:
 *   YELLOW   — the golden body
 *   GREEN    — the spiky crown leaves
 *   ORANGE   — tropical accent / warm highlight
 *   CREAM    — pale background, like pineapple flesh
 */

const COLORS = {
  // Brand
  yellow: '#F5C518',       // pineapple gold (primary)
  yellowDark: '#D4A80F',   // pressed / darker gold
  green: '#2D7D46',        // crown leaf green
  greenDark: '#1E5C32',    // deep green (header / active)
  orange: '#E8870A',       // tropical accent

  // Surfaces
  background: '#FFFDE7',   // cream — main screen background
  surface: '#FFFFFF',      // card / modal surface
  border: '#E8DCA0',       // warm golden border

  // Text
  textPrimary: '#1A1A1A',
  textSecondary: '#555555',
  textMuted: '#888888',
  textOnBrand: '#FFFFFF',  // white text on green / yellow

  // Status
  success: '#27AE60',
  danger: '#E74C3C',
  warning: '#F39C12',

  // Tab / navigation chrome
  tabActive: '#F5C518',
  tabInactive: '#A8A08C',
  headerBg: '#2D7D46',
  headerText: '#FFFFFF',
};

export default COLORS;
