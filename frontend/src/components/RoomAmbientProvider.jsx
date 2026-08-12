import { RoomAmbientContext } from './roomAmbientContext';

export default function RoomAmbientProvider({ value, children }) {
  return <RoomAmbientContext.Provider value={value}>{children}</RoomAmbientContext.Provider>;
}
