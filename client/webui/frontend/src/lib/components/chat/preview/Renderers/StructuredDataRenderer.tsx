import React, { useEffect, useMemo, useState } from "react";

import { Code, Eye } from "lucide-react";
import yaml from "js-yaml";

import { Button, JSONViewer } from "@/lib/components";

import type { BaseRendererProps } from ".";

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
        <div className="flex min-h-0 max-w-[100vw] flex-col">
            <div className="bg-background relative flex-1 overflow-auto">
                <Button variant={"default"} onClick={() => setShowRawTextView(!showRawTextView)} className="absolute top-4 right-4 z-10" title={showRawTextView ? "Show Structured View" : "Show Raw Text"}>
                    {showRawTextView ? (
                        <>
                            <Eye className="mr-1 h-3.5 w-3.5" /> Structured
                        </>
                    ) : (
                        <>
                            <Code className="mr-1 h-3.5 w-3.5" /> Raw Text
                        </>
                    )}
                </Button>
                {showRawTextView ? (
                    <div className="p-4 border overflow-auto">
                        <pre className="whitespace-pre-wrap" style={{
                                overflowWrap: "anywhere",
                            }}
                        >{rawData}</pre>
                    </div>
                ) : (
                    <JSONViewer data={parsedData} maxDepth={4} className="p-2 rounded-none" />
                )}
            </div>
        </div>
    );
};
