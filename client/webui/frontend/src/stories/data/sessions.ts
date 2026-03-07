import type { Session } from "@/lib/types/fe";
import { populatedProject } from "./projects";

export const sessions: Session[] = [
    {
        id: "session-1",
        name: "Session 1",
        createdTime: new Date("2024-03-18T10:30:00Z").toISOString(),
        updatedTime: new Date("2024-03-20T14:22:00Z").toISOString(),
        projectId: populatedProject.id,
        projectName: populatedProject.name,
    },
    {
        id: "session-2",
        name: "Session 2",
        createdTime: new Date("2024-03-15T09:15:00Z").toISOString(),
        updatedTime: new Date("2024-03-19T16:45:00Z").toISOString(),
        projectId: populatedProject.id,
        projectName: populatedProject.name,
    },
    {
        id: "session-3",
        name: "Session 3",
        createdTime: new Date("2024-03-15T09:15:00Z").toISOString(),
        updatedTime: new Date("2024-03-19T16:45:00Z").toISOString(),
    },
];
