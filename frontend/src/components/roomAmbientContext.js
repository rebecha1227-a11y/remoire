import { createContext } from 'react';

export const RoomAmbientContext = createContext(null);

export function readRoomAccentColor() {
  try {
    const tweaks = JSON.parse(localStorage.getItem('remoire_tweaks') || '{}');
    return tweaks.accentColor || '';
  } catch {
    return '';
  }
}
