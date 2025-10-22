import { useThemeContext } from "@/lib/hooks/useThemeContext";

interface ErrorIllustrationProps {
    width?: number;
    height?: number;
}

export function ErrorIllustration({ width = 24, height = 24 }: ErrorIllustrationProps) {
    const { currentTheme } = useThemeContext();

    const fill = currentTheme === "dark" ? "var(--color-background-wMain)" : "var(--color-background-w10)";
    const errorFill = currentTheme === "dark" ? "var(--color-error-w100)" : "var(--color-error-w10)";

    return (
        <svg width={width} height={height} focusable="false" aria-hidden="true" viewBox="0 0 131 131" fill="none">
            <path
                d="M119.681 63.9952C119.681 94.0948 95.2807 118.495 65.1812 118.495C35.0816 118.495 10.6812 94.0948 10.6812 63.9952C10.6812 33.8957 35.0816 9.49524 65.1812 9.49524C95.2807 9.49524 119.681 33.8957 119.681 63.9952Z"
                fill={errorFill}
            />
            <path d="M2.68115 119.495H128.681V120.495H2.68115V119.495Z" fill="var(--color-secondary-wMain)" />
            <rect x={14} y={34} width={104.054} height={70.6982} rx={1} fill={fill} stroke="var(--color-secondary-wMain)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            <path
                d="M59.4929 105.314C59.6018 104.866 60.0032 104.55 60.4646 104.55H72.4448C72.9061 104.55 73.3076 104.866 73.4165 105.314L75.1457 112.433C75.2986 113.062 74.8218 113.669 74.174 113.669H58.7354C58.0876 113.669 57.6107 113.062 57.7637 112.433L59.4929 105.314Z"
                fill={fill}
                stroke="var(--color-secondary-wMain)"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path
                d="M47.7852 114.103C47.7852 113.55 48.2329 113.103 48.7852 113.103H83.2724C83.8247 113.103 84.2724 113.55 84.2724 114.103V118.656C84.2724 119.208 83.8247 119.656 83.2724 119.656H48.7852C48.2329 119.656 47.7852 119.208 47.7852 118.656V114.103Z"
                fill={fill}
                stroke="var(--color-secondary-wMain)"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path d="M15.1406 95.0068H117.773" stroke="var(--color-secondary-wMain)" strokeWidth={2} />
            <g clipPath="url(#clip0_1688:196070)">
                <rect opacity={0.2} x={54.1126} y={45.1681} width={24.1} height={24.1} stroke="var(--color-secondary-wMain)" strokeWidth={0.1} />
                <path
                    d="M65.6426 60.1142C65.5359 60.1142 65.4453 60.0769 65.3706 60.0022C65.2959 59.9275 65.2586 59.8369 65.2586 59.7302V52.4022C65.2586 52.2955 65.2959 52.2049 65.3706 52.1302C65.4453 52.0555 65.5359 52.0182 65.6426 52.0182H66.9386C67.0559 52.0182 67.1466 52.0555 67.2106 52.1302C67.2853 52.1942 67.3226 52.2849 67.3226 52.4022V59.7302C67.3226 59.8369 67.2853 59.9275 67.2106 60.0022C67.1466 60.0769 67.0559 60.1142 66.9386 60.1142H65.6426ZM65.5466 63.2182C65.4399 63.2182 65.3493 63.1809 65.2746 63.1062C65.1999 63.0315 65.1626 62.9409 65.1626 62.8342V61.3462C65.1626 61.2289 65.1999 61.1329 65.2746 61.0582C65.3493 60.9835 65.4399 60.9462 65.5466 60.9462H67.0346C67.1519 60.9462 67.2479 60.9835 67.3226 61.0582C67.3973 61.1329 67.4346 61.2289 67.4346 61.3462V62.8342C67.4346 62.9409 67.3973 63.0315 67.3226 63.1062C67.2479 63.1809 67.1519 63.2182 67.0346 63.2182H65.5466Z"
                    fill="var(--color-secondary-wMain)"
                />
            </g>
            <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M51.3433 73.2659C51.3433 72.9897 51.5671 72.7659 51.8433 72.7659H80.2102C80.4864 72.7659 80.7102 72.9897 80.7102 73.2659C80.7102 73.542 80.4864 73.7659 80.2102 73.7659H51.8433C51.5671 73.7659 51.3433 73.542 51.3433 73.2659Z"
                fill="var(--color-secondary-wMain)"
            />
            <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M55.1851 83.2659C55.1851 82.9897 55.3503 82.7659 55.5542 82.7659H76.4995C76.7034 82.7659 76.8687 82.9897 76.8687 83.2659C76.8687 83.542 76.7034 83.7659 76.4995 83.7659H55.5542C55.3503 83.7659 55.1851 83.542 55.1851 83.2659Z"
                fill="var(--color-secondary-wMain)"
            />
            <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M51.3433 78.2659C51.3433 77.9897 51.5671 77.7659 51.8433 77.7659H80.2102C80.4864 77.7659 80.7102 77.9897 80.7102 78.2659C80.7102 78.542 80.4864 78.7659 80.2102 78.7659H51.8433C51.5671 78.7659 51.3433 78.542 51.3433 78.2659Z"
                fill="var(--color-secondary-wMain)"
            />
            <defs>
                <clipPath id="clip0_1688:196070">
                    <rect width={24} height={24} fill={fill} transform="translate(54.1626 45.2181)" />
                </clipPath>
            </defs>
        </svg>
    );
}
