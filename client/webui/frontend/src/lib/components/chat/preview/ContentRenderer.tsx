import React from "react";

import { AudioRenderer, CsvRenderer, DocxRenderer, HtmlRenderer, ImageRenderer, MarkdownRenderer, MermaidRenderer, PdfRenderer, PptxRenderer, StructuredDataRenderer, TextRenderer } from "./Renderers";
import type { RAGSearchResult } from "@/lib/types";

interface ContentRendererProps {
    content: string;
    rendererType: string;
    mime_type?: string;
    url?: string;
    filename?: string;
    setRenderError: (error: string | null) => void;
    isStreaming?: boolean;
    ragData?: RAGSearchResult;
}

export const ContentRenderer: React.FC<ContentRendererProps> = ({ content, rendererType, mime_type, url, filename, setRenderError, isStreaming, ragData }) => {
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
            return <MarkdownRenderer content={content} setRenderError={setRenderError} isStreaming={isStreaming} ragData={ragData} />;
        case "audio":
            return <AudioRenderer content={content} mime_type={mime_type} setRenderError={setRenderError} />;
        case "docx":
            return <DocxRenderer content={content} setRenderError={setRenderError} />;
        case "pptx":
            return <PptxRenderer content={content} setRenderError={setRenderError} />;
        case "pdf":
        case "application/pdf":
            if (url && filename) {
                return <PdfRenderer url={url} filename={filename} />;
            }
            setRenderError("URL and filename are required for PDF preview.");
            return null;
        default:
            return <TextRenderer content={content} setRenderError={setRenderError} isStreaming={isStreaming} />;
    }
};
