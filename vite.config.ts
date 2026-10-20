// This project uses a shared TanStack/Vite config to enable the app shell and SSR build behavior.
// Add custom Vite settings only when they are required to preserve the existing route and build setup.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
