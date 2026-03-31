import { createContext, useContext } from "react";

/** React context carrying the active language code ("en" | "zh"). */
export const LangContext = createContext("en");

/** Hook: returns the active language code from the nearest LangContext.Provider. */
export function useLang() {
  return useContext(LangContext);
}
