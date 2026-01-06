import { RouterProvider } from "react-router-dom";

import { TextSelectionProvider } from "@/lib/components/chat/selection";
import { AuthProvider, ConfigProvider, CsrfProvider, ProjectProvider, TaskProvider, ThemeProvider, AudioSettingsProvider, queryClient } from "@/lib/providers";

import { createRouter } from "./router";
import { QueryClientProvider } from "@tanstack/react-query";

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
