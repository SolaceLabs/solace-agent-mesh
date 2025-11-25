import type { Prompt, PromptGroup } from "@/lib";

export const defaultVersions: Prompt[] = [
    {
        id: "prompt-1",
        promptText: "What is the weather in {{weather}}",
        groupId: "group-1",
        userId: "user-id",
        version: 1,
        createdAt: new Date().getMilliseconds(),
        updatedAt: new Date().getMilliseconds(),
    },
    {
        promptText: "get the weather for {{place}}",
        id: "prompt-2",
        groupId: "group-1",
        userId: "user-id",
        version: 2,
        createdAt: new Date().getMilliseconds(),
        updatedAt: new Date().getMilliseconds(),
    },
];

export const weatherProductionPrompt: Prompt = defaultVersions[1];
export const weatherPromptGroup: PromptGroup = {
    id: "group-1",
    name: "weather-group",
    userId: "user-id",
    description: "Prompt for getting weather",
    category: "Other",
    isShared: false,
    isPinned: false,
    createdAt: new Date().getMilliseconds(),
    updatedAt: new Date().getMilliseconds(),
    productionPromptId: weatherProductionPrompt.id,
    productionPrompt: weatherProductionPrompt,
};

export const languagePrompts: Prompt[] = [
    {
        id: "prompt-3",
        promptText: "What is {{word}} in french",
        groupId: "group-2",
        userId: "user-id",
        version: 1,
        createdAt: new Date().getMilliseconds(),
        updatedAt: new Date().getMilliseconds(),
    },
];
export const languageProductionPrompt = languagePrompts[0];
export const languagePromptGroup: PromptGroup = {
    id: "group-2",
    name: "language-group",
    userId: "user-id",
    description: "Prompt for translating from english to french",
    category: "Communication",
    isShared: false,
    isPinned: false,
    createdAt: new Date().getMilliseconds(),
    updatedAt: new Date().getMilliseconds(),
    productionPromptId: weatherProductionPrompt.id,
    productionPrompt: weatherProductionPrompt,
};

export const defaultPromptGroups: PromptGroup[] = [weatherPromptGroup, languagePromptGroup];
