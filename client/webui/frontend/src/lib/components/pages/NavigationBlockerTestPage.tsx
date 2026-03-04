import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Header } from "@/lib/components";
import { useNavigationBlocker } from "@/lib/hooks";

/**
 * Test page to reproduce DATAGO-122642: Safari navigation blocker race condition
 *
 * Simulates the agent/connector creation flow where:
 * 1. User fills a form
 * 2. Navigation blocking is enabled
 * 3. User clicks "Create" which triggers an async operation
 * 4. After success, navigation should happen WITHOUT showing the blocker dialog
 *
 * Bug: In Safari, the dialog appears even after successful creation
 * Fix: Use useEffect to ensure isNavigationAllowed state is updated before navigation
 */
export const NavigationBlockerTestPage = () => {
    const navigate = useNavigate();
    const { allowNavigation, NavigationBlocker, setBlockingEnabled } = useNavigationBlocker();
    const [name, setName] = useState("");
    const [isSaving, setIsSaving] = useState(false);
    const [message, setMessage] = useState("");

    // Enable blocking when form has content
    useState(() => {
        setBlockingEnabled(!!name);
    });

    const handleCreate = useCallback(async () => {
        setIsSaving(true);
        setMessage("Creating...");

        // Simulate API call (like creating an agent/connector)
        await new Promise(resolve => setTimeout(resolve, 500));

        setMessage("Created successfully! Navigating...");

        // Navigate after successful creation
        // This is where the Safari bug occurs - the blocker dialog can appear
        allowNavigation(() => {
            navigate("/");
        });

        setIsSaving(false);
    }, [allowNavigation, navigate]);

    const handleCancel = useCallback(() => {
        allowNavigation(() => {
            navigate("/");
        });
    }, [allowNavigation, navigate]);

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title="Navigation Blocker Test (DATAGO-122642)"
                breadcrumbs={[
                    { label: "Home", onClick: () => navigate("/") },
                    { label: "Test Navigation Blocker" }
                ]}
            />

            <div className="flex-1 p-8">
                <div className="max-w-2xl mx-auto space-y-6">
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <h3 className="font-semibold text-yellow-900 mb-2">Testing Instructions (Safari):</h3>
                        <ol className="list-decimal list-inside space-y-1 text-sm text-yellow-800">
                            <li>Enter a name in the field below</li>
                            <li>Click "Create" button</li>
                            <li>Wait for the simulated API call to complete</li>
                            <li><strong>Expected:</strong> Page navigates home without showing blocker dialog</li>
                            <li><strong>Bug (before fix):</strong> "Unsaved changes will be discarded" dialog appears</li>
                        </ol>
                    </div>

                    {message && (
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-900">
                            {message}
                        </div>
                    )}

                    <div className="space-y-4 bg-white p-6 rounded-lg border">
                        <div>
                            <label className="block text-sm font-medium mb-2">
                                Name (required)
                            </label>
                            <input
                                type="text"
                                value={name}
                                onChange={(e) => {
                                    setName(e.target.value);
                                    setBlockingEnabled(!!e.target.value);
                                }}
                                placeholder="Enter a name..."
                                className="w-full px-3 py-2 border rounded-md"
                                disabled={isSaving}
                            />
                        </div>

                        <div className="flex gap-2">
                            <Button
                                variant="ghost"
                                onClick={handleCancel}
                                disabled={isSaving}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleCreate}
                                disabled={!name || isSaving}
                            >
                                {isSaving ? "Creating..." : "Create"}
                            </Button>
                        </div>
                    </div>

                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-700">
                        <h4 className="font-semibold mb-2">Technical Details:</h4>
                        <ul className="list-disc list-inside space-y-1">
                            <li>Navigation blocking enabled: {name ? "Yes" : "No"}</li>
                            <li>Current state simulates agent/connector creation flow</li>
                            <li>Fix uses useEffect to wait for state update before navigation</li>
                        </ul>
                    </div>
                </div>
            </div>

            <NavigationBlocker />
        </div>
    );
};