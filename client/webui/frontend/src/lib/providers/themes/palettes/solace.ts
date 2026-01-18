import type { ThemePalette } from "./themePalette";

export const solace: ThemePalette = {
    brand: {
        wMain: "#C9A962",      // Luxurious gold
        w30: "#E8D9B8",        // Light gold
        wMain30: "#C9A9624d",  // Gold with opacity
        w10: "#F7F3EB",        // Very light gold tint
        w60: "#D7BE8A",        // Medium gold
        w100: "#B08D4A",       // Deep gold
    },

    primary: {
        w100: "#3D3835",       // Deep warm brown
        w90: "#4F4A46",        // Dark warm gray
        wMain: "#625D58",      // Warm charcoal
        w60: "#948E88",        // Medium warm gray
        w40: "#B8B3AE",        // Light warm gray
        w20: "#D9D6D3",        // Very light warm gray
        w10: "#ECEAE8",        // Off-white with warm tint

        text: {
            wMain: "#3D3835",  // Deep warm brown for main text
            w100: "#2A2725",   // Almost black warm tone
            w10: "#D9D6D3",    // Light text on dark backgrounds
        },
    },

    secondary: {
        w70: "#6B6562",        // Medium warm gray
        w80: "#534F4C",        // Dark warm gray
        w8040: "#534F4C40",    // Dark warm gray with opacity
        w100: "#2A2725",       // Almost black warm tone
        wMain: "#8E8881",      // Warm stone gray
        w40: "#D4D0CC",        // Light warm gray
        w20: "#E8E5E2",        // Very light warm gray
        w10: "#F5F3F1",        // Off-white cream

        text: {
            wMain: "#625D58",  // Warm charcoal
            w50: "#B8B3AE",    // Light warm gray
        },
    },

    background: {
        w100: "#2A2725",       // Dark warm background
        wMain: "#3D3835",      // Dark warm background variant
        w20: "#FAF8F6",        // Luxurious off-white (main light background)
        w10: "#FFFEFD",        // Pure luxurious white
    },

    info: {
        w100: "#7E9CAF",       // Muted blue-gray
        wMain: "#A1BED0",      // Soft blue-gray
        w70: "#C4D8E5",        // Light blue-gray
        w30: "#DCE9F2",        // Very light blue-gray
        w20: "#E8F1F7",        // Pale blue-gray
        w10: "#F3F8FB",        // Almost white blue tint
    },

    error: {
        w100: "#A84B4A",       // Deep muted red
        wMain: "#C97270",      // Soft red
        w70: "#DCA5A4",        // Light red
        w30: "#EDD0CF",        // Very light red
        w20: "#F3E0E0",        // Pale red
        w10: "#F9F0F0",        // Almost white red tint
    },

    warning: {
        w100: "#B8884D",       // Deep amber
        wMain: "#D4A667",      // Soft amber
        w70: "#E4C79B",        // Light amber
        w30: "#F0DEC4",        // Very light amber
        w20: "#F5E9D9",        // Pale amber
        w10: "#FAF4ED",        // Almost white amber tint
    },

    success: {
        w100: "#6B8E7D",       // Deep sage green
        wMain: "#8BA898",      // Soft sage green
        w70: "#B0C8BB",        // Light sage green
        w30: "#D3E2D9",        // Very light sage green
        w20: "#E4EEE8",        // Pale sage green
        w10: "#F2F7F4",        // Almost white green tint
    },

    stateLayer: {
        w10: "#3D38351a",      // Warm overlay light
        w20: "#3D383533",      // Warm overlay medium
    },

    accent: {
        n0: {
            w100: "#8B7B9E",   // Muted purple
            wMain: "#A899B8",  // Soft purple
            w30: "#D7D0E0",    // Light purple
            w10: "#F1EEF5",    // Almost white purple tint
        },
        n1: {
            w100: "#6B6B7A",   // Muted blue-gray
            wMain: "#898999",  // Soft blue-gray
            w30: "#D1D1D9",    // Light blue-gray
            w60: "#ABABBB",    // Medium blue-gray
            w20: "#E3E3E8",    // Very light blue-gray
            w10: "#F1F1F4",    // Almost white blue-gray tint
        },
        n2: {
            w100: "#5D8A8C",   // Muted teal
            wMain: "#7FA9AB",  // Soft teal
            w30: "#C7DBDC",    // Light teal
            w20: "#DEEAEB",    // Very light teal
            w10: "#EFF5F5",    // Almost white teal tint
        },
        n3: {
            w100: "#8B7A9E",   // Muted lavender
            wMain: "#A899B8",  // Soft lavender
            w30: "#D7D0E0",    // Light lavender
            w10: "#F1EEF5",    // Almost white lavender tint
        },
        n4: {
            w100: "#B67C9E",   // Muted mauve
            wMain: "#CC99B8",  // Soft mauve
            w30: "#E9D9E0",    // Light mauve
        },
        n5: {
            w100: "#C68B7D",   // Muted terracotta
            wMain: "#D9A898",  // Soft terracotta
            w30: "#EED9D0",    // Light terracotta
            w60: "#E2BDB3",    // Medium terracotta
        },
        n6: {
            w100: "#C9A962",   // Gold (matches brand)
            wMain: "#D7BE8A",  // Light gold
            w30: "#EFE3CC",    // Very light gold
        },
        n7: {
            w100: "#7FB3CC",   // Muted sky blue
            wMain: "#A1C8D9",  // Soft sky blue
            w30: "#D6E8EF",    // Light sky blue
        },
        n8: {
            w100: "#7A7A7A",   // Warm gray
            wMain: "#999999",  // Medium warm gray
            w30: "#D9D9D9",    // Light warm gray
        },
        n9: {
            wMain: "#C97270",  // Soft red (accent)
        },
    },
    learning: {
        wMain: "#6B7A8E",      // Muted blue
        w90: "#5D6A7C",        // Dark blue
        w100: "#4F5A6B",       // Deep blue
        w20: "#D3D9E0",        // Light blue
        w10: "#E9EDF1",        // Very light blue
    },
};
