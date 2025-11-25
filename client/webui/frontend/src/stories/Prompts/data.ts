import type { Prompt, PromptGroup } from "@/lib";

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
    {
        promptText: "get the weather for {{place}}",
        id: "prompt-2",
        groupId: "group-id",
        userId: "user-id",
        version: 2,
        createdAt: new Date().getMilliseconds(),
        updatedAt: new Date().getMilliseconds(),
    },
];

export const productionPrompt: Prompt = defaultVersions[1];
export const defaultPromptGroup: PromptGroup = {
    id: "group-id",
    name: "my-group",
    userId: "user-id",
    description: "Prompt for getting weather",
    isShared: false,
    isPinned: false,
    createdAt: new Date().getMilliseconds(),
    updatedAt: new Date().getMilliseconds(),
    productionPromptId: productionPrompt.id,
    productionPrompt,
};

export const defaultPromptGroups: PromptGroup[] = [defaultPromptGroup];
