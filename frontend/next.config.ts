import type { NextConfig } from "next";
import { resolve } from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: resolve(__dirname),
  reactStrictMode: true,
};

export default nextConfig;
