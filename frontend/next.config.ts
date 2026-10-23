import type { NextConfig } from "next";

// Адрес backend. Rewrites вычисляются при сборке (next build), поэтому в Docker
// BACKEND_URL должен быть задан на этапе сборки образа (см. frontend/Dockerfile).
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Сжатие буферизует SSE (события запусков придут пачкой), поэтому отключаем его.
  compress: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
