import { useEffect } from "react";

import { consumePostLoginRedirect } from "@/lib/utils/url";

function AuthCallback() {
    useEffect(() => {
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const accessToken = params.get("access_token");
        const samAccessToken = params.get("sam_access_token");
        const refreshToken = params.get("refresh_token");

        if (samAccessToken) {
            localStorage.setItem("sam_access_token", samAccessToken);
        }
        if (accessToken) {
            localStorage.setItem("access_token", accessToken);
            if (refreshToken) {
                localStorage.setItem("refresh_token", refreshToken);
            }
            // Redirect back to the URL the user left from (restores embedded-chat
            // params dropped by the IdP round-trip), or "/" if none was stashed.
            window.location.href = consumePostLoginRedirect();
        } else {
            console.error("AuthCallback: No access token found in URL hash.");
        }
    }, []);

    return <div>Loading...</div>;
}

export default AuthCallback;
