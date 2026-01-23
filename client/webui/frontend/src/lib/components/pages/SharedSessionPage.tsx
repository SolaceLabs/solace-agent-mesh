/**
 * SharedSessionPage - Public view of a shared chat session
 */

import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Lock, Globe, Building2, AlertCircle } from "lucide-react";
import { Button, Spinner } from "@/lib/components/ui";
import { viewSharedSession } from "@/lib/api/shareApi";
import type { SharedSessionView } from "@/lib/types/share";

export function SharedSessionPage() {
    const { shareId } = useParams<{ shareId: string }>();
    const navigate = useNavigate();
    const [session, setSession] = useState<SharedSessionView | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (shareId) {
            loadSharedSession(shareId);
        }
    }, [shareId]);

    const loadSharedSession = async (id: string) => {
        setLoading(true);
        setError(null);
        try {
            const data = await viewSharedSession(id);
            setSession(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load shared session");
        } finally {
            setLoading(false);
        }
    };

    const getAccessIcon = (accessType: string) => {
        switch (accessType) {
            case "public":
                return <Globe className="h-4 w-4" />;
            case "authenticated":
                return <Lock className="h-4 w-4" />;
            case "domain-restricted":
                return <Building2 className="h-4 w-4" />;
            default:
                return null;
        }
    };

    const getAccessLabel = (accessType: string) => {
        switch (accessType) {
            case "public":
                return "Public";
            case "authenticated":
                return "Authenticated";
            case "domain-restricted":
                return "Domain Restricted";
            default:
                return accessType;
        }
    };

    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <Spinner size="large" variant="primary">
                    <p className="text-muted-foreground mt-4 text-sm">Loading shared session...</p>
                </Spinner>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-destructive h-16 w-16" />
                <h1 className="text-2xl font-semibold">Unable to View Session</h1>
                <p className="text-muted-foreground max-w-md text-center">{error}</p>
                <Button variant="outline" onClick={() => navigate("/")}>
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Go to Home
                </Button>
            </div>
        );
    }

    if (!session) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4 p-8">
                <AlertCircle className="text-muted-foreground h-16 w-16" />
                <h1 className="text-2xl font-semibold">Session Not Found</h1>
                <p className="text-muted-foreground">This shared session may have been deleted or the link is invalid.</p>
                <Button variant="outline" onClick={() => navigate("/")}>
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Go to Home
                </Button>
            </div>
        );
    }

    // Parse message bubbles from tasks
    const messages: Array<{ type: string; text: string; timestamp?: number }> = [];
    for (const task of session.tasks) {
        try {
            const bubbles = typeof task.message_bubbles === "string" ? JSON.parse(task.message_bubbles) : task.message_bubbles;

            if (Array.isArray(bubbles)) {
                for (const bubble of bubbles) {
                    messages.push({
                        type: bubble.type || "agent",
                        text: bubble.text || bubble.content || "",
                        timestamp: task.created_time,
                    });
                }
            }
        } catch (e) {
            console.error("Failed to parse message bubbles:", e);
        }
    }

    return (
        <div className="flex h-screen flex-col">
            {/* Header */}
            <header className="border-b px-6 py-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="sm" onClick={() => navigate("/")}>
                            <ArrowLeft className="mr-2 h-4 w-4" />
                            Back
                        </Button>
                        <div className="h-6 border-r" />
                        <div>
                            <h1 className="text-lg font-semibold">{session.title}</h1>
                            <div className="text-muted-foreground flex items-center gap-2 text-sm">
                                {getAccessIcon(session.access_type)}
                                <span>{getAccessLabel(session.access_type)}</span>
                                <span>•</span>
                                <span>Shared on {new Date(session.created_time).toLocaleDateString()}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Messages */}
            <main className="flex-1 overflow-y-auto p-6">
                <div className="mx-auto max-w-3xl space-y-4">
                    {messages.length === 0 ? (
                        <div className="text-muted-foreground py-12 text-center">
                            <p>No messages in this session.</p>
                        </div>
                    ) : (
                        messages.map((message, index) => (
                            <div key={index} className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}>
                                <div className={`max-w-[80%] rounded-lg px-4 py-2 ${message.type === "user" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                                    <p className="whitespace-pre-wrap">{message.text}</p>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </main>

            {/* Footer */}
            <footer className="text-muted-foreground border-t px-6 py-3 text-center text-sm">
                <p>This is a read-only view of a shared chat session.</p>
            </footer>
        </div>
    );
}
