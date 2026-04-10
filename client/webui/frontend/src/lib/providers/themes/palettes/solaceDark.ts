import type { ThemePalette, ThemeDefinition } from "./themePalette";

export const solaceDark: ThemePalette = {
    brand: {
        wMain: "#00c895",
        wMain30: "#00c895B3",
        w30: "#005248",
        w10: "#10332d",
        w60: "#00ad93",
        w100: "#66debf",
    },

    primary: {
        w100: "#66c7e5",
        w90: "#33b8e0",
        wMain: "#0892ce",
        w60: "#016489",
        w40: "#015470",
        w20: "#013a52",
        w10: "#00293b",

        text: {
            wMain: "#f5f5f5",
            w100: "#f5f5f5",
            w10: "#05172b",
        },
    },

    secondary: {
        w70: "#c5ced9",
        w80: "#d1d8e1",
        w8040: "#00000066",
        w100: "#f5f5f5",
        wMain: "#a8b5c5",
        w40: "#6f8190",
        w20: "#1e3a4d",
        w10: "#172935",

        text: {
            wMain: "#acbac2",
            w50: "#788c97",
        },
    },

    background: {
        w100: "#d4dbe4",
        wMain: "#7184A1",
        w20: "#0F2336",
        w10: "#02172b",
    },

    info: {
        w100: "#8ec3dd",
        wMain: "#1893cd",
        w70: "#3f88a8",
        w30: "#1d5872",
        w20: "#153f54",
        w10: "#0f2e3d",
    },

    error: {
        w100: "#e39a9b",
        wMain: "#d86263",
        w70: "#b57273",
        w30: "#6a4146",
        w20: "#4e3034",
        w10: "#523539",
    },

    warning: {
        w100: "#e8be86",
        wMain: "#e09a4a",
        w70: "#c28a54",
        w30: "#6a5a3b",
        w20: "#52462e",
        w10: "#3f3524",
    },

    success: {
        w100: "#9fd5cc",
        wMain: "#3fa695",
        w70: "#5fae9f",
        w30: "#44756c",
        w20: "#32564f",
        w10: "#263f39",
    },

    stateLayer: {
        w10: "#d1d8e11a",
        w20: "#d1d8e133",
    },

    accent: {
        n0: {
            w100: "#b9c6eb",
            wMain: "#6987d3",
            w30: "#243b7a",
            w10: "#1f3567",
        },
        n1: {
            w100: "#bcc3e2",
            wMain: "#7685c1",
            w30: "#233465",
            w60: "#4f5fa3",
            w20: "#18244a",
            w10: "#0f1833",
        },
        n2: {
            w100: "#a4d7d7",
            wMain: "#2f9698",
            w30: "#1f6667",
            w20: "#164a4b",
            w10: "#143d42",
        },
        n3: {
            w100: "#cdc2d6",
            wMain: "#9d78be",
            w30: "#542f74",
            w10: "#4a2768",
        },
        n4: {
            w100: "#e5b8d9",
            wMain: "#c05aab",
            w30: "#76376c",
        },
        n5: {
            w100: "#f2b7ae",
            wMain: "#d96f5f",
            w30: "#8f3528",
            w60: "#ae4132",
        },
        n6: {
            w100: "#e5ccaa",
            wMain: "#d4a055",
            w30: "#875e22",
        },
        n7: {
            w100: "#cfeaf6",
            wMain: "#1a729f",
            w30: "#2f5e73",
        },
        n8: {
            w100: "#b5bcc2",
            wMain: "#99a6b1",
            w30: "#748190",
        },
        n9: {
            wMain: "#e06e7b",
        },
    },

    learning: {
        wMain: "#02264a",
        w90: "#043465",
        w100: "#054280",
        w20: "#011528",
        w10: "#02264a",
    },

    // darkSurface and lightSurface are common for both themes
    darkSurface: {
        bg: "#03223B",
        bgHover: "#021B2F",
        bgActive: "#021B2F",
        text: "#f5f5f5",
        textMuted: "#acbac2",
        brandMain: "#00C895",
        brandAccent: "#00ad93",
        border: "#536574",
        buttonText: "#0892ce",
        buttonTextHover: "#33b8e0",
    },

    lightSurface: {
        bg: "#CFD3D9",
        bgActive: "#F3F4F6",
    },

    temporary: {
        primary: {
            wMain: "#E6EFF2",
        },
    },
};

export const solaceDarkTheme: ThemeDefinition = {
    id: "dark",
    label: "Solace Dark",
    palette: solaceDark,
};
