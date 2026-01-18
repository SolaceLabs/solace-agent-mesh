import React, { useState, useEffect } from "react";
import { useConfigContext } from "@/lib/hooks/useConfigContext";
import meshFlowLogo from "@/assets/meshFlow_logo.jpg";

const LOGO_URL_STORAGE_KEY = "webui_logo_url";

const HEADER_ICON = (
    <div className="flex h-full items-center justify-center overflow-hidden rounded-full">
        <img src={meshFlowLogo} alt="MeshFlow Logo" className="h-full w-full object-contain" />
    </div>
);

interface NavigationHeaderProps {
    onClick?: () => void;
}

export const NavigationHeader: React.FC<NavigationHeaderProps> = ({ onClick }) => {
    const config = useConfigContext();
    const [imageError, setImageError] = useState(false);
    const [logoUrl, setLogoUrl] = useState<string>("");

    // Load cached logo URL immediately on mount for instant display
    useEffect(() => {
        try {
            const cachedLogoUrl = localStorage.getItem(LOGO_URL_STORAGE_KEY);
            if (cachedLogoUrl) {
                setLogoUrl(cachedLogoUrl);
            }
        } catch (err) {
            console.warn("Failed to read cached logo URL from localStorage:", err);
        }
    }, []);

    // Update logo URL when config changes (after API call completes)
    useEffect(() => {
        if (config.configLogoUrl !== undefined) {
            setLogoUrl(config.configLogoUrl);
            try {
                localStorage.setItem(LOGO_URL_STORAGE_KEY, config.configLogoUrl);
            } catch (error) {
                console.error("Failed to save logo URL to localStorage:", error);
            }
            // Reset image error state when logo URL changes
            setImageError(false);
        }
    }, [config.configLogoUrl]);

    const shouldShowCustomLogo = logoUrl && !imageError;

    return (
        <div className="flex h-full w-20 cursor-pointer items-center justify-center" onClick={onClick}>
            {shouldShowCustomLogo ? (
                <div className="flex h-12 w-12 items-center justify-center overflow-hidden">
                    <img src={logoUrl} alt="Logo" className="h-full w-full object-contain" onError={() => setImageError(true)} />
                </div>
            ) : (
                HEADER_ICON
            )}
        </div>
    );
};
