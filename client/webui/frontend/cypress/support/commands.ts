/// <reference types="cypress" />
import "@testing-library/cypress/add-commands";

import type { ByRoleOptions } from "@testing-library/dom";

/* eslint-disable @typescript-eslint/no-namespace */
declare global {
    namespace Cypress {
        interface Chainable {
            // @testing-library/cypress commands
            findByText(text: string | RegExp): Chainable;
            findByRole(role: string, options?: Partial<ByRoleOptions>): Chainable;
            findAllByRole(role: string, options?: Partial<ByRoleOptions>): Chainable;
            findByTestId(testId: string): Chainable;
            findByDisplayValue(value: string | RegExp): Chainable;

            // custom commands for community application
            startNewChat(): Chainable;
            navigateToChat(): Chainable;
            navigateToAgents(): Chainable;
        }
        interface SuiteConfigOverrides {
            tags?: string[];
        }
    }
}

Cypress.Commands.add("startNewChat", () => {
    cy.navigateToChat();
    cy.findAllByRole("button", { name: "Start New Chat Session" }).filter(":visible").should("have.length", 1).click();

    // Check if dialog appears (when persistenceEnabled is false)
    cy.get("body").then($body => {
        if ($body.find('[role="dialog"]').length > 0) {
            // Dialog exists, wait for it to be visible and click confirmation
            cy.findByRole("dialog").should("be.visible");
            cy.findByRole("button", { name: "Start New Chat" }).should("be.visible").click();
        }
        // If no dialog exists, the new chat was already started by the button click
    });
});

Cypress.Commands.add("navigateToChat", () => {
    cy.log("Navigating to Chat page");
    cy.findByRole("button", { name: "Chat" }).should("be.visible").click();
    cy.url().should("include", "/");
});

Cypress.Commands.add("navigateToAgents", () => {
    cy.log("Navigating to Agents page");
    cy.findByRole("button", { name: "Agents" }).should("be.visible").click();
});

export {};
