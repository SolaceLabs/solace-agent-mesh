import { useState, useCallback } from "react";
import { api } from "@/lib/api";

export interface FeedbackData {
    type: "up" | "down";
    text: string;
}

interface UseFeedbackOptions {
    sessionId: string;
    onError?: (title: string, error: string) => void;
}

interface UseFeedbackReturn {
    submittedFeedback: Record<string, FeedbackData>;
    submitFeedback: (taskId: string, feedbackType: "up" | "down", feedbackText: string) => Promise<void>;
    setSubmittedFeedback: React.Dispatch<React.SetStateAction<Record<string, FeedbackData>>>;
}

/**
 * Custom hook to manage user feedback for chat tasks
 * Handles submission and tracking of thumbs up/down feedback
 */
export const useFeedback = ({ sessionId, onError }: UseFeedbackOptions): UseFeedbackReturn => {
    const [submittedFeedback, setSubmittedFeedback] = useState<Record<string, FeedbackData>>({});

    /**
     * Submit feedback for a specific task
     */
    const submitFeedback = useCallback(
        async (taskId: string, feedbackType: "up" | "down", feedbackText: string) => {
            if (!sessionId) {
                console.error("Cannot submit feedback without a session ID.");
                onError?.("Feedback Failed", "No active session found.");
                return;
            }

            try {
                await api.webui.post("/api/v1/feedback", {
                    taskId,
                    sessionId,
                    feedbackType,
                    feedbackText,
                });

                // Update local state on success
                setSubmittedFeedback(prev => ({
                    ...prev,
                    [taskId]: { type: feedbackType, text: feedbackText },
                }));
            } catch (error) {
                console.error("Failed to submit feedback:", error);
                onError?.("Feedback Submission Failed", "Failed to submit feedback. Please try again.");
                throw error;
            }
        },
        [sessionId, onError]
    );

    return {
        submittedFeedback,
        submitFeedback,
        setSubmittedFeedback,
    };
};
