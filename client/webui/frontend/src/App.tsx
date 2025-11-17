import { RouterProvider } from "react-router-dom";

import { TextSelectionProvider } from "@/lib/components/chat/selection";
import { AuthProvider, ConfigProvider, CsrfProvider, ProjectProvider, TaskProvider, ThemeProvider } from "@/lib/providers";

import { createRouter } from "./router";

function AppContent() {
    return <RouterProvider router={createRouter()} />;
}

function App() {
    return (
        <ThemeProvider>
            <CsrfProvider>
                <ConfigProvider>
                    <AuthProvider>
                        <ProjectProvider>
                            <TaskProvider>
                                <TextSelectionProvider>
                                    <AppContent />
                                </TextSelectionProvider>
                            </TaskProvider>
                        </ProjectProvider>
                    </AuthProvider>
                </ConfigProvider>
            </CsrfProvider>
        </ThemeProvider>
    );
}

export default App;
