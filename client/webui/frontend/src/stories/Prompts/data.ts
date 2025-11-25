import type { Prompt, PromptGroup } from "@/lib";

export const defaultPromptGroup: PromptGroup = {
    id: "group-id",
    name: "my-group",
    userId: "user-id",
    productionPromptId: "prod-id",
    isShared: false,
    isPinned: false,
    createdAt: new Date().getMilliseconds(),
    updatedAt: new Date().getMilliseconds(),
};

export const defaultVersions: Prompt[] = [
    {
        id: "prompt-1",
        promptText: "What is the weather in {{weather}}",
        groupId: "group-id",
        userId: "user-id",
        version: 1,
        createdAt: new Date().getMilliseconds(),
        updatedAt: new Date().getMilliseconds(),
    },
];
