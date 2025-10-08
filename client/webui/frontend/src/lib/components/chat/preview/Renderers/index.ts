/**
 * Base properties expected by all content renderers (HTML, Mermaid, etc.).
 */
export interface BaseRendererProps {
    content: string; // Raw content to render
    rendererType?: string; // Optional, for structured data renderers
    mime_type?: string; // Optional MIME type for specific renderers
    setRenderError: (error: string | null) => void; // Function to set error state
}

export { AudioRenderer } from "./AudioRenderer";
export { CsvRenderer } from "./CsvRenderer";
export { HtmlRenderer } from "./HTMLRenderer";
export { ImageRenderer } from "./ImageRenderer";
export { MarkdownRenderer } from "./MarkdownRenderer";
export { MermaidRenderer } from "./MermaidRenderer";
export { StructuredDataRenderer } from "./StructuredDataRenderer";
export { TextRenderer } from "./TextRenderer";
