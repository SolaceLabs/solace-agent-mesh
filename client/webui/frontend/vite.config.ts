import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

export default defineConfig(({ mode }) => {

  const env = loadEnv(mode, process.cwd(), ''); // Load env vars from frontend dir

  // Determine the backend port. Use env var or default to 8000.
  const backendPort = env.VITE_BACKEND_PORT || process.env.FASTAPI_PORT || '8000';
  const backendTarget = `http://localhost:${backendPort}`;

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    build: { // Add build configuration
      outDir: 'static', // Output build files to the 'static' directory
      emptyOutDir: true, // Clear the directory before building
      rollupOptions: {
        input: {
          main: 'index.html',
          authCallback: 'auth-callback.html',
        },
      },
    },
    server: {
      proxy: {
        // Proxy requests starting with /api to the backend server
        '/api': {
          target: backendTarget, // Use the determined backend URL (e.g., http://localhost:8000)
          changeOrigin: true, // Recommended for virtual hosted sites
          secure: false, // Disable SSL verification if backend is HTTP
          // No rewrite needed if backend paths also start with /api
        },
      },
      port: 3000, // Explicitly set frontend dev server port (optional)
      host: true, // Allow access from network (optional)
    },
  };
});
