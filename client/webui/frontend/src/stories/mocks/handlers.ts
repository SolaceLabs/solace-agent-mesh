import { http, HttpResponse } from "msw";
import { mockAgentCards } from "./data";

export const globalHandlers = [http.get("*/api/v1/agentCards", () => HttpResponse.json(mockAgentCards))];
