import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  async rewrites() {
    const gatewayHost = process.env.GATEWAY_BACKEND_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${gatewayHost}/api/:path*`,
      },
      {
        source: "/v1/:path*",
        destination: `${gatewayHost}/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${gatewayHost}/health`,
      },
    ];
  },
};

export default nextConfig;
