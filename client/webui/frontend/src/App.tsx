import { RouterProvider } from "react-router-dom";

import { TextSelectionProvider } from "@/lib/components/chat/selection";
import { AuthProvider, ConfigProvider, CsrfProvider, ProjectProvider, TaskProvider, ThemeProvider, AudioSettingsProvider } from "@/lib/providers";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { createRouter } from "./router";

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 1000 * 60 * 5, // 5 minutes
            retry: (failureCount, error) => {
                // Don't retry on 4xx errors (client errors)
                if (error instanceof Error && error.message.includes("4")) {
                    return false;
                }
                return failureCount < 2;
            },
            refetchOnWindowFocus: false,
        },
        mutations: {
            retry: false,
        },
    },
});

function AppContent() {
    return <RouterProvider router={createRouter()} />;
}

function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <ThemeProvider>
                <CsrfProvider>
                    <ConfigProvider>
                        <AuthProvider>
                            <ProjectProvider>
                                <AudioSettingsProvider>
                                    <TaskProvider>
                                        <TextSelectionProvider>
                                            <AppContent />
                                        </TextSelectionProvider>
                                    </TaskProvider>
                                </AudioSettingsProvider>
                            </ProjectProvider>
                        </AuthProvider>
                    </ConfigProvider>
                </CsrfProvider>
            </ThemeProvider>
        </QueryClientProvider>
    );
}

export default App;
