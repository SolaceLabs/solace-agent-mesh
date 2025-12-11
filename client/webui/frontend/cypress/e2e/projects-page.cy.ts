import { CYPRESS_TAG, generateName } from "cypress/support/utils";

describe("Projects Page - Navigation and Layout", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToProjects();
        cy.deleteCypressProjects();
    });

    afterEach(() => {
        cy.deleteCypressProjects();
    });

    it("should create a project and verify its details", () => {
        const projectName = generateName();

        cy.findByRole("button", { name: "Create New Project" }).click();

        cy.findByLabelText(/Project Name/i).type(projectName);

        cy.findByLabelText(/Description/i).type("Cleanup test project");

        cy.findByRole("button", { name: "Create Project" }).click();

        cy.findAllByText(projectName).should("have.length", 2);

        cy.findByRole("heading", { name: "Instructions" })
            .parent()
            .parent()
            .within(() => {
                cy.findByRole("button", { name: "Edit" }).click();
            });

        cy.findByRole("dialog", { name: "Edit Project Instructions" }).within(() => {
            cy.get("textarea").type("You are a helpful assistant. Please respond only in French.");

            cy.findByRole("button", { name: "Save" }).click();
        });

        cy.findByRole("heading", { name: "Chats" })
            .parent()
            .findByRole("button", { name: /New Chat/i })
            .click();

        cy.findByRole("button", { name: "New Chat" }).should("be.visible");

        cy.findByText(projectName).should("be.visible");
    });
});
