import React, { useMemo, useState } from "react";
import { Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/lib/components/ui";
import { ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AgentPickerSuggestion {
    name: string;
    reason: string;
}

interface AvailableAgent {
    name: string;
    displayName?: string;
    description?: string;
}

interface AgentPickerCardProps {
    prompt: string;
    suggestions: AgentPickerSuggestion[];
    allowOther: boolean;
    availableAgents: AvailableAgent[];
    resolvedAgentName?: string;
    onSelect: (agentName: string) => void;
}

const OTHER_VALUE = "__other__";

export const AgentPickerCard: React.FC<AgentPickerCardProps> = ({ prompt, suggestions, allowOther, availableAgents, resolvedAgentName, onSelect }) => {
    const suggestedNames = useMemo(() => new Set(suggestions.map(s => s.name)), [suggestions]);
    const otherAgents = useMemo(() => availableAgents.filter(a => !suggestedNames.has(a.name)), [availableAgents, suggestedNames]);
    const isResolved = !!resolvedAgentName;

    const initialOtherAgent = otherAgents[0]?.name ?? "";

    // If a previous selection resolved this picker to an agent that wasn't in
    // the suggestions, restore the radio to "Other" with that agent in the
    // dropdown so the UI matches the saved choice.
    const resolvedIsOther = isResolved && !!resolvedAgentName && !suggestedNames.has(resolvedAgentName);

    const [selectedRadio, setSelectedRadio] = useState<string>(() => {
        if (resolvedIsOther) return OTHER_VALUE;
        if (resolvedAgentName) return resolvedAgentName;
        return suggestions[0]?.name ?? (allowOther ? OTHER_VALUE : "");
    });
    const [otherSelected, setOtherSelected] = useState<string>(() => (resolvedIsOther ? resolvedAgentName! : initialOtherAgent));

    const displayNameFor = (name: string) => availableAgents.find(a => a.name === name)?.displayName || name;
    const descriptionFor = (suggestion: AgentPickerSuggestion) => suggestion.reason || availableAgents.find(a => a.name === suggestion.name)?.description || "";

    const chosenAgent = selectedRadio === OTHER_VALUE ? otherSelected : selectedRadio;
    const canSave = !!chosenAgent && !isResolved;

    const handleSave = () => {
        if (!canSave) return;
        onSelect(chosenAgent);
    };

    return (
        <div className="not-prose mt-3 rounded-lg border bg-(--background-w10) p-4">
            <p className="mb-3 text-sm font-medium text-(--primary-text-wMain)">{prompt}</p>
            <div role="radiogroup" className="space-y-2">
                {suggestions.map(suggestion => {
                    const isSelected = selectedRadio === suggestion.name;
                    return (
                        <label
                            key={suggestion.name}
                            className={cn("flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors", isSelected && "border-(--primary-wMain) bg-(--primary-w10)", isResolved && "cursor-default opacity-70")}
                        >
                            <input
                                type="radio"
                                name="agent-picker"
                                value={suggestion.name}
                                checked={isSelected}
                                disabled={isResolved}
                                onChange={() => setSelectedRadio(suggestion.name)}
                                className="mt-1 h-4 w-4 flex-shrink-0 cursor-pointer appearance-none rounded-full border-2 border-(--secondary-text-wMain) bg-transparent transition-colors checked:border-(--primary-wMain) checked:bg-(--primary-wMain) checked:shadow-[inset_0_0_0_3px_var(--background-w10)] disabled:cursor-not-allowed"
                            />
                            <div className="min-w-0 flex-1">
                                <a
                                    href={`#/agents?agent=${encodeURIComponent(suggestion.name)}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    onClick={e => e.stopPropagation()}
                                    className="inline-flex items-center gap-1 text-sm font-medium text-(--primary-wMain) hover:underline"
                                >
                                    {displayNameFor(suggestion.name)}
                                    <ExternalLink className="h-3 w-3" />
                                </a>
                                {descriptionFor(suggestion) && <p className="mt-1 text-xs text-(--secondary-text-wMain)">{descriptionFor(suggestion)}</p>}
                            </div>
                        </label>
                    );
                })}

                {allowOther && otherAgents.length > 0 && (
                    <label className={cn("flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors", selectedRadio === OTHER_VALUE && "border-(--primary-wMain) bg-(--primary-w10)", isResolved && "cursor-default opacity-70")}>
                        <input
                            type="radio"
                            name="agent-picker"
                            value={OTHER_VALUE}
                            checked={selectedRadio === OTHER_VALUE}
                            disabled={isResolved}
                            onChange={() => setSelectedRadio(OTHER_VALUE)}
                            className="h-4 w-4 flex-shrink-0 cursor-pointer appearance-none rounded-full border-2 border-(--secondary-text-wMain) bg-transparent transition-colors checked:border-(--primary-wMain) checked:bg-(--primary-wMain) checked:shadow-[inset_0_0_0_3px_var(--background-w10)] disabled:cursor-not-allowed"
                        />
                        <span className="flex-shrink-0 text-sm">Other</span>
                        <Select
                            value={otherSelected}
                            onValueChange={value => {
                                setOtherSelected(value);
                                setSelectedRadio(OTHER_VALUE);
                            }}
                            disabled={isResolved}
                        >
                            <SelectTrigger className="ml-auto max-w-[14rem] min-w-0 flex-1">
                                <SelectValue placeholder="Select an agent" />
                            </SelectTrigger>
                            <SelectContent>
                                {otherAgents.map(agent => (
                                    <SelectItem key={agent.name} value={agent.name}>
                                        {agent.displayName || agent.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </label>
                )}
            </div>
            <div className="mt-3 flex justify-end">
                <Button onClick={handleSave} disabled={!canSave} size="sm">
                    {isResolved ? "Saved" : "Save"}
                </Button>
            </div>
        </div>
    );
};
