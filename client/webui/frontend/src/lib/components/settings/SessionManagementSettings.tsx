import React, { useState } from "react";
import { Calendar } from "lucide-react";
import { Button, Label, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, Input } from "@/lib/components/ui";
import { DialogFooter } from "@/lib/components/ui/dialog";
import { deleteAllSessions, bulkDeleteSessions } from "@/lib/api/sessions";
import { useChatContext } from "@/lib/hooks";

export const SessionManagementSettings: React.FC = () => {
    const { addNotification, handleNewSession } = useChatContext();
    const [loading, setLoading] = useState(false);
    const [isDeleteAllDialogOpen, setIsDeleteAllDialogOpen] = useState(false);
    const [isDateRangeDialogOpen, setIsDateRangeDialogOpen] = useState(false);
    const [customStartDate, setCustomStartDate] = useState("");
    const [customEndDate, setCustomEndDate] = useState("");

    const handleDeleteAllConfirm = async () => {
        setLoading(true);
        try {
            const result = await deleteAllSessions();

            if (result) {
                addNotification(`Successfully deleted ${result.deletedCount} session${result.deletedCount !== 1 ? "s" : ""}`, "success");

                if (result.failedCount > 0) {
                    addNotification(`Failed to delete ${result.failedCount} session${result.failedCount !== 1 ? "s" : ""}`, "warning");
                }

                // Start a new session after deleting all
                handleNewSession();
            }
        } catch (error) {
            console.error("Failed to delete sessions:", error);
            addNotification("Failed to delete sessions", "warning");
        } finally {
            setLoading(false);
            setIsDeleteAllDialogOpen(false);
        }
    };

    const handleDateRangeDelete = () => {
        if (!customStartDate || !customEndDate) {
            addNotification("Please select both start and end dates", "warning");
            return;
        }

        const startDate = new Date(customStartDate).getTime();
        const endDate = new Date(customEndDate).getTime();

        if (startDate > endDate) {
            addNotification("Start date must be before end date", "warning");
            return;
        }

        setIsDateRangeDialogOpen(true);
    };

    const handleDateRangeDeleteConfirm = async () => {
        setLoading(true);
        try {
            const startDate = new Date(customStartDate).getTime();
            const endDate = new Date(customEndDate).getTime();

            const result = await bulkDeleteSessions({ startDate, endDate });

            if (result) {
                addNotification(`Successfully deleted ${result.deletedCount} session${result.deletedCount !== 1 ? "s" : ""}`, "success");

                if (result.failedCount > 0) {
                    addNotification(`Failed to delete ${result.failedCount} session${result.failedCount !== 1 ? "s" : ""}`, "warning");
                }

                // Clear the date inputs
                setCustomStartDate("");
                setCustomEndDate("");
            }
        } catch (error) {
            console.error("Failed to delete sessions:", error);
            addNotification("Failed to delete sessions", "warning");
        } finally {
            setLoading(false);
            setIsDateRangeDialogOpen(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Delete All Sessions Section */}
            <div className="space-y-4">
                <div className="border-b pb-2">
                    <h3 className="text-lg font-semibold">Delete All Sessions</h3>
                </div>

                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Label className="font-medium">Remove all chat sessions</Label>
                    </div>
                    <Button variant="outline" onClick={() => setIsDeleteAllDialogOpen(true)}>
                        Delete All
                    </Button>
                </div>
            </div>

            {/* Delete by Date Range Section */}
            <div className="space-y-4">
                <div className="border-b pb-2">
                    <h3 className="text-lg font-semibold">Delete by Date Range</h3>
                </div>

                <div className="flex items-center gap-2">
                    <Calendar className="size-4" />
                    <Label className="font-medium">Select date range to delete sessions</Label>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <Label>Start Date</Label>
                        <Input type="date" value={customStartDate} onChange={e => setCustomStartDate(e.target.value)} className="dark:[color-scheme:dark]" />
                    </div>
                    <div className="space-y-2">
                        <Label>End Date</Label>
                        <Input type="date" value={customEndDate} onChange={e => setCustomEndDate(e.target.value)} className="dark:[color-scheme:dark]" />
                    </div>
                </div>

                <Button variant="outline" onClick={handleDateRangeDelete} disabled={!customStartDate || !customEndDate}>
                    Delete Sessions in Range
                </Button>
            </div>

            {/* Delete All Confirmation Dialog */}
            <Dialog open={isDeleteAllDialogOpen} onOpenChange={setIsDeleteAllDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Delete All Sessions?</DialogTitle>
                        <DialogDescription>Are you sure you want to delete all your chat sessions? This action is permanent and cannot be undone. All messages, artifacts, and associated data will be removed.</DialogDescription>
                    </DialogHeader>

                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setIsDeleteAllDialogOpen(false)} disabled={loading}>
                            Cancel
                        </Button>
                        <Button variant="outline" onClick={handleDeleteAllConfirm} disabled={loading}>
                            {loading ? "Deleting..." : "Delete All Sessions"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Date Range Confirmation Dialog */}
            <Dialog open={isDateRangeDialogOpen} onOpenChange={setIsDateRangeDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Delete Sessions in Date Range?</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to delete sessions from {customStartDate} to {customEndDate}? This action is permanent and cannot be undone. All messages, artifacts, and associated data will be removed.
                        </DialogDescription>
                    </DialogHeader>

                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setIsDateRangeDialogOpen(false)} disabled={loading}>
                            Cancel
                        </Button>
                        <Button variant="outline" onClick={handleDateRangeDeleteConfirm} disabled={loading}>
                            {loading ? "Deleting..." : "Delete Sessions"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
