import React from "react";

import { 
    AudioRenderer, 
    CsvRenderer, 
    HtmlRenderer, 
    ImageRenderer, 
    MarkdownRenderer, 
    MermaidRenderer, 
    StructuredDataRenderer 
} from "./Renderers";

interface ContentRendererProps {
    content: string;
    rendererType: string;
    mime_type?: string;
    setRenderError: (error: string | null) => void;
}

export const ContentRenderer: React.FC<ContentRendererProps> = ({ content, rendererType, mime_type, setRenderError }) => {

    // Delegate to the appropriate renderer based on rendererType
    switch (rendererType) {
        case "csv":
            return <CsvRenderer content={content} setRenderError={setRenderError} />;
        case "mermaid":
            return <MermaidRenderer content={content} setRenderError={setRenderError} />;
        case "html":
            return <HtmlRenderer content={content} setRenderError={setRenderError} />;
        case "json":
        case "yaml":
            return <StructuredDataRenderer content={content} rendererType={rendererType} setRenderError={setRenderError} />;
        case "image":
            return <ImageRenderer content={content} mime_type={mime_type} setRenderError={setRenderError} />;
        case "markdown":
            return <MarkdownRenderer content={content} setRenderError={setRenderError} />;
        case "audio":
            return <AudioRenderer content={content} mime_type={mime_type} setRenderError={setRenderError} />;
        default:
            return (
                <div className="p-4 overflow-auto">
                    <pre className="whitespace-pre-wrap" style={{
                        overflowWrap: "anywhere"
                    }}>{content}</pre>
                </div>
            );
    }
};
