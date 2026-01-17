import React, { useState, useEffect } from "react";
import { FileType, Loader2, ChevronLeft, ChevronRight, Play, Pause, ZoomIn, ZoomOut, Maximize2, RotateCcw } from "lucide-react";
import DOMPurify from "dompurify";

interface PptxRendererProps {
    content: string;
    setRenderError: (error: string | null) => void;
}

interface ZipContent {
    files: Record<string, unknown>;
    file: (path: string) => { async: (type: string) => Promise<string> } | null;
}

// Function to extract slide content from PPTX zip structure
const extractSlidesFromPptx = async (zipContent: ZipContent): Promise<string[]> => {
    const slides: string[] = [];

    try {
        // Get the presentation.xml file to understand the slide structure
        const presentationXml = await zipContent.file("ppt/presentation.xml")?.async("text");

        if (!presentationXml) {
            console.warn("Could not find presentation.xml in PPTX file");
            return slides;
        }

        // Parse the presentation XML to find slide references
        const parser = new DOMParser();
        const presentationDoc = parser.parseFromString(presentationXml, "text/xml");
        const slideIds = presentationDoc.querySelectorAll("p\\:sldId, sldId");

        // Extract content from each slide
        for (let i = 0; i < slideIds.length; i++) {
            const slideNum = i + 1;
            const slideXmlPath = `ppt/slides/slide${slideNum}.xml`;

            try {
                const slideXml = await zipContent.file(slideXmlPath)?.async("text");
                if (slideXml) {
                    const slideContent = parseSlideXml(slideXml);
                    slides.push(slideContent);
                }
            } catch (error) {
                console.warn(`Could not extract slide ${slideNum}:`, error);
                slides.push(`
                    <div class="slide-content">
                        <h2>Slide ${slideNum}</h2>
                        <p>Content could not be extracted from this slide.</p>
                    </div>
                `);
            }
        }

        // If no slides were found, try to find slide files directly
        if (slides.length === 0) {
            const slideFiles = Object.keys(zipContent.files).filter(name => name.startsWith("ppt/slides/slide") && name.endsWith(".xml"));

            for (const slideFile of slideFiles) {
                try {
                    const slideXml = await zipContent.file(slideFile)?.async("text");
                    if (slideXml) {
                        const slideContent = parseSlideXml(slideXml);
                        slides.push(slideContent);
                    }
                } catch (error) {
                    console.warn(`Could not extract ${slideFile}:`, error);
                }
            }
        }
    } catch (error) {
        console.error("Error extracting slides from PPTX:", error);
    }

    return slides;
};

// Function to parse individual slide XML and extract text content with table detection
const parseSlideXml = (slideXml: string): string => {
    try {
        const parser = new DOMParser();
        const slideDoc = parser.parseFromString(slideXml, "text/xml");

        // Check for table elements first
        const tableElements = slideDoc.querySelectorAll("a\\:tbl, tbl");

        if (tableElements.length > 0) {
            // This slide contains tables - parse them specially
            return parseSlideWithTables(slideDoc);
        }

        // Extract all text content from the slide
        const textElements = slideDoc.querySelectorAll("a\\:t, t");
        const textContent: string[] = [];

        textElements.forEach(element => {
            const text = element.textContent?.trim();
            if (text) {
                textContent.push(text);
            }
        });

        // Try to identify titles vs content based on position or formatting
        let title = "";
        let content: string[] = [];

        if (textContent.length > 0) {
            // First text element is likely the title
            title = textContent[0];
            content = textContent.slice(1);
        }

        // Create HTML structure
        let slideHtml = '<div class="slide-content">';

        if (title) {
            slideHtml += `<h2>${escapeHtml(title)}</h2>`;
        }

        if (content.length > 0) {
            // Check if content looks like a formatted table (has | separators and ─ lines)
            const joinedContent = content.join("\n");
            if (joinedContent.includes("|") && joinedContent.includes("─")) {
                slideHtml += parseFormattedTableText(joinedContent);
            } else {
                // Regular content processing
                content.forEach(text => {
                    if (text.includes("\n")) {
                        // Multi-line content - treat as separate paragraphs
                        const lines = text.split("\n").filter(line => line.trim());
                        lines.forEach(line => {
                            slideHtml += `<p>${escapeHtml(line.trim())}</p>`;
                        });
                    } else {
                        slideHtml += `<p>${escapeHtml(text)}</p>`;
                    }
                });
            }
        }

        slideHtml += "</div>";
        return slideHtml;
    } catch (error) {
        console.error("Error parsing slide XML:", error);
        return `
            <div class="slide-content">
                <h2>Slide Content</h2>
                <p>Could not parse slide content.</p>
            </div>
        `;
    }
};

// Function to parse slides that contain actual PowerPoint table elements
const parseSlideWithTables = (slideDoc: Document): string => {
    let slideHtml = '<div class="slide-content">';

    // Extract title from title placeholder
    const titleElements = slideDoc.querySelectorAll("p\\:sp[type='title'] a\\:t, sp[type='title'] t");
    if (titleElements.length > 0) {
        const title = titleElements[0].textContent?.trim();
        if (title) {
            slideHtml += `<h2>${escapeHtml(title)}</h2>`;
        }
    }

    // Extract table data
    const tableElements = slideDoc.querySelectorAll("a\\:tbl, tbl");

    tableElements.forEach(tableElement => {
        const rows = tableElement.querySelectorAll("a\\:tr, tr");

        if (rows.length > 0) {
            slideHtml += '<table class="pptx-table">';

            rows.forEach((row, rowIndex) => {
                const cells = row.querySelectorAll("a\\:tc, tc");
                const isHeader = rowIndex === 0;

                slideHtml += "<tr>";
                cells.forEach(cell => {
                    const cellText = cell.textContent?.trim() || "";
                    const tag = isHeader ? "th" : "td";
                    slideHtml += `<${tag}>${escapeHtml(cellText)}</${tag}>`;
                });
                slideHtml += "</tr>";
            });

            slideHtml += "</table>";
        }
    });

    slideHtml += "</div>";
    return slideHtml;
};

// Function to parse formatted table text (from our custom table formatting)
const parseFormattedTableText = (text: string): string => {
    const lines = text.split("\n").filter(line => line.trim());

    if (lines.length < 2) {
        return `<p>${escapeHtml(text)}</p>`;
    }

    let tableHtml = '<table class="pptx-table">';
    let isFirstRow = true;

    for (const line of lines) {
        if (line.includes("─")) {
            // Skip separator lines
            continue;
        }

        if (line.includes("|")) {
            const cells = line
                .split("|")
                .map(cell => cell.trim())
                .filter(cell => cell);

            if (cells.length > 0) {
                tableHtml += "<tr>";
                cells.forEach(cellText => {
                    const tag = isFirstRow ? "th" : "td";
                    tableHtml += `<${tag}>${escapeHtml(cellText)}</${tag}>`;
                });
                tableHtml += "</tr>";
                isFirstRow = false;
            }
        }
    }

    tableHtml += "</table>";
    return tableHtml;
};

// Helper function to escape HTML
const escapeHtml = (text: string): string => {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
};

export const PptxRenderer: React.FC<PptxRendererProps> = ({ content, setRenderError }) => {
    const [slides, setSlides] = useState<string[]>([]);
    const [currentSlide, setCurrentSlide] = useState<number>(0);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [conversionError, setConversionError] = useState<string | null>(null);
    const [isPlaying, setIsPlaying] = useState<boolean>(false);
    const [zoomLevel, setZoomLevel] = useState<number>(1);
    const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
    const [panX, setPanX] = useState<number>(0);
    const [panY, setPanY] = useState<number>(0);
    const [isDragging, setIsDragging] = useState<boolean>(false);
    const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

    useEffect(() => {
        const convertPptxToHtml = async () => {
            try {
                setIsLoading(true);
                setConversionError(null);
                setRenderError(null);

                // Import JSZip dynamically
                const JSZip = await import("jszip");

                // Convert base64 content to ArrayBuffer
                const binaryString = atob(content);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }

                // Parse PPTX file using JSZip
                const zip = new JSZip.default();
                const zipContent = await zip.loadAsync(bytes.buffer);

                // Extract slide content
                const extractedSlides = await extractSlidesFromPptx(zipContent as unknown as ZipContent);

                if (extractedSlides.length > 0) {
                    setSlides(extractedSlides);
                } else {
                    setSlides([
                        `<div class="slide-content">
                            <h1>PowerPoint Presentation</h1>
                            <p>This PPTX file has been successfully loaded.</p>
                            <p>Content extraction is in progress...</p>
                        </div>`,
                    ]);
                }
                setCurrentSlide(0);
            } catch (error) {
                console.error("Error converting PPTX to HTML:", error);
                setConversionError(error instanceof Error ? error.message : "Unknown conversion error");
                setRenderError("Failed to convert PPTX file for preview");
            } finally {
                setIsLoading(false);
            }
        };

        if (content) {
            convertPptxToHtml();
        }
    }, [content, setRenderError]);

    // Auto-advance slides in presentation mode
    useEffect(() => {
        if (isPlaying && slides.length > 0) {
            const timer = setInterval(() => {
                setCurrentSlide(prev => (prev + 1) % slides.length);
            }, 5000);
            return () => clearInterval(timer);
        }
    }, [isPlaying, slides.length]);

    // Keyboard navigation
    useEffect(() => {
        const handleKeyPress = (event: KeyboardEvent) => {
            if (event.key === "ArrowRight" || event.key === " ") {
                nextSlide();
            } else if (event.key === "ArrowLeft") {
                prevSlide();
            } else if (event.key === "Escape") {
                setIsPlaying(false);
                setIsFullscreen(false);
            } else if (event.key === "f" || event.key === "F") {
                toggleFullscreen();
            }
        };

        window.addEventListener("keydown", handleKeyPress);
        return () => window.removeEventListener("keydown", handleKeyPress);
    }, []);

    const nextSlide = () => {
        setCurrentSlide(prev => (prev + 1) % slides.length);
        resetPan();
    };

    const prevSlide = () => {
        setCurrentSlide(prev => (prev - 1 + slides.length) % slides.length);
        resetPan();
    };

    const goToSlide = (index: number) => {
        setCurrentSlide(index);
        resetPan();
    };

    const togglePlayback = () => {
        setIsPlaying(!isPlaying);
    };

    const zoomIn = () => {
        setZoomLevel(prev => Math.min(prev + 0.25, 2));
    };

    const zoomOut = () => {
        setZoomLevel(prev => Math.max(prev - 0.25, 0.5));
        if (zoomLevel <= 1) resetPan();
    };

    const toggleFullscreen = () => {
        setIsFullscreen(!isFullscreen);
    };

    const resetZoom = () => {
        setZoomLevel(1);
        resetPan();
    };

    const resetPan = () => {
        setPanX(0);
        setPanY(0);
    };

    // Mouse event handlers for pan and zoom
    const handleMouseDown = (event: React.MouseEvent) => {
        if (zoomLevel > 1) {
            setIsDragging(true);
            setDragStart({
                x: event.clientX - panX,
                y: event.clientY - panY,
            });
            event.preventDefault();
        }
    };

    const handleMouseMove = (event: React.MouseEvent) => {
        if (isDragging && zoomLevel > 1) {
            setPanX(event.clientX - dragStart.x);
            setPanY(event.clientY - dragStart.y);
        }
    };

    const handleMouseUp = () => {
        setIsDragging(false);
    };

    const handleWheel = (event: React.WheelEvent) => {
        event.preventDefault();
        const delta = event.deltaY > 0 ? -0.1 : 0.1;
        const newZoom = Math.max(0.5, Math.min(2, zoomLevel + delta));
        setZoomLevel(newZoom);

        if (newZoom <= 1) {
            resetPan();
        }
    };

    if (isLoading) {
        return (
            <div className="flex h-64 flex-col items-center justify-center space-y-4 text-center">
                <Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
                <div>
                    <h3 className="text-lg font-semibold">Converting Presentation</h3>
                    <p className="text-muted-foreground">Converting PPTX file to HTML for preview...</p>
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
                    <p className="text-muted-foreground">Unable to convert PPTX file for preview.</p>
                    <p className="text-muted-foreground mt-2 text-sm">Download the file to open it in Microsoft PowerPoint or a compatible application.</p>
                    <p className="mt-2 text-xs text-red-500">Error: {conversionError}</p>
                </div>
            </div>
        );
    }

    if (slides.length === 0) {
        return (
            <div className="flex h-64 flex-col items-center justify-center space-y-4 text-center">
                <FileType className="text-muted-foreground h-16 w-16" />
                <div>
                    <h3 className="text-lg font-semibold">Empty Presentation</h3>
                    <p className="text-muted-foreground">The PPTX file appears to be empty or contains no readable slides.</p>
                </div>
            </div>
        );
    }

    const slideContent = (
        <>
            <div
                className="slide-viewport"
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                style={{
                    cursor: zoomLevel > 1 ? (isDragging ? "grabbing" : "grab") : "default",
                }}
            >
                <div
                    className="slide-container"
                    style={{
                        transform: `scale(${zoomLevel}) translate(${panX / zoomLevel}px, ${panY / zoomLevel}px)`,
                        transformOrigin: "center center",
                    }}
                >
                    <div
                        dangerouslySetInnerHTML={{
                            __html: DOMPurify.sanitize(slides[currentSlide], {
                                ALLOWED_TAGS: ["div", "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "strong", "em", "br", "table", "thead", "tbody", "tr", "th", "td"],
                                ALLOWED_ATTR: ["class"],
                            }),
                        }}
                    />
                    <div className="slide-number">
                        {currentSlide + 1} / {slides.length}
                    </div>
                </div>
            </div>

            <div className="controls">
                <button onClick={prevSlide} disabled={slides.length <= 1} className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
                    <ChevronLeft className="h-4 w-4" />
                    Previous
                </button>

                <button onClick={togglePlayback} className="flex items-center gap-2 rounded bg-slate-600 px-4 py-2 text-white hover:bg-slate-700">
                    {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    {isPlaying ? "Pause" : "Play"}
                </button>

                <button onClick={zoomOut} disabled={zoomLevel <= 0.5} className="flex items-center gap-2 rounded bg-slate-500 px-3 py-2 text-white hover:bg-slate-600 disabled:cursor-not-allowed disabled:opacity-50" title="Zoom Out">
                    <ZoomOut className="h-4 w-4" />
                </button>

                <button onClick={resetZoom} className="rounded bg-slate-500 px-3 py-2 text-sm text-white hover:bg-slate-600" title="Reset Zoom & Pan">
                    <RotateCcw className="mr-1 h-3 w-3" />
                    {Math.round(zoomLevel * 100)}%
                </button>

                <button onClick={zoomIn} disabled={zoomLevel >= 2} className="flex items-center gap-2 rounded bg-slate-500 px-3 py-2 text-white hover:bg-slate-600 disabled:cursor-not-allowed disabled:opacity-50" title="Zoom In">
                    <ZoomIn className="h-4 w-4" />
                </button>

                <button onClick={toggleFullscreen} className="flex items-center gap-2 rounded bg-slate-700 px-3 py-2 text-white hover:bg-slate-800" title="Toggle Fullscreen (F key)">
                    <Maximize2 className="h-4 w-4" />
                </button>

                <button onClick={nextSlide} disabled={slides.length <= 1} className="flex items-center gap-2 rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
                    Next
                    <ChevronRight className="h-4 w-4" />
                </button>
            </div>

            <div className="slide-indicator">
                {slides.map((_, index) => (
                    <div key={index} className={`slide-dot ${index === currentSlide ? "active" : ""}`} onClick={() => goToSlide(index)} />
                ))}
            </div>

            <div className="mt-2 text-center text-sm text-gray-300">Mouse wheel to zoom • Drag to pan when zoomed • Arrow keys to navigate • F for fullscreen</div>
        </>
    );

    const styles = `
        .pptx-preview-container {
            background: #1a1a1a;
            padding: 1rem;
            color: white;
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        
        .slide-viewport {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            margin-bottom: 1rem;
            min-height: 400px;
            border-radius: 8px;
            background: #2a2a2a;
        }
        
        .slide-container {
            width: 800px;
            height: 450px;
            background: white;
            color: #333;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 3rem;
            position: relative;
            transition: transform 0.2s ease;
            user-select: none;
        }
        
        .fullscreen-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: #1a1a1a;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 2rem;
            cursor: pointer;
        }
        
        .fullscreen-overlay > * {
            cursor: default;
        }
        
        .slide-content {
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            text-align: center;
        }
        
        .slide-content h1 {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 2rem;
            color: #1e40af;
        }
        
        .slide-content h2 {
            font-size: 2.5rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            color: #1d4ed8;
        }
        
        .slide-content h3 {
            font-size: 2rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #1e40af;
        }
        
        .slide-content p {
            font-size: 1.5rem;
            line-height: 1.6;
            margin-bottom: 1rem;
        }
        
        .slide-content ul {
            font-size: 1.25rem;
            text-align: left;
            max-width: 600px;
            margin: 0 auto;
        }
        
        .slide-content li {
            margin-bottom: 0.75rem;
            line-height: 1.5;
        }
        
        .slide-content strong {
            color: #1e40af;
            font-weight: 600;
        }
        
        .pptx-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem auto;
            font-size: 1.25rem;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .pptx-table th {
            background: #1e40af;
            color: white;
            font-weight: bold;
            padding: 1rem;
            text-align: center;
            border: 1px solid #1d4ed8;
        }
        
        .pptx-table td {
            padding: 0.75rem 1rem;
            text-align: center;
            border: 1px solid #e5e7eb;
        }
        
        .pptx-table tr:nth-child(even) td {
            background: #f8f9fa;
        }
        
        .pptx-table tr:nth-child(odd) td {
            background: white;
        }
        
        .controls {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 0.75rem;
            flex-wrap: wrap;
            flex-shrink: 0;
            margin-bottom: 0.5rem;
        }
        
        .slide-indicator {
            display: flex;
            gap: 0.5rem;
            justify-content: center;
            flex-shrink: 0;
            margin-bottom: 0.5rem;
        }
        
        .slide-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .slide-dot.active {
            background: white;
        }
        
        .slide-number {
            position: absolute;
            bottom: 1rem;
            right: 1rem;
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-size: 0.875rem;
        }
        
        @media (max-width: 768px) {
            .slide-container {
                width: 600px;
                height: 337px;
                padding: 2rem;
            }
            
            .slide-content h1 {
                font-size: 2rem;
            }
            
            .slide-content h2 {
                font-size: 1.75rem;
            }
            
            .slide-content p {
                font-size: 1.25rem;
            }
            
            .slide-content ul {
                font-size: 1.125rem;
            }
            
            .controls {
                gap: 0.5rem;
            }
        }
    `;

    // Handle click on fullscreen overlay background to close
    const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
        // Only close if clicking directly on the overlay background, not on child elements
        if (event.target === event.currentTarget) {
            setIsFullscreen(false);
        }
    };

    if (isFullscreen) {
        return (
            <div className="fullscreen-overlay" onClick={handleOverlayClick}>
                <style>{styles}</style>
                {slideContent}
            </div>
        );
    }

    return (
        <div className="pptx-preview-container max-w-none">
            <style>{styles}</style>
            {slideContent}
        </div>
    );
};
