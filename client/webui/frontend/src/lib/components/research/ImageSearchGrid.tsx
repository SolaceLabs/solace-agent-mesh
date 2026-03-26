import React, { useState, useEffect, useRef } from "react";
import { ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";

interface ImageResult {
    imageUrl: string;
    title?: string;
    link: string;
}

interface ImageSearchGridProps {
    images: ImageResult[];
    maxVisible?: number;
}

const ImageSearchGrid: React.FC<ImageSearchGridProps> = ({ images, maxVisible = 6 }) => {
    const [selectedImageIndex, setSelectedImageIndex] = useState<number | null>(null);
    const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

    if (!images || images.length === 0) {
        return null;
    }

    const visibleImages = images.slice(0, maxVisible);
    const hasMore = images.length > maxVisible;

    const handleImageError = (imageUrl: string) => {
        setImageErrors(prev => new Set(prev).add(imageUrl));
    };

    const handleImageClick = (index: number) => {
        setSelectedImageIndex(index);
    };

    const handleCloseModal = () => {
        setSelectedImageIndex(null);
    };

    const handlePrevious = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (selectedImageIndex !== null && selectedImageIndex > 0) {
            setSelectedImageIndex(selectedImageIndex - 1);
        }
    };

    const handleNext = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (selectedImageIndex !== null && selectedImageIndex < images.length - 1) {
            setSelectedImageIndex(selectedImageIndex + 1);
        }
    };

    const selectedImage = selectedImageIndex !== null ? images[selectedImageIndex] : null;

    const dialogRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (selectedImageIndex !== null) {
            dialogRef.current?.focus();
        }
    }, [selectedImageIndex]);

    const handleDialogKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Escape") { handleCloseModal(); return; }
        if (e.key !== "Tab") return;
        const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
            'button, [href], [tabindex]:not([tabindex="-1"])'
        );
        if (!focusable || focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
            if (document.activeElement === first) { e.preventDefault(); last.focus(); }
        } else {
            if (document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
    };

    const getGridClass = () => {
        const count = visibleImages.length;
        if (count === 1) return "grid-cols-1";
        if (count === 2) return "grid-cols-2";
        return "grid-cols-2 md:grid-cols-3";
    };

    return (
        <>
            <div className="mt-2">
                <div className={`grid ${getGridClass()} gap-2`}>
                    {visibleImages.map((image, index) => {
                        const hasError = imageErrors.has(image.imageUrl);

                        return (
                            <div
                                key={image.imageUrl}
                                className="group relative aspect-video cursor-pointer overflow-hidden rounded-lg border border-(--secondary-w20) bg-(--secondary-w10) transition-all hover:border-(--primary-wMain)"
                                onClick={() => !hasError && handleImageClick(index)}
                                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (!hasError) handleImageClick(index); } }}
                                role="button"
                                tabIndex={0}
                            >
                                {!hasError ? (
                                    <>
                                        <img
                                            src={image.imageUrl}
                                            alt={image.title || `Image ${index + 1}`}
                                            className="h-full w-full object-cover transition-transform group-hover:scale-105"
                                            loading="lazy"
                                            onError={() => handleImageError(image.imageUrl)}
                                        />
                                        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100">
                                            <div className="absolute right-0 bottom-0 left-0 p-2">
                                                <p className="line-clamp-2 text-xs font-medium text-(--darkSurface-text)">{image.title || "View image"}</p>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div className="flex h-full w-full items-center justify-center text-(--secondary-text-wMain)">
                                        <span className="text-xs">Failed to load</span>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
                {hasMore && <p className="mt-2 text-xs text-(--secondary-text-wMain) italic">+{images.length - maxVisible} more images</p>}
            </div>

            {/* Image Modal with Navigation */}
            {selectedImage && selectedImageIndex !== null && (
                <div ref={dialogRef} className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4" role="dialog" aria-modal="true" aria-label={selectedImage?.title || "Image viewer"} onClick={handleCloseModal} onKeyDown={handleDialogKeyDown} tabIndex={-1}>
                    {/* Previous button */}
                    {selectedImageIndex > 0 && (
                        <button onClick={handlePrevious} className="absolute left-4 z-10 text-(--darkSurface-text) transition-colors hover:text-(--secondary-w40)" aria-label="Previous image">
                            <ChevronLeft className="h-12 w-12" />
                        </button>
                    )}

                    {/* Next button */}
                    {selectedImageIndex < images.length - 1 && (
                        <button onClick={handleNext} className="absolute right-4 z-10 text-(--darkSurface-text) transition-colors hover:text-(--secondary-w40)" aria-label="Next image">
                            <ChevronRight className="h-12 w-12" />
                        </button>
                    )}

                    {/* Image container */}
                    <div className="relative max-h-[90vh] max-w-[90vw] rounded-lg bg-(--background-w10) shadow-2xl" onClick={e => e.stopPropagation()}>
                        {/* Image */}
                        <img src={selectedImage.imageUrl} alt={selectedImage.title || "Image"} className="max-h-[80vh] max-w-full rounded-t-lg object-contain" />

                        {/* Image info */}
                        <div className="border-t border-(--secondary-w20) p-4">
                            <div className="flex items-center justify-between">
                                <div className="flex-1">
                                    {selectedImage.title && (
                                        <a href={selectedImage.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-(--info-wMain) hover:text-(--info-w100) hover:underline">
                                            {selectedImage.title}
                                            <ExternalLink className="h-3 w-3" />
                                        </a>
                                    )}
                                </div>
                                <span className="text-xs text-(--secondary-text-wMain)">
                                    {selectedImageIndex + 1} / {images.length}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};

export { ImageSearchGrid };
