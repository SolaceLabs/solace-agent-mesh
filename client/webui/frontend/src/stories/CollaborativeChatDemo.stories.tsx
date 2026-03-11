/**
 * Comprehensive demo showing the full collaborative chat experience
 */

import type { Meta, StoryObj } from "@storybook/react-vite";
import { UserPresenceAvatars } from "@/lib/components/chat/UserPresenceAvatars";
import { ShareNotificationMessage } from "@/lib/components/chat/ShareNotificationMessage";
import { CollaborationInfoCards } from "@/lib/components/chat/CollaborationInfoCards";
import { MessageUserAttribution } from "@/lib/components/chat/MessageUserAttribution";
import { mockCollaborativeUsers, mockActiveCollaborativeSession } from "@/lib/mockData/collaborativeChat";

const meta: Meta = {
    title: "Chat/Collaboration/Full Demo",
    parameters: {
        layout: "fullscreen",
    },
};

export default meta;

type Story = StoryObj;

export const CollaborativeChatConversation: Story = {
    render: () => (
        <div className="flex h-screen w-full flex-col">
            {/* Header */}
            <div className="bg-background flex items-center justify-between border-b px-6 py-4">
                <h1 className="text-lg font-semibold">Python Script Development</h1>
                <div className="flex items-center gap-4">
                    <UserPresenceAvatars users={mockActiveCollaborativeSession.collaborators} currentUserId={mockActiveCollaborativeSession.currentUserId} />
                    <button className="bg-primary text-primary-foreground rounded px-4 py-2 text-sm">Share</button>
                </div>
            </div>

            {/* Message area */}
            <div className="flex-1 overflow-y-auto p-6">
                <div className="mx-auto max-w-3xl space-y-4">
                    {/* Alice's first message (before sharing) */}
                    <div>
                        <MessageUserAttribution userName={mockCollaborativeUsers.alice.name} timestamp={Date.now() - 4 * 60 * 60 * 1000} userIndex={0} />
                        <div className="rounded-lg bg-[var(--old-colours/secondary-w20,#e7e9ec)] p-4">
                            <p className="text-base">Hi! Can you help me create a Python script to process CSV files and generate reports?</p>
                        </div>
                    </div>

                    {/* Agent response */}
                    <div className="ml-10">
                        <div className="mb-1 flex items-center gap-2">
                            <div className="bg-primary text-primary-foreground flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold">🤖</div>
                            <span className="text-sm font-medium">Solace Agent Mesh</span>
                        </div>
                        <div className="rounded-lg bg-white p-4 shadow-sm">
                            <p className="text-base">I'd be happy to help you create a Python script for CSV processing. I'll create a script that can read CSV files, process the data, and generate reports.</p>
                        </div>
                    </div>

                    {/* Alice's follow-up */}
                    <div>
                        <MessageUserAttribution userName={mockCollaborativeUsers.alice.name} timestamp={Date.now() - 3.5 * 60 * 60 * 1000} userIndex={0} />
                        <div className="rounded-lg bg-[var(--old-colours/secondary-w20,#e7e9ec)] p-4">
                            <p className="text-base">Great! Can you also add error handling for missing columns?</p>
                        </div>
                    </div>

                    {/* Agent response with artifact */}
                    <div className="ml-10">
                        <div className="mb-1 flex items-center gap-2">
                            <div className="bg-primary text-primary-foreground flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold">🤖</div>
                            <span className="text-sm font-medium">Solace Agent Mesh</span>
                        </div>
                        <div className="rounded-lg bg-white p-4 shadow-sm">
                            <p className="text-base">I've created a Python script with comprehensive error handling. It includes validation for missing columns and provides helpful error messages.</p>
                            <div className="mt-3 rounded border bg-gray-50 p-3">
                                <div className="flex items-center gap-2">
                                    <span className="font-mono text-sm">📄 csv_processor.py</span>
                                    <span className="text-muted-foreground text-xs">2.4 KB</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* SHARE NOTIFICATION */}
                    <ShareNotificationMessage sharedBy={mockActiveCollaborativeSession.sharedByName!} sharedWith={mockActiveCollaborativeSession.sharedWithNames!} timestamp={mockActiveCollaborativeSession.sharedAt!} />

                    {/* INFO CARDS */}
                    <CollaborationInfoCards />

                    {/* Bob's first message (after being added) */}
                    <div>
                        <MessageUserAttribution userName={mockCollaborativeUsers.bob.name} timestamp={Date.now() - 2 * 60 * 60 * 1000} userIndex={1} />
                        <div className="rounded-lg bg-[var(--old-colours/secondary-w20,#e7e9ec)] p-4">
                            <p className="text-base">Thanks for adding me! Quick question - does this script handle different CSV delimiters like semicolons?</p>
                        </div>
                    </div>

                    {/* Agent response to Bob */}
                    <div className="ml-10">
                        <div className="mb-1 flex items-center gap-2">
                            <div className="bg-primary text-primary-foreground flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold">🤖</div>
                            <span className="text-sm font-medium">Solace Agent Mesh</span>
                        </div>
                        <div className="rounded-lg bg-white p-4 shadow-sm">
                            <p className="text-base">Great question! Yes, the script uses Python's csv.Sniffer to automatically detect different delimiters including semicolons, tabs, and pipes.</p>
                        </div>
                    </div>

                    {/* Alice responds to Bob's question */}
                    <div>
                        <MessageUserAttribution userName={mockCollaborativeUsers.alice.name} timestamp={Date.now() - 1 * 60 * 60 * 1000} userIndex={0} />
                        <div className="rounded-lg bg-[var(--old-colours/secondary-w20,#e7e9ec)] p-4">
                            <p className="text-base">That's a good point Bob! We often get files with different formats from various sources.</p>
                        </div>
                    </div>

                    {/* Your own message (current user - Bob) - NO ATTRIBUTION */}
                    <div className="flex justify-end">
                        <div className="bg-primary text-primary-foreground rounded-lg p-4" style={{ maxWidth: "70%" }}>
                            <p className="text-base">Perfect! This will save us a lot of time. Can we also add a summary statistics feature?</p>
                        </div>
                    </div>

                    {/* Agent response */}
                    <div className="ml-10">
                        <div className="mb-1 flex items-center gap-2">
                            <div className="bg-primary text-primary-foreground flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold">🤖</div>
                            <span className="text-sm font-medium">Solace Agent Mesh</span>
                        </div>
                        <div className="rounded-lg bg-white p-4 shadow-sm">
                            <p className="text-base">Absolutely! I'll add a summary statistics module that calculates count, mean, median, and standard deviation for numeric columns.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    ),
};
