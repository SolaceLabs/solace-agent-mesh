import React from "react";
import { User } from "lucide-react";
import { useAuthContext } from "@/lib/hooks";

export const ProfileSettings: React.FC = () => {
    const { userInfo } = useAuthContext();
    const userName = typeof userInfo?.username === "string" ? userInfo.username : "Guest";
    const userEmail = typeof userInfo?.email === "string" ? userInfo.email : "";

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4">
                <div className="flex size-20 items-center justify-center rounded-full bg-[var(--color-brand-w10)]">
                    <User className="size-10 text-[var(--color-brand-w60)]" />
                </div>
                <div>
                    <h3 className="text-lg font-semibold">{userName}</h3>
                    {userEmail && <p className="text-muted-foreground text-sm">{userEmail}</p>}
                </div>
            </div>

            <div className="space-y-4">
                <div>
                    <label className="text-sm font-medium">Username</label>
                    <div className="bg-muted mt-1.5 rounded-md border px-3 py-2">{userName}</div>
                </div>
                {userEmail && (
                    <div>
                        <label className="text-sm font-medium">Email</label>
                        <div className="bg-muted mt-1.5 rounded-md border px-3 py-2">{userEmail}</div>
                    </div>
                )}
            </div>
        </div>
    );
};
