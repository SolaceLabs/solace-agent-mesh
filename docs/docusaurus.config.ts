import { themes as prismThemes } from "prism-react-renderer";
import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";

// This runs in Node.js - Don't use client-side code here 
// https://docusaurus.io/docs/configuration

const config: Config = {
  title: "Solace Agent Mesh",
  favicon: "/img/logo.png",
  url: "https://solacelabs.github.io",
  baseUrl: "/solace-agent-mesh",
  organizationName: "SolaceLabs",
  projectName: "solace-agent-mesh", 

  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "throw",

  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      {
        docs: {
          sidebarPath: "./sidebars.ts",
          editUrl: "https://github.com/SolaceLabs/solace-agent-mesh/edit/main/docs",
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: "img/logo.png",
    colorMode: {
      defaultMode: 'dark',
      disableSwitch: false,
      respectPrefersColorScheme: true,
    },

    navbar: {
      title: "Solace Agent Mesh",
      logo: {
        alt: "Solace Agent Mesh Logo",
        src: "img/logo.png",
        href: "/docs/documentation/getting-started/introduction",
      },
      items: [
        {
          type: "docSidebar",
          sidebarId: "docSidebar",
          position: "left",
          label: "Documentation",
        },
        {
          href: "https://github.com/SolaceLabs/solace-agent-mesh/",
          label: "GitHub",
          position: "right",
        },
      ],
    },
    docs: {
      sidebar: {
        hideable: false,
        autoCollapseCategories: false,
      },
    },
    footer: {
      style: "dark",
      links: [
        {
          title: "Solace Agent Mesh",
          items: [
            {
              label: "Documentation",
              to: "/docs/documentation/getting-started/introduction",
            },
            {
              label: "GitHub",
              href: "https://github.com/SolaceLabs/solace-agent-mesh/",
            },
            {
              label: "Official Plugins",
              href: "https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/",
            }
          ],
        },
        {
          title: "Company",
          items: [
            {
              label: "Products",
              href: "https://solace.com/products/",
            },
            {
              label: "Contact",
              href: "https://solace.com/contact/",
            },
            {
              label: "Support",
              href: "https://solace.com/support/",
            },
            {
              label: "Privacy and Legal",
              href: "https://solace.com/legal/",
            },
          ],
        },
        {
          title: "Community",
          items: [
            {
              label: "LinkedIn",
              href: "https://www.linkedin.com/company/solacedotcom/",
            },
            {
              label: "GitHub",
              href: "https://github.com/SolaceLabs",
            },
            {
              label: "YouTube",
              href: "https://www.youtube.com/SolaceSystems",
            },
            {
              label: "X",
              href: "https://twitter.com/solacedotcom",
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Solace.`,
      logo: {
        alt: 'Solace Logo',
        src: 'img/solace-logo.png',
        width: "10%",
        height: "10%",
      },
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,

  markdown: {
    mermaid: true
  },
  themes: ['@docusaurus/theme-mermaid'],

  plugins: [require.resolve('docusaurus-lunr-search')],
};

export default config;
