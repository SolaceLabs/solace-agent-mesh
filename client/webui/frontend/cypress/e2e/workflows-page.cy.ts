describe.skip("Workflows Page - List Display and Navigation", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToWorkflows();
    });

    it("should navigate to workflows tab successfully", () => {
        // Verify we're on the workflows page by checking the URL
        cy.url().should("include", "tab=workflows");
    });

    it("should display workflows in the list", () => {
        // Wait for the workflows table to be visible
        cy.findByRole("table", { name: "Workflows" }).should("be.visible");

        // Verify the expected column headers are present
        cy.findByText("Name").should("be.visible");
        cy.findByText("Version").should("be.visible");
        cy.findByText("Status").should("be.visible");

        // Verify there are workflow rows within the table
        cy.findByRole("table", { name: "Workflows" }).find("tbody tr").should("have.length.greaterThan", 0);

        // Verify the first workflow has data in all columns
        cy.findByRole("table", { name: "Workflows" })
            .find("tbody tr")
            .first()
            .within(() => {
                cy.get("td").eq(0).should("not.be.empty"); // Name column has content
                cy.get("td").eq(1).should("not.be.empty"); // Version column has content
                cy.get("td").eq(2).should("not.be.empty"); // Status column has content
            });
    });
});

describe.skip("Workflows Page - Search and Filtering", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToWorkflows();
    });

    it("should filter workflows by search term", () => {
        cy.log("Getting first workflow name for search");

        // Get the first workflow's name to use as search term
        cy.findByRole("table", { name: "Workflows" })
            .find("tbody tr")
            .first()
            .find("td")
            .eq(0)
            .invoke("text")
            .then(workflowName => {
                const trimmedName = workflowName.trim();
                const searchTerm = trimmedName.substring(0, Math.min(3, trimmedName.length)); // Use first 3 chars or full name if shorter

                cy.log(`Searching for workflows containing: ${searchTerm}`);

                // Type in search input
                cy.findByPlaceholderText("Filter by name...").should("be.visible").type(searchTerm);

                // Verify we have at least one workflow after filtering
                cy.findByRole("table", { name: "Workflows" }).find("tbody tr").should("have.length.greaterThan", 0);

                // Verify filtered results contain the search term
                cy.findByRole("table", { name: "Workflows" }).find("tbody tr").first().should("contain.text", searchTerm);
            });
    });

    it("should show no results for non-matching search", () => {
        cy.findByPlaceholderText("Filter by name...").should("be.visible").type("ABC123");

        // Table should not exist when there are no results (empty state shown instead)
        cy.findByRole("table", { name: "Workflows" }).should("not.exist");

        // Verify empty state is shown
        cy.findByText("No workflows found").should("be.visible");
    });

    it("should clear search filter and restore all workflows", () => {
        // Get initial count before searching
        cy.findByRole("table", { name: "Workflows" })
            .find("tbody tr")
            .then($rows => {
                const initialCount = $rows.length;

                // Search for a term that is very unlikely to match any workflows
                cy.findByPlaceholderText("Filter by name...").should("be.visible").type("XYZNONEXISTENT999");

                // Verify no results - table should not exist when there are no results
                cy.findByRole("table", { name: "Workflows" }).should("not.exist");

                // Click the Clear Filter button to restore all workflows
                cy.findByRole("button", { name: "Clear Filter" }).should("be.visible").click();

                // Verify results are restored to the initial count
                cy.findByRole("table", { name: "Workflows" }).find("tbody tr").should("have.length", initialCount);
            });
    });
});

describe.skip("Workflows Page - Workflow Visualization", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToWorkflows();
    });

    it("should navigate to workflow visualization when clicking workflow name", () => {
        cy.log("Clicking first workflow to navigate to visualization");

        // Get the first workflow's name from the table
        cy.findByRole("table", { name: "Workflows" })
            .find("tbody tr")
            .first()
            .find("td")
            .eq(0)
            .invoke("text")
            .then(workflowName => {
                // Click the first workflow button
                cy.findByRole("table", { name: "Workflows" })
                    .find("tbody tr")
                    .first()
                    .within(() => {
                        cy.findByRole("button").first().click();
                    });

                cy.log(`Verifying navigation to workflow: ${workflowName.trim()}`);

                // Should navigate to the workflow visualization page
                cy.url().should("include", "/agents/workflows/");
                cy.url().should("include", workflowName.trim());
            });
    });

    it("should display workflow flowchart", () => {
        cy.log("Navigating to workflow visualization");

        // Click the first workflow button from the table
        cy.findByRole("table", { name: "Workflows" })
            .find("tbody tr")
            .first()
            .within(() => {
                cy.findByRole("button").first().click();
            });

        cy.log("Verifying flowchart elements render");

        // Wait for the workflow visualization to render and verify essential nodes
        cy.findByRole("region", { name: "Workflow visualization" })
            .should("exist")
            .within(() => {
                // Verify essential workflow nodes exist
                cy.findByText("Start").should("exist");
                cy.findByText("End").should("exist");

                // Verify the flowchart contains some nodes (beyond just Start and End)
                cy.get("span").should("have.length.greaterThan", 2);
            });
    });

    it("should open agent details panel and display properties when clicking on an agent node", () => {
        cy.log("Navigating to workflow visualization");

        // Click the first workflow to view the flowchart
        cy.findByRole("table", { name: "Workflows" })
            .find("tbody tr")
            .first()
            .within(() => {
                cy.findByRole("button").first().click();
            });

        // Verify we navigated to the workflow visualization page
        cy.url().should("include", "/agents/workflows/");

        cy.log("Waiting for workflow visualization to render");

        // Wait for the visualization container to render and Start node to load
        cy.findByRole("region", { name: "Workflow visualization" })
            .should("exist")
            .within(() => {
                cy.findByText("Start").should("exist");
            });

        cy.log("Clicking on an agent node to open details panel");

        // Scope our search to ONLY the visualization container
        // Filter excludes system nodes: Start, End, and control flow nodes (Switch, Map, Loop)
        cy.findByRole("region", { name: "Workflow visualization" }).within(() => {
            cy.get("span")
                .filter((_index, el) => {
                    const text = el.textContent?.trim() || "";
                    return text.length > 0 && text !== "Start" && text !== "End" && text !== "Switch" && text !== "Map" && text !== "Loop";
                })
                .first()
                .click();
        });

        // Verify the node detail panel slides in
        cy.findByRole("complementary", { name: "Node details panel" }).should("be.visible");

        cy.log("Testing panel view toggles");

        // Verify view toggle buttons are present within the panel
        cy.findByRole("complementary", { name: "Node details panel" }).within(() => {
            cy.findByRole("button", { name: "Details view" }).should("be.visible");
            cy.findByRole("button", { name: "Code view" }).should("be.visible");

            // Toggle to Code view and verify the Copy button appears (only in code view)
            cy.findByRole("button", { name: "Code view" }).click();
            cy.findByTestId("Copy").should("exist");

            // Toggle back to Details view and verify the Copy button is gone
            cy.findByRole("button", { name: "Details view" }).click();
            cy.findByTestId("Copy").should("not.exist");
        });

        cy.log("Closing node details panel");

        // Close the panel by clicking on the SVG background
        // Note: SVG has pointer-events: none, but click bubbles to parent container
        cy.findByRole("region", { name: "Workflow visualization" }).find("svg").first().click({ force: true });

        // Verify the panel is closed
        cy.findByRole("complementary", { name: "Node details panel" }).should("not.exist");
    });

    it("should not allow clicking on start and end nodes", () => {
        cy.log("Navigating to workflow visualization");

        // Click the first workflow to view the flowchart
        cy.findByRole("table", { name: "Workflows" })
            .find("tbody tr")
            .first()
            .within(() => {
                cy.findByRole("button").first().click();
            });

        // Verify we navigated to the workflow visualization page
        cy.url().should("include", "/agents/workflows/");

        cy.log("Waiting for workflow visualization to render");

        // Wait for the visualization container to render and Start node to load
        cy.findByRole("region", { name: "Workflow visualization" })
            .should("exist")
            .within(() => {
                cy.findByText("Start").should("exist");
            });

        cy.log("Opening details panel with an agent node");

        // Scope our search to ONLY the visualization container
        // Filter excludes system nodes: Start, End, and control flow nodes (Switch, Map, Loop)
        cy.findByRole("region", { name: "Workflow visualization" }).within(() => {
            cy.get("span")
                .filter((_index, el) => {
                    const text = el.textContent?.trim() || "";
                    return text.length > 0 && text !== "Start" && text !== "End" && text !== "Switch" && text !== "Map" && text !== "Loop";
                })
                .first()
                .click();
        });

        // Verify the node details panel opened
        cy.findByRole("complementary", { name: "Node details panel" }).should("be.visible");

        cy.log("Testing that Start node does not open panel");

        // Click on Start node within the visualization - should close the panel
        cy.findByRole("region", { name: "Workflow visualization" }).within(() => {
            cy.findByText("Start").click();
        });

        // Verify the panel is closed (Start node is not clickable)
        cy.findByRole("complementary", { name: "Node details panel" }).should("not.exist");

        cy.log("Testing that End node does not open panel");

        // Try clicking on End node within the visualization
        cy.findByRole("region", { name: "Workflow visualization" }).within(() => {
            cy.findByText("End").click();
        });

        // Verify no panel opens for End node (End node is not clickable)
        cy.findByRole("complementary", { name: "Node details panel" }).should("not.exist");
    });
});

describe.skip("Workflows Page - Workflow Detail Panel", { tags: ["@community"] }, () => {
    beforeEach(() => {
        cy.navigateToWorkflows();
    });

    it("should open workflow detail panel from visualization page", () => {
        cy.log("Navigating to workflow visualization");

        // Click the first workflow to view the flowchart
        cy.findByRole("table", { name: "Workflows" })
            .find("tbody tr")
            .first()
            .within(() => {
                cy.findByRole("button").first().click();
            });

        // Wait for visualization to load
        cy.findByRole("region", { name: "Workflow visualization" }).should("exist");

        cy.log("Opening workflow details panel");

        // Click the Open Workflow Details button (top right)
        cy.findByRole("button", { name: /Open Workflow Details/i })
            .should("be.visible")
            .click();

        // Verify Workflow Details panel opened using its semantic role
        cy.findByRole("complementary", { name: "Workflow details panel" }).should("be.visible");

        cy.log("Closing workflow details panel");

        // Close the panel by clicking the close button within the panel
        cy.findByRole("complementary", { name: "Workflow details panel" }).within(() => {
            cy.findByRole("button", { name: "Close" }).click();
        });

        // Verify the panel is closed
        cy.findByRole("complementary", { name: "Workflow details panel" }).should("not.exist");
    });
});
