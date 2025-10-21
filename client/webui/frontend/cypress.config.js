import { defineConfig } from "cypress";

export default defineConfig({
    e2e: {
        baseUrl: process.env.CYPRESS_BASE_URL || "http://localhost:3000",
        setupNodeEvents(on, config) {
            config.baseUrl = process.env.CYPRESS_BASE_URL || config.baseUrl;
            return config;
        },
        specPattern: "cypress/e2e/**/*.cy.{js,jsx,ts,tsx}",
        supportFile: "cypress/support/e2e.ts",
        defaultCommandTimeout: 20000,
        pageLoadTimeout: 90000,
        requestTimeout: 30000,
        responseTimeout: 90000,
        // Retry configuration for flaky tests
        retries: {
            runMode: 2,
            openMode: 0,
        },
        // Disable Chrome's aggressive connection limiting
        chromeWebSecurity: false,
        // Experimental features for better stability
        experimentalMemoryManagement: true,
        numTestsKeptInMemory: 1,
        // Additional settings for port-forwarding stability
        watchForFileChanges: false,
        // JUnit reporter configuration for GitHub Actions
        reporter: "junit",
        reporterOptions: {
            mochaFile: "cypress/results/results-[hash].xml",
            toConsole: true,
        },
    },
    viewportWidth: 1280,
    viewportHeight: 720,
    video: true,
    screenshotOnRunFailure: true,
});
