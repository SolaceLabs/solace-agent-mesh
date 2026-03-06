import { useCallback, useEffect, useRef, useState } from "react";
import { useGesture } from "@use-gesture/react";
import { Scan } from "lucide-react";
import mermaid from "mermaid";

import { Button } from "@/lib/components/ui";
import { useThemeContext } from "@/lib/hooks/useThemeContext";
import { getErrorMessage } from "@/lib/utils";

import type { BaseRendererProps } from ".";

/**
 * Validates Mermaid input for potentially dangerous patterns
 * Provides defense-in-depth by catching obvious attacks before Mermaid processing
 */
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

export const MermaidRenderer = ({ content, setRenderError }: BaseRendererProps) => {
    const { currentTheme } = useThemeContext();

    const [svgHtml, setSvgHtml] = useState<string>("");
    const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });

    const containerRef = useRef<HTMLDivElement>(null);
    const svgContainerRef = useRef<HTMLDivElement>(null);
    const offscreenRef = useRef<HTMLDivElement>(null);
    const renderCountRef = useRef(0);

    // Initialize Mermaid once when theme changes
    useEffect(() => {
        const styles = getComputedStyle(document.documentElement);
        const cssVar = (name: string) => styles.getPropertyValue(name).trim();

        mermaid.initialize({
            startOnLoad: false,
            theme: "base",
            themeVariables: {
                background: cssVar("--background"),
                primaryColor: cssVar("--primary"),
                primaryTextColor: cssVar("--foreground"),
                primaryBorderColor: cssVar("--border"),
                secondaryColor: cssVar("--secondary"),
                tertiaryColor: cssVar("--muted"),
                lineColor: cssVar("--muted-foreground"),
                textColor: cssVar("--foreground"),
                mainBkg: cssVar("--card"),
                nodeBorder: cssVar("--border"),
            },
            secure: ["theme", "themeCSS"], // Prevent injection via theme configs
            fontFamily: "arial, sans-serif",
            logLevel: "error" as const,
            securityLevel: "strict",
            maxTextSize: 50000, // Prevent DoS with extremely large diagrams
        });
    }, [currentTheme]);

    useEffect(() => {
        let cancelled = false;
        // Unique ID per render call — avoids collisions in React strict mode
        const renderId = `mermaid-${++renderCountRef.current}`;

        const renderDiagram = async () => {
            if (!content.trim()) {
                setSvgHtml("");
                return;
            }

            setRenderError(null);

            // Validate input for dangerous patterns
            if (!validateMermaidInput(content)) {
                setRenderError("Invalid diagram content: potentially unsafe patterns detected");
                setSvgHtml("");
                return;
            }

            try {
                const { svg, bindFunctions } = await mermaid.render(renderId, content, offscreenRef.current ?? undefined);

                if (!cancelled) {
                    setSvgHtml(svg);
                    setRenderError(null);

                    // Clean up the off-screen render container to prevent DOM node leaks
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
        };

        renderDiagram();

        return () => {
            cancelled = true;
        };
    }, [content, currentTheme, setRenderError]);

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

    // Reset transform to initial view
    const resetTransform = useCallback(() => {
        setTransform({ x: 0, y: 0, scale: 1 });
    }, []);

    // Reset transform when content changes
    useEffect(() => {
        setTransform({ x: 0, y: 0, scale: 1 });
    }, [svgHtml]);

    // Zoom via native wheel listener (must be non-passive to preventDefault)
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
        <div className="bg-background flex h-full min-w-0 flex-col overflow-hidden p-4">
            <div ref={offscreenRef} aria-hidden style={{ position: "fixed", top: -10000, left: -10000, width: 1920, height: 1080 }} />
            <div ref={containerRef} className="relative flex min-h-96 w-full flex-1 items-start justify-center overflow-hidden" style={{ touchAction: "none" }} {...bind()}>
                {svgHtml ? (
                    <div
                        ref={svgContainerRef}
                        className="flex max-h-full w-full cursor-grab items-start justify-center pt-16 active:cursor-grabbing"
                        style={{
                            transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
                            transformOrigin: "0 0",
                        }}
                        dangerouslySetInnerHTML={{ __html: svgHtml }}
                    />
                ) : null}

                <div className="bg-muted absolute top-0 right-3 flex items-center gap-2 rounded">
                    <Button onClick={resetTransform} tooltip="Reset View" variant="ghost">
                        <Scan />
                    </Button>
                    <div className="h-6 w-px border-l" />
                    <div className="text-muted-foreground text-xs">Drag to pan</div>
                    <div className="h-6 w-px border-l" />
                    <div className="text-muted-foreground pr-2 text-xs">Scroll to zoom</div>
                </div>
            </div>
        </div>
    );
};
