import type { ComboBoxItem } from "@/lib/components/ui/combobox";

export const comboBoxMockData = {
    basicItems: [
        { id: "option-1", label: "First Option" },
        { id: "option-2", label: "Second Option" },
        { id: "option-3", label: "Third Option" },
    ] as ComboBoxItem[],

    itemsWithSubtext: [
        { id: "python", label: "Python", subtext: "Python 3.11" },
        { id: "javascript", label: "JavaScript", subtext: "Node.js 20" },
        { id: "golang", label: "Go", subtext: "Go 1.21" },
    ] as ComboBoxItem[],

    itemsWithSections: [
        { id: "default-1", label: "Common Model", section: "default" as const },
        { id: "default-2", label: "General Purpose", section: "default" as const },
        { id: "advanced-1", label: "Specialized Model", section: "advanced" as const },
        { id: "advanced-2", label: "Research Model", section: "advanced" as const },
    ] as ComboBoxItem[],

    itemsWithImages: [
        { id: "openai", label: "OpenAI", subtext: "GPT-4, GPT-3.5" },
        { id: "anthropic", label: "Anthropic", subtext: "Claude models" },
        { id: "google", label: "Google", subtext: "Gemini, PaLM" },
    ] as ComboBoxItem[],
};
