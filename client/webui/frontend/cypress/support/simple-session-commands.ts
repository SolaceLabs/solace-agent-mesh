/**
 * Simple Cypress session management for Solace Agent Mesh Community
 *
 * This provides a minimal session solution for the community version
 * without authentication requirements.
 */

declare global {
    namespace Cypress {
        interface Chainable {
            /**
             * Creates a minimal session with the SAM community application
             * by visiting the app and making basic API calls to trigger session creation
             */
            ensureSamSession(): Chainable<void>;
        }
    }
}

Cypress.Commands.add("ensureSamSession", () => {
    cy.session(
        "sam-community-session",
        () => {
            cy.log("Ensuring SAM community application session exists");

            // Visit the application to establish initial session
            cy.visit("/", { failOnStatusCode: false });

            // Wait for the app to be ready
            cy.get("body").should("be.visible");

            // Make a few API calls to ensure session is properly initialized
            cy.request({
                method: "GET",
                url: "/api/v1/config",
                failOnStatusCode: false,
            }).then(response => {
                cy.log("Config API status:", response.status);
            });

            // Make an agentCards call to further initialize session
            cy.request({
                method: "GET",
                url: "/api/v1/agentCards",
                failOnStatusCode: false,
            }).then(response => {
                cy.log("AgentCards API status:", response.status);
            });

            cy.wait(200);

            cy.log("SAM community session initialized");
        },
        {
            cacheAcrossSpecs: false,
            validate() {
                cy.request({
                    method: "GET",
                    url: "/api/v1/config",
                    failOnStatusCode: false,
                })
                    .its("status")
                    .should("be.oneOf", [200, 401, 403]);
            },
        }
    );
});

export {};
