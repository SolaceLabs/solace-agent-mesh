import { createContext } from "react";
import type { SelectionContextValue } from "./types";

export const TextSelectionContext = createContext<SelectionContextValue | undefined>(undefined);
