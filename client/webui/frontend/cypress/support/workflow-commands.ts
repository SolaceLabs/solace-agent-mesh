/// <reference types="cypress" />

// Custom commands for workflow testing
Cypress.Commands.add("waitForWorkflowToLoad", (options = {}) => {
    const { timeout = 30000 } = options;

    // Wait for React Flow to be fully rendered
    cy.get(".react-flow__renderer", { timeout }).should("exist").should("be.visible");

    // Wait for the viewport to be ready
    cy.get(".react-flow__viewport", { timeout }).should("exist").should("be.visible");

    // Wait for nodes to be rendered
    cy.get(".react-flow__nodes", { timeout })
        .should("exist")
        .should("be.visible")
        .within(() => {
            cy.get(".react-flow__node").should("have.length.greaterThan", 0);
        });

    // Give React Flow time to finish animations
    cy.wait(500);
});

Cypress.Commands.add("waitForWorkflowNodes", (expectedCount, options = {}) => {
    const { timeout = 30000 } = options;

    // More specific selector for React Flow nodes
    cy.get(".react-flow__node", { timeout }).should("have.length", expectedCount);

    // Also check that nodes are visible and positioned
    cy.get(".react-flow__node").each($node => {
        cy.wrap($node).should("be.visible").should("have.attr", "style").and("include", "transform");
    });
});

// Extend Cypress namespace
declare global {
    namespace Cypress {
        interface Chainable {
            waitForWorkflowToLoad(options?: { timeout?: number }): Chainable;
            waitForWorkflowNodes(expectedCount: number, options?: { timeout?: number }): Chainable;
        }
    }
}

export {};
