import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

// The app is a static export served by the local FastAPI server (app/backend/server.py).
// In development, `next dev` forwards /api calls to that server.
const config: NextConfig = {
  output: "export",
  distDir: "out",
  images: { unoptimized: true },
  poweredByHeader: false,
  ...(isDev && {
    async rewrites() {
      return [{ source: "/api/:path*", destination: "http://127.0.0.1:8765/api/:path*" }];
    },
  }),
};

export default config;
