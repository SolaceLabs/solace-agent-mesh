import { useState, useEffect } from "react";

interface ModelProviderIconProps {
    provider: string;
    size?: "sm" | "md";
}

const sizeConfig = {
    sm: {
        container: "h-8 w-8",
        margin: "mr-2",
        image: "h-7 w-7",
        text: "text-xs",
    },
    md: {
        container: "h-12 w-12",
        margin: "mr-4",
        image: "h-10 w-10",
        text: "text-sm",
    },
};

const providerIconMap: Record<string, string> = {
    anthropic: new URL("./assets/claude.svg", import.meta.url).href,
    openai: new URL("./assets/openai.svg", import.meta.url).href,
    openai_compatible: new URL("./assets/openai.svg", import.meta.url).href,
    google_ai_studio: new URL("./assets/google_ai_studio.svg", import.meta.url).href,
    vertex_ai: new URL("./assets/vertexai.svg", import.meta.url).href,
    azure_openai: new URL("./assets/azure_openai.svg", import.meta.url).href,
    bedrock: new URL("./assets/bedrock.svg", import.meta.url).href,
    ollama: new URL("./assets/ollama.svg", import.meta.url).href,
};

export const ModelProviderIcon = ({ provider, size = "md" }: ModelProviderIconProps) => {
    const [imageError, setImageError] = useState(false);
    const config = sizeConfig[size];
    const iconPath = providerIconMap[provider.toLowerCase()];

    useEffect(() => {
        setImageError(false);
    }, [provider]);

    if (!iconPath || imageError) {
        return (
            <div className={`${config.margin} bg-muted flex ${config.container} items-center justify-center rounded-full`}>
                <span className={`text-muted-foreground ${config.text} font-semibold`}>{provider.charAt(0).toUpperCase()}</span>
            </div>
        );
    }

    return (
        <div className={`${config.margin} flex ${config.container} items-center justify-center rounded-xs`}>
            <img src={iconPath} alt={provider} className={`${config.image} object-contain`} onError={() => setImageError(true)} />
        </div>
    );
};
