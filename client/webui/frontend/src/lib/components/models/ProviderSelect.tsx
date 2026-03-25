import { ComboBox, type ComboBoxItem } from "@/lib/components/ui";
import { ModelProviderIcon } from "./ModelProviderIcon";
import type { ModelProvider } from "./modelProviderUtils";

interface ProviderSelectProps {
    value: string | undefined;
    onValueChange: (value: string) => void;
    providers: ModelProvider[];
    placeholder?: string;
    disabled?: boolean;
    invalid?: boolean;
}

export const ProviderSelect = ({ value, onValueChange, providers, placeholder, disabled, invalid }: ProviderSelectProps) => {
    // Convert ModelProvider to DropDownItem with icons and sections
    const dropDownItems: ComboBoxItem[] = providers.map(provider => ({
        id: provider.id,
        label: provider.label,
        icon: provider.id === "custom" ? undefined : <ModelProviderIcon provider={provider.id} size="xs" />,
        subtext: provider.id === "custom" ? "Configure a provider that implements the OpenAI-compatible API protocol (including LiteLLM-compatible endpoints)" : undefined,
        section: provider.id === "custom" ? "advanced" : "default",
    }));

    return <ComboBox value={value} onValueChange={onValueChange} items={dropDownItems} placeholder={placeholder || ""} disabled={disabled} invalid={invalid} />;
};
