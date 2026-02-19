describe("Chat Page - Navigation and Layout", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToChat();
    });

    it("should display main navigation", () => {
        cy.findByRole("button", { name: "Chat" }).should("be.visible");
        cy.findByRole("button", { name: "Agent Mesh" }).should("be.visible");
    });

    it("should display side panel buttons", () => {
        cy.findByRole("button", { name: "Expand Panel" }).should("be.visible");
        cy.findByRole("button", { name: "Files" }).should("be.visible");
        cy.findByRole("button", { name: "Activity" }).should("be.visible");
    });

    it("should display files panel", () => {
        cy.findByRole("button", { name: "Files" }).should("be.visible").click();
        cy.findByText("No files available").should("be.visible");
    });

    it("should display workflow panel", () => {
        cy.findByRole("button", { name: "Activity" }).should("be.visible").click();
        cy.findByText("No task selected to display").should("be.visible");
    });

    it("should expand and collapse side panel", () => {
        cy.findByRole("button", { name: "Expand Panel" }).should("be.visible").click();
        cy.findByRole("tablist").should("be.visible");
        cy.findByRole("button", { name: "Collapse Panel" }).should("be.visible").click();
        cy.findByRole("tablist").should("not.exist");
    });
});

describe("Chat Page - Messaging Functionality", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToChat();
    });

    it("should have a functioning chat input", () => {
        cy.findByTestId("chat-input").should("be.visible");
        cy.findByTestId("chat-input").type("Test message");
        cy.findByTestId("chat-input").should("have.text", "Test message");
    });

    it("should allow sending a message and show workflow", () => {
        cy.startNewChat();

        // Verify no workflow button exists initially
        cy.findByRole("button", { name: "View Activity" }).should("not.exist");

        // Send a test message
        cy.findByTestId("chat-input").should("be.visible").type("Hello SAM{enter}");

        // Wait for the agent response - workflow button should appear
        cy.findByRole("button", { name: "View Activity" }).should("be.visible");

        // Check workflow panel shows execution details
        cy.findByRole("button", { name: "View Activity" }).should("be.visible").click();
        cy.findByText("No task selected to display").should("not.exist");
        cy.findByText("Completed").should("be.visible");

        // Verify workflow nodes are present
        cy.findAllByTestId("userNode").should("have.length.greaterThan", 0);
    });

    it("should handle multiple messages in a conversation", () => {
        cy.startNewChat();

        // Send first message
        cy.findByTestId("chat-input").type("First message{enter}");
        cy.findByRole("button", { name: "View Activity" }).should("be.visible");

        // Send second message
        cy.findByRole("button", { name: "Send message" }).should("be.visible");
        cy.findByTestId("chat-input").type("Second message{enter}");

        // Wait for the second agent response by checking for the workflow button again
        // This ensures both user messages and agent responses are present
        cy.findAllByRole("button", { name: "View Activity" }).should("have.length.greaterThan", 1);
    });
});

describe("Chat Page - Theme and Responsive Design", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToChat();
    });

    it("should be responsive on tablet viewport", () => {
        cy.viewport(768, 1024); // iPad viewport

        // All main elements should be visible
        cy.findByRole("button", { name: "Chat" }).should("be.visible");
        cy.findByRole("button", { name: "Agent Mesh" }).should("be.visible");
        cy.findByTestId("chat-input").should("be.visible");
    });
});
