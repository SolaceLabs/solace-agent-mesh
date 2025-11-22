import React, { useState, useRef, useEffect } from "react";
import { SunMoon, Activity, User, Upload, Trash2 } from "lucide-react";
import { useThemeContext } from "@/lib/hooks";
import { Label, Switch, Button } from "@/lib/components/ui";
import { getUserProfile, uploadAvatar, deleteAvatar } from "@/lib/api/user-profile-api";
import type { UserProfile } from "@/lib/api/user-profile-api";

const CONTEXT_INDICATOR_STORAGE_KEY = "show-context-indicator";

export const GeneralSettings: React.FC = () => {
    const { currentTheme, toggleTheme } = useThemeContext();
    const [showContextIndicator, setShowContextIndicator] = useState(() => {
        const saved = localStorage.getItem(CONTEXT_INDICATOR_STORAGE_KEY);
        return saved !== null ? saved === "true" : true; // Default to true (shown)
    });

    const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Load user profile on mount
    useEffect(() => {
        loadUserProfile();
    }, []);

    const loadUserProfile = async () => {
        try {
            const profile = await getUserProfile();
            setUserProfile(profile);
        } catch (error) {
            console.error("Failed to load user profile:", error);
        }
    };

    const handleContextIndicatorToggle = (checked: boolean) => {
        setShowContextIndicator(checked);
        localStorage.setItem(CONTEXT_INDICATOR_STORAGE_KEY, String(checked));
        // Dispatch event to notify ChatPage of the change
        window.dispatchEvent(new CustomEvent("context-indicator-visibility-changed", { detail: { visible: checked } }));
    };

    const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        // Validate file type
        const validTypes = ["image/jpeg", "image/png", "image/gif", "image/webp"];
        if (!validTypes.includes(file.type)) {
            setUploadError("Please select a valid image file (JPEG, PNG, GIF, or WebP)");
            return;
        }

        // Validate file size (5MB max)
        const maxSize = 5 * 1024 * 1024;
        if (file.size > maxSize) {
            setUploadError("File size must be less than 5MB");
            return;
        }

        setIsUploading(true);
        setUploadError(null);

        try {
            await uploadAvatar(file, "local");
            await loadUserProfile();
            // Dispatch event to notify other components (like UserMenu) to refresh
            window.dispatchEvent(new CustomEvent("avatar-updated"));
        } catch (error) {
            console.error("Failed to upload avatar:", error);
            setUploadError(error instanceof Error ? error.message : "Failed to upload avatar");
        } finally {
            setIsUploading(false);
            // Reset file input
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        }
    };

    const handleAvatarDelete = async () => {
        if (!confirm("Are you sure you want to delete your avatar?")) {
            return;
        }

        setIsUploading(true);
        setUploadError(null);

        try {
            await deleteAvatar();
            await loadUserProfile();
            // Dispatch event to notify other components
            window.dispatchEvent(new CustomEvent("avatar-updated"));
        } catch (error) {
            console.error("Failed to delete avatar:", error);
            setUploadError(error instanceof Error ? error.message : "Failed to delete avatar");
        } finally {
            setIsUploading(false);
        }
    };

    const triggerFileInput = () => {
        fileInputRef.current?.click();
    };

    return (
        <div className="space-y-6">
            {/* Profile Section */}
            <div className="space-y-4">
                <div className="border-b pb-2">
                    <h3 className="text-lg font-semibold">Profile</h3>
                </div>

                {/* Avatar Upload */}
                <div className="space-y-3">
                    <Label className="flex items-center gap-2 font-medium">
                        <User className="size-4" />
                        Profile Picture
                    </Label>

                    <div className="flex items-center gap-4">
                        {/* Avatar Preview */}
                        <div className="relative flex-shrink-0">
                            {userProfile?.avatarUrl ? (
                                <img src={userProfile.avatarUrl} alt="Avatar" className="h-16 w-16 rounded-full border-2 border-gray-200 object-cover dark:border-gray-700" />
                            ) : (
                                <div className="flex h-16 w-16 items-center justify-center rounded-full border-2 border-gray-200 bg-blue-600 text-xl font-semibold text-white dark:border-gray-700">
                                    {userProfile?.displayName?.[0]?.toUpperCase() || "U"}
                                </div>
                            )}
                        </div>

                        {/* Upload/Delete Buttons - Inline to the right */}
                        <div className="ml-auto flex items-center gap-2">
                            <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={handleAvatarUpload} className="hidden" />

                            <Button onClick={triggerFileInput} disabled={isUploading} size="sm" variant="ghost" className="flex items-center gap-2">
                                <Upload className="size-4" />
                                {isUploading ? "Uploading..." : "Upload"}
                            </Button>

                            {userProfile?.avatarUrl && (
                                <Button onClick={handleAvatarDelete} disabled={isUploading} size="sm" variant="ghost" className="flex items-center gap-2">
                                    <Trash2 className="size-4" />
                                    Delete
                                </Button>
                            )}
                        </div>
                    </div>

                    {/* Error Message */}
                    {uploadError && <p className="text-sm text-red-600 dark:text-red-400">{uploadError}</p>}

                    {/* Help Text */}
                    <p className="text-xs text-gray-500 dark:text-gray-400">Supported formats: JPEG, PNG, GIF, WebP. Maximum size: 5MB</p>
                </div>
            </div>

            {/* Display Section */}
            <div className="space-y-4">
                <div className="border-b pb-2">
                    <h3 className="text-lg font-semibold">Display</h3>
                </div>

                {/* Theme Toggle */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SunMoon className="size-4" />
                        <Label className="font-medium">Dark Mode</Label>
                    </div>
                    <Switch checked={currentTheme === "dark"} onCheckedChange={toggleTheme} />
                </div>

                {/* Context Indicator Toggle */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Activity className="size-4" />
                        <Label className="font-medium">Context Usage Indicator</Label>
                    </div>
                    <Switch checked={showContextIndicator} onCheckedChange={handleContextIndicatorToggle} />
                </div>
            </div>
        </div>
    );
};
