import { useThemeContext } from "@/lib/hooks/useThemeContext";

interface WorkflowIllustrationProps {
    width?: number;
    height?: number;
    className?: string;
}

export function WorkflowIllustration({ width, height, className }: WorkflowIllustrationProps) {
    const { currentTheme } = useThemeContext();

    const cardBg = currentTheme === "dark" ? "var(--color-background-wMain)" : "var(--color-background-w10)";
    const cardBorder = "var(--color-secondary-wMain)";
    const textPrimary = "var(--foreground)";
    const textSecondary = "var(--color-secondary-wMain)";
    const iconBg = "var(--color-success-w10)";
    const iconColor = "var(--color-success-wMain)";
    const arrowColor = "var(--color-secondary-wMain)";
    const startBg = currentTheme === "dark" ? "var(--color-background-wMain)" : "var(--color-background-w10)";
    const mapColor = "var(--color-info-wMain)";

    return (
        <svg width={width} height={height} viewBox="0 0 900 1200" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} style={{ maxWidth: "100%", height: "auto" }}>
            {/* Definitions */}
            <defs>
                {/* Arrow marker */}
                <marker id="arrowhead" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
                    <path d="M 2 2 L 10 6 L 2 10 z" fill={arrowColor} />
                </marker>

                {/* Bot/Agent icon - detailed robot design */}
                <g id="bot-icon">
                    {/* Icon background */}
                    <rect x="0" y="0" width="28" height="28" rx="6" fill={iconBg} />
                    {/* Robot head */}
                    <rect x="8" y="10" width="12" height="10" rx="2" fill={iconColor} />
                    {/* Antenna */}
                    <line x1="14" y1="10" x2="14" y2="7" stroke={iconColor} strokeWidth="1.5" strokeLinecap="round" />
                    <circle cx="14" cy="6" r="1.5" fill={iconColor} />
                    {/* Eyes */}
                    <circle cx="11.5" cy="13.5" r="1" fill={cardBg} />
                    <circle cx="16.5" cy="13.5" r="1" fill={cardBg} />
                    {/* Mouth */}
                    <line x1="11" y1="17" x2="17" y2="17" stroke={cardBg} strokeWidth="1" strokeLinecap="round" />
                    {/* Body */}
                    <rect x="9" y="21" width="10" height="4" rx="1" fill={iconColor} />
                </g>
            </defs>

            {/* Start Node */}
            <g id="start-node">
                <rect x="360" y="30" width="180" height="64" rx="32" fill={startBg} stroke={cardBorder} strokeWidth="2" />
                {/* Play icon - clean triangle, centered */}
                <path d="M 408 48 L 408 76 L 428 62 Z" fill={textPrimary} opacity="0.8" />
                <text x="445" y="70" fontFamily="system-ui, -apple-system, sans-serif" fontSize="22" fontWeight="600" fill={textPrimary}>
                    Start
                </text>
            </g>

            {/* Arrow from Start to OrderValidator */}
            <line x1="450" y1="94" x2="450" y2="160" stroke={arrowColor} strokeWidth="2.5" markerEnd="url(#arrowhead)" />

            {/* OrderValidator Card */}
            <g id="order-validator">
                <rect x="250" y="160" width="400" height="80" rx="12" fill={cardBg} stroke={cardBorder} strokeWidth="2" filter="drop-shadow(0 1px 3px rgba(0, 0, 0, 0.1))" />
                <use href="#bot-icon" x="270" y="186" />
                <text x="315" y="210" fontFamily="system-ui, -apple-system, sans-serif" fontSize="20" fontWeight="600" fill={textPrimary}>
                    OrderValidator
                </text>
                <text x="585" y="210" fontFamily="system-ui, -apple-system, sans-serif" fontSize="16" fill={textSecondary} textAnchor="end">
                    Agent
                </text>
            </g>

            {/* Arrows from OrderValidator to parallel nodes */}
            <path d="M 450 240 Q 300 280 280 360" stroke={arrowColor} strokeWidth="2.5" fill="none" markerEnd="url(#arrowhead)" />
            <path d="M 450 240 Q 600 280 620 360" stroke={arrowColor} strokeWidth="2.5" fill="none" markerEnd="url(#arrowhead)" />

            {/* CustomerEnricher Card */}
            <g id="customer-enricher">
                <rect x="80" y="360" width="400" height="80" rx="12" fill={cardBg} stroke={cardBorder} strokeWidth="2" filter="drop-shadow(0 1px 3px rgba(0, 0, 0, 0.1))" />
                <use href="#bot-icon" x="100" y="386" />
                <text x="145" y="410" fontFamily="system-ui, -apple-system, sans-serif" fontSize="20" fontWeight="600" fill={textPrimary}>
                    CustomerEnricher
                </text>
                <text x="415" y="410" fontFamily="system-ui, -apple-system, sans-serif" fontSize="16" fill={textSecondary} textAnchor="end">
                    Agent
                </text>
            </g>

            {/* InventoryChecker Card */}
            <g id="inventory-checker">
                <rect x="520" y="360" width="400" height="80" rx="12" fill={cardBg} stroke={cardBorder} strokeWidth="2" filter="drop-shadow(0 1px 3px rgba(0, 0, 0, 0.1))" />
                <use href="#bot-icon" x="540" y="386" />
                <text x="585" y="410" fontFamily="system-ui, -apple-system, sans-serif" fontSize="20" fontWeight="600" fill={textPrimary}>
                    InventoryChecker
                </text>
                <text x="855" y="410" fontFamily="system-ui, -apple-system, sans-serif" fontSize="16" fill={textSecondary} textAnchor="end">
                    Agent
                </text>
            </g>

            {/* Arrows from parallel nodes to DiscountCalculator */}
            <path d="M 280 440 Q 380 480 450 540" stroke={arrowColor} strokeWidth="2.5" fill="none" markerEnd="url(#arrowhead)" />
            <path d="M 720 440 Q 520 480 450 540" stroke={arrowColor} strokeWidth="2.5" fill="none" markerEnd="url(#arrowhead)" />

            {/* DiscountCalculator Card */}
            <g id="discount-calculator">
                <rect x="250" y="540" width="400" height="80" rx="12" fill={cardBg} stroke={cardBorder} strokeWidth="2" filter="drop-shadow(0 1px 3px rgba(0, 0, 0, 0.1))" />
                <use href="#bot-icon" x="270" y="566" />
                <text x="315" y="590" fontFamily="system-ui, -apple-system, sans-serif" fontSize="20" fontWeight="600" fill={textPrimary}>
                    DiscountCalculator
                </text>
                <text x="585" y="590" fontFamily="system-ui, -apple-system, sans-serif" fontSize="16" fill={textSecondary} textAnchor="end">
                    Agent
                </text>
            </g>

            {/* Arrow from DiscountCalculator to Map */}
            <line x1="450" y1="620" x2="450" y2="710" stroke={arrowColor} strokeWidth="2.5" markerEnd="url(#arrowhead)" />

            {/* Map container box - positioned first so Map node can straddle it */}
            <rect x="200" y="740" width="500" height="200" rx="12" fill="none" stroke={mapColor} strokeWidth="2" strokeDasharray="8,4" opacity="0.5" />

            {/* Map Node - straddling the top of the container */}
            <g id="map-node">
                <rect x="360" y="710" width="180" height="60" rx="10" fill={cardBg} stroke={mapColor} strokeWidth="2" filter="drop-shadow(0 1px 3px rgba(0, 0, 0, 0.1))" />
                {/* Loop/refresh icon - two circular arrows forming a cycle */}
                <g transform="translate(385, 732)">
                    {/* Top curved arrow pointing right */}
                    <path d="M 2 6 C 2 3 4 1 7 1 C 10 1 12 3 12 6" stroke={mapColor} strokeWidth="1.8" fill="none" strokeLinecap="round" />
                    {/* Arrow head pointing down-right */}
                    <path d="M 10.5 4 L 12 6 L 10.5 8" stroke={mapColor} strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />

                    {/* Bottom curved arrow pointing left */}
                    <path d="M 12 10 C 12 13 10 15 7 15 C 4 15 2 13 2 10" stroke={mapColor} strokeWidth="1.8" fill="none" strokeLinecap="round" />
                    {/* Arrow head pointing up-left */}
                    <path d="M 3.5 12 L 2 10 L 3.5 8" stroke={mapColor} strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                </g>

                <text x="413" y="747" fontFamily="system-ui, -apple-system, sans-serif" fontSize="20" fontWeight="600" fill={mapColor}>
                    Map
                </text>

                {/* Expand/maximize icon - four arrows pointing outward */}
                <g transform="translate(493, 734)">
                    {/* Top-left to center diagonal */}
                    <path d="M 1 1 L 5 5" stroke={mapColor} strokeWidth="1.8" strokeLinecap="round" />
                    <path d="M 1 1 L 3 1 M 1 1 L 1 3" stroke={mapColor} strokeWidth="1.8" strokeLinecap="round" />

                    {/* Top-right to center diagonal */}
                    <path d="M 13 1 L 9 5" stroke={mapColor} strokeWidth="1.8" strokeLinecap="round" />
                    <path d="M 13 1 L 11 1 M 13 1 L 13 3" stroke={mapColor} strokeWidth="1.8" strokeLinecap="round" />

                    {/* Bottom-left to center diagonal */}
                    <path d="M 1 13 L 5 9" stroke={mapColor} strokeWidth="1.8" strokeLinecap="round" />
                    <path d="M 1 13 L 3 13 M 1 13 L 1 11" stroke={mapColor} strokeWidth="1.8" strokeLinecap="round" />

                    {/* Bottom-right to center diagonal */}
                    <path d="M 13 13 L 9 9" stroke={mapColor} strokeWidth="1.8" strokeLinecap="round" />
                    <path d="M 13 13 L 11 13 M 13 13 L 13 11" stroke={mapColor} strokeWidth="1.8" strokeLinecap="round" />
                </g>
            </g>

            {/* ItemProcessor Card (inside map) */}
            <g id="item-processor">
                <rect x="250" y="814" width="400" height="80" rx="12" fill={cardBg} stroke={cardBorder} strokeWidth="2" filter="drop-shadow(0 1px 3px rgba(0, 0, 0, 0.1))" />
                <use href="#bot-icon" x="270" y="840" />
                <text x="315" y="864" fontFamily="system-ui, -apple-system, sans-serif" fontSize="20" fontWeight="600" fill={textPrimary}>
                    ItemProcessor
                </text>
                <text x="585" y="864" fontFamily="system-ui, -apple-system, sans-serif" fontSize="16" fill={textSecondary} textAnchor="end">
                    Agent
                </text>
            </g>

            {/* Arrow from Map to PriceCalculator */}
            <line x1="450" y1="954" x2="450" y2="1024" stroke={arrowColor} strokeWidth="2.5" markerEnd="url(#arrowhead)" />

            {/* PriceCalculator Card */}
            <g id="price-calculator">
                <rect x="250" y="1024" width="400" height="80" rx="12" fill={cardBg} stroke={cardBorder} strokeWidth="2" filter="drop-shadow(0 1px 3px rgba(0, 0, 0, 0.1))" />
                <use href="#bot-icon" x="270" y="1050" />
                <text x="315" y="1074" fontFamily="system-ui, -apple-system, sans-serif" fontSize="20" fontWeight="600" fill={textPrimary}>
                    PriceCalculator
                </text>
                <text x="585" y="1074" fontFamily="system-ui, -apple-system, sans-serif" fontSize="16" fill={textSecondary} textAnchor="end">
                    Agent
                </text>
            </g>

            {/* Arrow from PriceCalculator continuing down */}
            <line x1="450" y1="1104" x2="450" y2="1164" stroke={arrowColor} strokeWidth="2.5" markerEnd="url(#arrowhead)" />
        </svg>
    );
}
