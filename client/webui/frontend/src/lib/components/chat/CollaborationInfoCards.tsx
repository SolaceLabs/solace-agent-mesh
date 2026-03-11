/**
 * Collaboration Info Cards Component
 *
 * Displays informational cards explaining the benefits of chat collaboration
 * Shown once below the share notification message
 */

import { CheckCircle2 } from "lucide-react";

export function CollaborationInfoCards() {
    const benefits = [
        {
            text: "Work in one place together. No more switching back and forth between all your chats!",
            icon: <CheckCircle2 className="h-5 w-5 text-green-600" />,
        },
        {
            text: "Branch off this chat into your own private conversation at any time",
            icon: <CheckCircle2 className="h-5 w-5 text-green-600" />,
        },
    ];

    return (
        <div className="flex flex-col gap-3 py-2 sm:flex-row">
            {benefits.map((benefit, index) => (
                <div key={index} className="flex flex-1 items-start gap-3 rounded bg-[var(--old-colours/background-w20,#f7f8f9)] p-4" style={{ backgroundColor: "var(--old-colours/background-w20, #f7f8f9)" }}>
                    <div className="shrink-0">{benefit.icon}</div>
                    <p className="text-sm leading-relaxed font-medium">{benefit.text}</p>
                </div>
            ))}
        </div>
    );
}
