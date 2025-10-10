import React, { useEffect, useMemo, useState } from "react";

import { Code, Eye } from "lucide-react";
import yaml from "js-yaml";

import { Button, JSONViewer } from "@/lib/components";

import { TextRenderer, type BaseRendererProps } from ".";

interface StructuredDataRendererProps extends BaseRendererProps {
    rendererType: "json" | "yaml";
}

export const StructuredDataRenderer: React.FC<StructuredDataRendererProps> = ({ content, rendererType, setRenderError }) => {
    const [showRawTextView, setShowRawTextView] = useState(false);

    useEffect(() => {
        setRenderError(null);
    }, [content, setRenderError]);

    const [rawData, parsedData] = useMemo(() => {
        try {
            if (rendererType === "yaml") {
                const parsedYaml = yaml.load(content);
                return [content, parsedYaml];
            } else if (rendererType === "json") {
                const parsedJson = JSON.parse(content);
                return [JSON.stringify(parsedJson, null, 2), parsedJson];
            }

            throw new Error(`Unsupported renderer type: ${rendererType}`);
        } catch (e) {
            const errorType = rendererType === "yaml" ? "YAML" : "JSON";
            console.error(`Error parsing ${errorType} for panel:`, e);
            const errorData = {
                [`${errorType}_Parsing_Error`]: `The provided content is not valid ${errorType}.`,
                Details: (e as Error).message,
                Content_Snippet: content.substring(0, 500) + (content.length > 500 ? "..." : ""),
            };
            setRenderError(`${errorType} parsing failed: ${(e as Error).message}`);
            return [content, errorData];
        }
    }, [content, rendererType, setRenderError]);

    return (
        <div className="bg-background relative flex h-full flex-col overflow-hidden">
            <div className="absolute top-4 right-4 z-10">
                <Button onClick={() => setShowRawTextView(!showRawTextView)} title={showRawTextView ? "Show Structured View" : "Show Raw Text"}>
                    {showRawTextView ? (
                        <>
                            <Eye /> Structured
                        </>
                    ) : (
                        <>
                            <Code /> Raw Text
                        </>
                    )}
                </Button>
            </div>
            <div className="flex min-h-0 flex-col">
                <div className="flex-1 overflow-auto">{showRawTextView ? <TextRenderer content={rawData} setRenderError={setRenderError} /> : <JSONViewer data={parsedData} maxDepth={4} className="min-h-16 border-none p-2" />}</div>
            </div>
        </div>
    );
};
