import { useCallback, useEffect, useRef, useState } from "react";
import { useGesture } from "@use-gesture/react";
import { Scan } from "lucide-react";
import mermaid from "mermaid";

import { Button } from "@/lib/components/ui";
import { getErrorMessage } from "@/lib/utils";

import type { BaseRendererProps } from ".";

/** Validate Mermaid input for potentially dangerous patterns */
const validateMermaidInput = (input: string): boolean => {
    const dangerousPatterns = [
        /<script/i, // Script tags
        /javascript:/i, // JavaScript protocol
        /on\w+\s*=/i, // Event handlers (onclick, onerror, etc.)
        /<iframe/i, // Iframes
        /<object/i, // Object embeds
        /<embed/i, // Embed tags
        /data:text\/html/i, // Data URLs with HTML
    ];

    return !dangerousPatterns.some(pattern => pattern.test(input));
};

/** Module-level counter to ensure unique render IDs */
let globalRenderCount = 0;

/** Serialize mermaid.render() calls */
let renderQueue: Promise<void> = Promise.resolve();
/** Initialize mermaid once */
let mermaidInitialized = false;

function initializeMermaid() {
    if (mermaidInitialized) return;
    mermaidInitialized = true;

    mermaid.initialize({
        startOnLoad: false,
        theme: "default",
        secure: ["theme", "themeCSS"],
        fontFamily: "arial, sans-serif",
        logLevel: "error" as const,
        securityLevel: "strict",
        maxTextSize: 50000,
    });
}

export const MermaidRenderer = ({ content, setRenderError }: BaseRendererProps) => {
    const [svgHtml, setSvgHtml] = useState<string>("");
    const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });

    const containerRef = useRef<HTMLDivElement>(null);
    const svgContainerRef = useRef<HTMLDivElement>(null);
    const offscreenRef = useRef<HTMLDivElement>(null);

    const resetTransform = useCallback(() => {
        setTransform({ x: 0, y: 0, scale: 1 });
    }, []);

    useEffect(() => {
        let cancelled = false;
        const renderId = `mermaid-${++globalRenderCount}`;

        const renderDiagram = async () => {
            if (!content.trim()) {
                setSvgHtml("");
                return;
            }

            setRenderError(null);

            if (!validateMermaidInput(content)) {
                setRenderError("Invalid diagram content: potentially unsafe patterns detected");
                setSvgHtml("");
                return;
            }

            // Serialize renders because mermaid's parser/renderer uses global state
            const ticket = renderQueue.then(async () => {
                if (cancelled) return;

                initializeMermaid();

                try {
                    const { svg, bindFunctions } = await mermaid.render(renderId, content, offscreenRef.current ?? undefined);

                    if (!cancelled) {
                        setSvgHtml(svg);
                        setRenderError(null);

                        if (offscreenRef.current) {
                            offscreenRef.current.innerHTML = "";
                        }

                        if (bindFunctions) {
                            requestAnimationFrame(() => {
                                if (svgContainerRef.current && !cancelled) {
                                    bindFunctions(svgContainerRef.current);
                                }
                            });
                        }
                    }
                } catch (error) {
                    if (!cancelled) {
                        setRenderError(getErrorMessage(error, "Failed to render diagram"));
                        setSvgHtml("");
                    }
                }
            });

            renderQueue = ticket.catch(() => {});
        };

        renderDiagram();

        return () => {
            cancelled = true;
        };
    }, [content, setRenderError]);

    // Make the SVG responsive after it's inserted into the DOM
    useEffect(() => {
        const svgEl = svgContainerRef.current?.querySelector("svg");
        if (!svgEl) return;

        if (!svgEl.getAttribute("viewBox")) {
            const w = svgEl.width.baseVal.value;
            const h = svgEl.height.baseVal.value;
            if (w && h) {
                svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
            }
        }

        svgEl.removeAttribute("width");
        svgEl.removeAttribute("height");
        svgEl.style.width = "auto";
        svgEl.style.height = "auto";
        svgEl.style.maxWidth = "100%";
        svgEl.style.maxHeight = "100%";
        svgEl.setAttribute("preserveAspectRatio", "xMidYMid meet");
    }, [svgHtml]);

    // Reset when svgHtml changes
    useEffect(() => {
        resetTransform();
    }, [resetTransform, svgHtml]);

    // Zoom via native wheel listener
    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;

        const onWheel = (e: WheelEvent) => {
            e.preventDefault();
            const rect = el.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;

            setTransform(prev => {
                const newScale = Math.min(10, Math.max(0.1, prev.scale - e.deltaY * 0.001));
                const ratio = newScale / prev.scale;
                const x = mx - (mx - prev.x) * ratio;
                const y = my - (my - prev.y) * ratio;
                return { x, y, scale: newScale };
            });
        };

        el.addEventListener("wheel", onWheel, { passive: false });
        return () => el.removeEventListener("wheel", onWheel);
    }, []);

    // Pan via drag gesture
    const bind = useGesture(
        {
            onDrag: ({ offset: [x, y] }) => {
                setTransform(prev => ({ ...prev, x, y }));
            },
        },
        {
            drag: {
                from: () => [transform.x, transform.y],
            },
        }
    );

    return (
        <div className="flex h-full min-w-0 flex-col overflow-hidden rounded-sm p-4">
            <div ref={offscreenRef} aria-hidden style={{ position: "fixed", top: -10000, left: -10000, width: 1920, height: 1080 }} />
            <div ref={containerRef} className="bg-muted relative flex w-full items-start justify-center overflow-hidden p-2" style={{ touchAction: "none" }} {...bind()}>
                {svgHtml ? (
                    <div
                        ref={svgContainerRef}
                        className="mt-16 flex max-h-full w-full cursor-grab items-start justify-center active:cursor-grabbing"
                        style={{
                            transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
                            transformOrigin: "0 0",
                        }}
                    >
                        <div className="flex max-h-full w-full items-center justify-center rounded-sm bg-(--color-background) p-4 dark:bg-(--color-background-w20)" dangerouslySetInnerHTML={{ __html: svgHtml }} />
                    </div>
                ) : null}

                <div className="bg-background absolute top-3 right-3 flex items-center gap-2 rounded-sm p-1">
                    <Button onClick={resetTransform} tooltip="Reset View" variant="ghost">
                        <Scan />
                    </Button>
                    <div className="h-6 w-px border-l" />
                    <div className="text-muted-foreground pr-2 text-xs">Drag to pan and scroll to zoom</div>
                </div>
            </div>
        </div>
    );
};
