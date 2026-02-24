import React from "react";
import solaceLogoFull from "@/assets/solace-logo-full.svg";
import solaceLogoShort from "@/assets/solace-logo-s.svg";

interface SolaceIconProps {
    className?: string;
    variant?: "full" | "short";
}

export const SolaceIcon: React.FC<SolaceIconProps> = ({ className, variant = "full" }) => {
    const logoSrc = variant === "short" ? solaceLogoShort : solaceLogoFull;

    return <img src={logoSrc} alt="Solace" className={className} />;
};
