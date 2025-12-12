import { generateName } from "cypress/support/utils";

describe("Projects Page - Navigation and Layout", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToProjects();
        cy.deleteCypressProjects();
    });

    afterEach(() => {
        cy.deleteCypressProjects();
    });

    it("should create a project, upload files, and transition to chat", () => {
        const projectName = generateName();

        cy.createProject(projectName, "This is a test project created by Cypress.");

        cy.findAllByText(projectName).should("have.length", 2);

        cy.addProjectInstructions("These are the updated instructions for the project.");

        cy.fixture("test-upload.txt").then(fileContent => {
            cy.uploadFileToProject(fileContent, "test-upload.txt", "Description for the file");
        });

        cy.findByRole("button", { name: /Start New Chat/i }).click();

        cy.url().should("include", "/chat");

        cy.contains('[data-slot="badge"]', projectName).should("be.visible");

        cy.findByTestId("expandPanel").click();

        cy.findByText("test-upload.txt").should("be.visible");

        cy.findByText("Description for the file").should("be.visible");
    });
});
