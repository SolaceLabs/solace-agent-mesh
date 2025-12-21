import React, { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/lib/components/ui";

interface MermaidDiagramModalProps {
    isOpen: boolean;
    onClose: () => void;
    mermaidSource: string;
    title: string;
}

export const MermaidDiagramModal: React.FC<MermaidDiagramModalProps> = ({ isOpen, onClose, mermaidSource, title }) => {
    const mermaidRef = useRef<HTMLDivElement>(null);
    const [renderError, setRenderError] = useState<string | null>(null);
    const [isRendering, setIsRendering] = useState(false);

    useEffect(() => {
        console.log('[MermaidDiagramModal] useEffect triggered:', { isOpen, hasMermaidSource: !!mermaidSource, hasRef: !!mermaidRef.current });

        if (!isOpen || !mermaidSource) {
            console.log('[MermaidDiagramModal] Skipping render - modal not open or no source');
            return;
        }

        // Use a small delay to ensure the DOM is ready
        const timer = setTimeout(() => {
            if (!mermaidRef.current) {
                console.log('[MermaidDiagramModal] Ref not ready yet');
                return;
            }

            setIsRendering(true);
            setRenderError(null);

            // Detect dark mode
            const isDarkMode = document.documentElement.classList.contains('dark');
            console.log('[MermaidDiagramModal] Dark mode detected:', isDarkMode);

            // Initialize mermaid with theme-appropriate configuration
            mermaid.initialize({
                startOnLoad: false,
                theme: isDarkMode ? "dark" : "default",
                securityLevel: "loose",
                flowchart: {
                    useMaxWidth: true,
                    htmlLabels: true,
                    curve: "basis",
                },
                themeVariables: isDarkMode ? {
                    primaryColor: '#3b82f6',
                    primaryTextColor: '#e5e7eb',
                    primaryBorderColor: '#60a5fa',
                    lineColor: '#9ca3af',
                    secondaryColor: '#1e40af',
                    tertiaryColor: '#1e3a8a',
                    background: '#1f2937',
                    mainBkg: '#374151',
                    secondBkg: '#4b5563',
                    nodeBorder: '#6b7280',
                    clusterBkg: '#111827',
                    clusterBorder: '#4b5563',
                    titleColor: '#f3f4f6',
                    edgeLabelBackground: '#374151',
                    nodeTextColor: '#f3f4f6',
                } : {},
            });

            // Render the diagram
            const renderDiagram = async () => {
                try {
                    // Clear previous content
                    if (mermaidRef.current) {
                        mermaidRef.current.innerHTML = '';
                    }

                    const uniqueId = `mermaid-${Date.now()}`;
                    console.log('[MermaidDiagramModal] Rendering diagram:', mermaidSource.substring(0, 100));

                    const { svg } = await mermaid.render(uniqueId, mermaidSource);

                    console.log('[MermaidDiagramModal] Got SVG, length:', svg.length);

                    if (mermaidRef.current) {
                        mermaidRef.current.innerHTML = svg;
                        console.log('[MermaidDiagramModal] Diagram rendered successfully');
                    }
                    setIsRendering(false);
                } catch (error) {
                    console.error("[MermaidDiagramModal] Error rendering mermaid diagram:", error);
                    const errorMessage = error instanceof Error ? error.message : "Unknown error";
                    setRenderError(errorMessage);
                    setIsRendering(false);
                }
            };

            renderDiagram();
        }, 100);

        return () => clearTimeout(timer);
    }, [isOpen, mermaidSource]);

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-4xl w-[90vw] max-h-[90vh]" showCloseButton>
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    <DialogDescription>
                        Workflow visualization showing the structure and flow of nodes
                    </DialogDescription>
                </DialogHeader>
                <div className="scrollbar-themed overflow-auto max-h-[calc(90vh-8rem)] p-4 rounded">
                    {isRendering && (
                        <div className="flex justify-center items-center min-h-[200px]">
                            <div className="text-sm text-muted-foreground">Rendering diagram...</div>
                        </div>
                    )}
                    {renderError && (
                        <div className="text-red-500 p-4 border border-red-300 dark:border-red-700 rounded bg-red-50 dark:bg-red-950">
                            <strong>Error rendering diagram:</strong> {renderError}
                            <pre className="mt-2 text-xs overflow-auto">{mermaidSource}</pre>
                        </div>
                    )}
                    <div ref={mermaidRef} className="flex justify-center items-center min-h-[200px]" />
                </div>
            </DialogContent>
        </Dialog>
    );
};
