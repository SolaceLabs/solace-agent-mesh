import { useContext } from "react";
import { TextSelectionContext } from "./TextSelectionContext";

export const useTextSelection = () => {
    const context = useContext(TextSelectionContext);
    if (!context) {
        throw new Error("useTextSelection must be used within TextSelectionProvider");
    }
    return context;
};
