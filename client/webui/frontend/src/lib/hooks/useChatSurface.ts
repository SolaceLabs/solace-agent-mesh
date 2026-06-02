import { useContext } from "react";

import { ChatSurfaceContext, type ChatSurface } from "@/lib/contexts";

/**
 * The chat surface capabilities. Defaults to the full web UI when no
 * ChatSurfaceProvider is present (the context default), so consumers never need
 * a provider to behave as the standard UI.
 */
export function useChatSurface(): ChatSurface {
    return useContext(ChatSurfaceContext);
}
