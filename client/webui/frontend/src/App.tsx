import { RouterProvider } from "react-router-dom";

import { TextSelectionProvider } from "@/lib/components/chat/selection";
import { AuthProvider, ConfigProvider, CsrfProvider, ProjectProvider, TaskProvider, ThemeProvider, AudioSettingsProvider, QueryProvider, SSEProvider } from "@/lib/providers";

import { createRouter } from "./router";

function AppContent() {
    return <RouterProvider router={createRouter()} />;
}

function App() {
    return (
        <QueryProvider>
            <ThemeProvider>
                <CsrfProvider>
                    <ConfigProvider>
                        <AuthProvider>
                            <SSEProvider>
                                <ProjectProvider>
                                    <AudioSettingsProvider>
                                        <TaskProvider>
                                            <TextSelectionProvider>
                                                <AppContent />
                                            </TextSelectionProvider>
                                        </TaskProvider>
                                    </AudioSettingsProvider>
                                </ProjectProvider>
                            </SSEProvider>
                        </AuthProvider>
                    </ConfigProvider>
                </CsrfProvider>
            </ThemeProvider>
        </QueryProvider>
    );
}

export default App;
