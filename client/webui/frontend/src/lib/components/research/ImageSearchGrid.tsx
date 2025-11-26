import React, { useState } from "react";
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
                                key={index}
                                className="group hover:border-primary dark:hover:border-primary relative aspect-video cursor-pointer overflow-hidden rounded-lg border border-gray-200 bg-gray-100 transition-all dark:border-gray-700 dark:bg-gray-800"
                                onClick={() => !hasError && handleImageClick(index)}
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
                                                <p className="line-clamp-2 text-xs font-medium text-white">{image.title || "View image"}</p>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div className="flex h-full w-full items-center justify-center text-gray-400 dark:text-gray-600">
                                        <span className="text-xs">Failed to load</span>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
                {hasMore && <p className="mt-2 text-xs text-gray-500 italic dark:text-gray-400">+{images.length - maxVisible} more images</p>}
            </div>

            {/* Image Modal with Navigation */}
            {selectedImage && selectedImageIndex !== null && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4" onClick={handleCloseModal}>
                    {/* Previous button */}
                    {selectedImageIndex > 0 && (
                        <button onClick={handlePrevious} className="absolute left-4 z-10 text-white transition-colors hover:text-gray-300" aria-label="Previous image">
                            <ChevronLeft className="h-12 w-12" />
                        </button>
                    )}

                    {/* Next button */}
                    {selectedImageIndex < images.length - 1 && (
                        <button onClick={handleNext} className="absolute right-4 z-10 text-white transition-colors hover:text-gray-300" aria-label="Next image">
                            <ChevronRight className="h-12 w-12" />
                        </button>
                    )}

                    {/* Image container */}
                    <div className="relative max-h-[90vh] max-w-[90vw] rounded-lg bg-white shadow-2xl dark:bg-gray-800" onClick={e => e.stopPropagation()}>
                        {/* Image */}
                        <img src={selectedImage.imageUrl} alt={selectedImage.title || "Image"} className="max-h-[80vh] max-w-full rounded-t-lg object-contain" />

                        {/* Image info */}
                        <div className="border-t border-gray-200 p-4 dark:border-gray-700">
                            <div className="flex items-center justify-between">
                                <div className="flex-1">
                                    {selectedImage.title && (
                                        <a
                                            href={selectedImage.link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline dark:text-blue-400 dark:hover:text-blue-300"
                                        >
                                            {selectedImage.title}
                                            <ExternalLink className="h-3 w-3" />
                                        </a>
                                    )}
                                </div>
                                <span className="text-xs text-gray-500 dark:text-gray-400">
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
