describe.skip("Projects - File Upload and Indexing", { tags: ["@rc"] }, () => {
    let projectId: string;
    const projectName = `Indexing Test ${Date.now()}`;

    beforeEach(() => {
        cy.ensureSamSession();
    });

    afterEach(() => {
        if (projectId) {
            cy.request({
                method: "DELETE",
                url: `/api/v1/projects/${projectId}`,
                failOnStatusCode: false,
            });
        }
    });

    it("should index uploaded file and use index_search tool when queried", () => {
        cy.visit("/#/projects");
        cy.url().should("include", "/projects");

        cy.findByRole("button", { name: /create new project/i })
            .should("be.visible")
            .click();

        cy.findByRole("dialog").should("be.visible");
        cy.get("#project-name").type(projectName);
        cy.findByRole("button", { name: /create project/i }).click();

        cy.url().should("match", /\/projects\/[a-f0-9-]+$/);
        cy.url().then(url => {
            projectId = url.split("/").pop() || "";
            cy.log(`Created project with ID: ${projectId}`);
        });

        cy.get('input[name="project-files"]').should("exist").selectFile("cypress/fixtures/test-document.txt", { force: true });

        cy.findByRole("dialog").should("be.visible");
        cy.contains("test-document.txt").should("be.visible");
        cy.findByTestId("dialogConfirmButton").should("be.visible").click();

        cy.contains("Project file processing complete", { timeout: 60000 }).should("be.visible");

        cy.contains("test-document.txt").should("be.visible");

        cy.findByTestId("startNewChatButton", { timeout: 10000 }).should("be.visible").click();

        cy.findByTestId("chat-input").should("be.visible").type("What information is available about the indexing feature?{enter}");

        cy.ensurePanelExpanded();

        cy.contains("button", "Activity", { timeout: 30000 }).should("be.visible");

        cy.findByTestId("activity").click();

        cy.get('[data-testid="tool-node-index_search"]', { timeout: 10000 }).should("be.visible").and("contain", "index_search");

        cy.findByTestId("rag").click();

        cy.contains("test-document.txt").should("be.visible");
        cy.contains("1 citation").should("be.visible");
    });
});
