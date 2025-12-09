import { useNavigate, useParams } from "react-router-dom";
import { Button, Header } from "@/lib/components";
import { ArrowLeft, Edit } from "lucide-react";
import { useApp } from "@/lib/hooks/useApp";

export function AppViewPage() {
    const { appId } = useParams<{ appId: string }>();
    const navigate = useNavigate();
    const { app, loading, error } = useApp(appId!);

    const handleBack = () => {
        navigate("/apps");
    };

    const handleEdit = () => {
        if (app) {
            navigate(`/apps/${app.appId}/editor`);
        }
    };

    if (loading) {
        return (
            <div className="flex h-full w-full items-center justify-center">
                <div className="text-muted-foreground">Loading app...</div>
            </div>
        );
    }

    if (error || !app) {
        return (
            <div className="flex h-full w-full flex-col">
                <Header
                    title="App View"
                    buttons={[
                        <Button key="back" variant="ghost" onClick={handleBack}>
                            <ArrowLeft className="size-4" />
                            Back
                        </Button>,
                    ]}
                />
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                        <div className="text-destructive font-semibold">Error</div>
                        <div className="text-muted-foreground">
                            {error || "App not found"}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (app.status !== "deployed") {
        return (
            <div className="flex h-full w-full flex-col">
                <Header
                    title={app.name}
                    buttons={[
                        <Button key="back" variant="ghost" onClick={handleBack}>
                            <ArrowLeft className="size-4" />
                            Back
                        </Button>,
                        <Button key="edit" variant="default" onClick={handleEdit}>
                            <Edit className="size-4" />
                            Edit App
                        </Button>,
                    ]}
                />
                <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                        <div className="font-semibold text-lg">App Not Deployed</div>
                        <div className="text-muted-foreground mt-2">
                            This app hasn't been deployed yet. Deploy it from the editor.
                        </div>
                        <Button className="mt-4" onClick={handleEdit}>
                            Go to Editor
                        </Button>
                    </div>
                </div>
            </div>
        );
    }

    // Construct URL to deployed app
    const deployedUrl = `/api/v1/apps/${app.appId}/deployed/`;

    return (
        <div className="flex h-full w-full flex-col">
            <Header
                title={app.name}
                subtitle={`Version ${app.currentVersion}`}
                buttons={[
                    <Button key="back" variant="ghost" onClick={handleBack}>
                        <ArrowLeft className="size-4" />
                        Back
                    </Button>,
                    <Button key="edit" variant="outline" onClick={handleEdit}>
                        <Edit className="size-4" />
                        Edit
                    </Button>,
                ]}
            />

            <div className="flex-1 overflow-hidden bg-background">
                <iframe
                    src={deployedUrl}
                    className="w-full h-full border-0"
                    title={app.name}
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                />
            </div>
        </div>
    );
}
