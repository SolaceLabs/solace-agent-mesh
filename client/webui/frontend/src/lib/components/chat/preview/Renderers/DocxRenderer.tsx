import React, { useState, useEffect } from "react";
import { FileType, Loader2 } from "lucide-react";
import DOMPurify from "dompurify";

interface DocxRendererProps {
    content: string;
    setRenderError: (error: string | null) => void;
}

export const DocxRenderer: React.FC<DocxRendererProps> = ({ content, setRenderError }) => {
    const [htmlContent, setHtmlContent] = useState<string>("");
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [conversionError, setConversionError] = useState<string | null>(null);

    useEffect(() => {
        const convertDocxToHtml = async () => {
            try {
                setIsLoading(true);
                setConversionError(null);
                setRenderError(null);

                // Import mammoth dynamically
                const mammoth = await import("mammoth");

                // Convert base64 content to ArrayBuffer
                // Clean the base64 string by removing any whitespace and newlines
                const cleanedContent = content.replace(/\s/g, "");

                // Validate base64 string
                const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/;
                if (!base64Regex.test(cleanedContent)) {
                    throw new Error("Invalid base64 content: contains invalid characters");
                }

                let binaryString: string;
                try {
                    binaryString = atob(cleanedContent);
                } catch (atobError) {
                    console.error("atob decoding failed:", atobError);
                    throw new Error(`Failed to decode base64 content: ${atobError instanceof Error ? atobError.message : "Unknown error"}`);
                }

                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }

                // Convert DOCX to HTML with enhanced options to preserve formatting
                const result = await mammoth.convertToHtml(
                    {
                        arrayBuffer: bytes.buffer,
                    } as Parameters<typeof mammoth.convertToHtml>[0],
                    {
                        styleMap: [
                            "p[style-name='Heading 1'] => h1:fresh",
                            "p[style-name='Heading 2'] => h2:fresh",
                            "p[style-name='Heading 3'] => h3:fresh",
                            "p[style-name='Heading 4'] => h4:fresh",
                            "p[style-name='Heading 5'] => h5:fresh",
                            "p[style-name='Heading 6'] => h6:fresh",
                            "p[style-name='Title'] => h1.title:fresh",
                            "p[style-name='Subtitle'] => h2.subtitle:fresh",
                            "r[style-name='Strong'] => strong",
                            "r[style-name='Emphasis'] => em",
                        ],
                        // Preserve inline formatting like colors, fonts, etc.
                        includeDefaultStyleMap: true,
                        // Convert images if present
                        convertImage: mammoth.images.imgElement(function (image: { read: (encoding: string) => Promise<string>; contentType: string }) {
                            return image.read("base64").then(function (imageBuffer: string) {
                                return {
                                    src: "data:" + image.contentType + ";base64," + imageBuffer,
                                };
                            });
                        }),
                    }
                );

                // Sanitize the HTML content
                const sanitizedHtml = DOMPurify.sanitize(result.value, {
                    ALLOWED_TAGS: ["p", "br", "strong", "em", "u", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table", "thead", "tbody", "tr", "td", "th", "blockquote", "pre", "code", "span", "div", "a", "img"],
                    ALLOWED_ATTR: ["href", "src", "alt", "title", "style", "class"],
                });

                setHtmlContent(sanitizedHtml);

                // Log any conversion messages/warnings
                if (result.messages && result.messages.length > 0) {
                    console.warn("DOCX conversion messages:", result.messages);
                }
            } catch (error) {
                console.error("Error converting DOCX to HTML:", error);
                setConversionError(error instanceof Error ? error.message : "Unknown conversion error");
                setRenderError("Failed to convert DOCX file for preview");
            } finally {
                setIsLoading(false);
            }
        };

        if (content) {
            convertDocxToHtml();
        }
    }, [content, setRenderError]);

    if (isLoading) {
        return (
            <div className="flex h-64 flex-col items-center justify-center space-y-4 text-center">
                <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
                <div>
                    <h3 className="text-lg font-semibold">Converting Document</h3>
                    <p className="text-muted-foreground">Converting DOCX file to HTML for preview...</p>
                </div>
            </div>
        );
    }

    if (conversionError) {
        return (
            <div className="flex h-64 flex-col items-center justify-center space-y-4 text-center">
                <FileType className="text-muted-foreground h-16 w-16" />
                <div>
                    <h3 className="text-lg font-semibold">Conversion Failed</h3>
                    <p className="text-muted-foreground">Unable to convert DOCX file for preview.</p>
                    <p className="text-muted-foreground mt-2 text-sm">Download the file to open it in Microsoft Word or a compatible application.</p>
                    <p className="mt-2 text-xs text-red-500">Error: {conversionError}</p>
                </div>
            </div>
        );
    }

    if (!htmlContent) {
        return (
            <div className="flex h-64 flex-col items-center justify-center space-y-4 text-center">
                <FileType className="text-muted-foreground h-16 w-16" />
                <div>
                    <h3 className="text-lg font-semibold">Empty Document</h3>
                    <p className="text-muted-foreground">The DOCX file appears to be empty or contains no readable content.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="docx-preview-container max-w-none">
            <style>{`
                .docx-preview-container {
                    background: #f5f5f5;
                    padding: 2rem;
                    min-height: 100vh;
                }
                
                .dark .docx-preview-container {
                    background: #1f2937;
                }
                
                .docx-content {
                    font-family: 'Calibri', 'Segoe UI', system-ui, -apple-system, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 8.5in;
                    min-height: 11in;
                    margin: 0 auto;
                    padding: 1in;
                    background: white;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    border-radius: 4px;
                    page-break-inside: avoid;
                }
                
                .dark .docx-content {
                    background: #374151;
                    color: #e5e7eb;
                }
                
                @media print {
                    .docx-preview-container {
                        background: white;
                        padding: 0;
                    }
                    .docx-content {
                        box-shadow: none;
                        border-radius: 0;
                        max-width: none;
                        margin: 0;
                        padding: 1in;
                    }
                }
                
                /* Preserve inline styles from mammoth while providing fallbacks */
                .docx-content h1 {
                    font-size: 1.875rem;
                    font-weight: 700;
                    margin: 1.5rem 0 1rem 0;
                    border-bottom: 2px solid #e5e7eb;
                    padding-bottom: 0.5rem;
                }
                .docx-content h1:not([style*="color"]) {
                    color: #2563eb;
                }
                .dark .docx-content h1:not([style*="color"]) {
                    color: #60a5fa;
                }
                .docx-content h1.title {
                    font-size: 2.25rem;
                    text-align: center;
                    border-bottom: 3px solid #3b82f6;
                }
                .docx-content h1.title:not([style*="color"]) {
                    color: #1e40af;
                }
                .dark .docx-content h1.title:not([style*="color"]) {
                    color: #93c5fd;
                }
                
                .docx-content h2 {
                    font-size: 1.5rem;
                    font-weight: 600;
                    margin: 1.25rem 0 0.75rem 0;
                }
                .docx-content h2:not([style*="color"]) {
                    color: #1d4ed8;
                }
                .dark .docx-content h2:not([style*="color"]) {
                    color: #93c5fd;
                }
                .docx-content h2.subtitle {
                    font-size: 1.25rem;
                    text-align: center;
                    font-style: italic;
                }
                .docx-content h2.subtitle:not([style*="color"]) {
                    color: #4338ca;
                }
                .dark .docx-content h2.subtitle:not([style*="color"]) {
                    color: #a5b4fc;
                }
                
                .docx-content h3 {
                    font-size: 1.25rem;
                    font-weight: 600;
                    margin: 1rem 0 0.5rem 0;
                }
                .docx-content h3:not([style*="color"]) {
                    color: #1e40af;
                }
                .dark .docx-content h3:not([style*="color"]) {
                    color: #93c5fd;
                }
                
                .docx-content h4 {
                    font-size: 1.125rem;
                    font-weight: 600;
                    margin: 0.875rem 0 0.5rem 0;
                }
                .docx-content h4:not([style*="color"]) {
                    color: #3730a3;
                }
                .dark .docx-content h4:not([style*="color"]) {
                    color: #a5b4fc;
                }
                
                .docx-content h5 {
                    font-size: 1rem;
                    font-weight: 600;
                    margin: 0.75rem 0 0.5rem 0;
                }
                .docx-content h5:not([style*="color"]) {
                    color: #4338ca;
                }
                .dark .docx-content h5:not([style*="color"]) {
                    color: #c4b5fd;
                }
                
                .docx-content h6 {
                    font-size: 0.875rem;
                    font-weight: 600;
                    margin: 0.75rem 0 0.5rem 0;
                }
                .docx-content h6:not([style*="color"]) {
                    color: #5b21b6;
                }
                .dark .docx-content h6:not([style*="color"]) {
                    color: #c4b5fd;
                }
                
                .docx-content p {
                    margin: 0.75rem 0;
                    text-align: justify;
                }
                
                .docx-content strong {
                    font-weight: 700;
                }
                .docx-content strong:not([style*="color"]) {
                    color: #1f2937;
                }
                .dark .docx-content strong:not([style*="color"]) {
                    color: #f3f4f6;
                }
                
                .docx-content em {
                    font-style: italic;
                }
                .docx-content em:not([style*="color"]) {
                    color: #374151;
                }
                .dark .docx-content em:not([style*="color"]) {
                    color: #d1d5db;
                }
                
                .docx-content ul, .docx-content ol {
                    margin: 0.75rem 0;
                    padding-left: 1.5rem;
                }
                .docx-content li {
                    margin: 0.25rem 0;
                }
                
                .docx-content table {
                    width: 100%;
                    border-collapse: collapse;
                    margin: 1rem 0;
                }
                .docx-content th, .docx-content td {
                    border: 1px solid #d1d5db;
                    padding: 0.5rem;
                    text-align: left;
                }
                .dark .docx-content th, .dark .docx-content td {
                    border-color: #4b5563;
                }
                .docx-content th {
                    background-color: #f3f4f6;
                    font-weight: 600;
                }
                .dark .docx-content th {
                    background-color: #4b5563;
                }
                
                .docx-content blockquote {
                    border-left: 4px solid #3b82f6;
                    padding-left: 1rem;
                    margin: 1rem 0;
                    font-style: italic;
                    color: #4b5563;
                }
                .dark .docx-content blockquote {
                    color: #9ca3af;
                }
                
                /* Support for images */
                .docx-content img {
                    max-width: 100%;
                    height: auto;
                    margin: 1rem 0;
                    border-radius: 4px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }
            `}</style>
            <div className="docx-content" dangerouslySetInnerHTML={{ __html: htmlContent }} />
        </div>
    );
};
