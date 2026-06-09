/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    NEXT_PUBLIC_WS_URL:  process.env.NEXT_PUBLIC_WS_URL  || "ws://localhost:8000",
  },
  transpilePackages: ["@vladmandic/face-api"],
  webpack: (config, { isServer }) => {
    // face-api / tfjs use dynamic require for backends — suppress warnings
    config.ignoreWarnings = [
      { module: /@vladmandic\/face-api/ },
      { module: /@tensorflow/ },
    ]
    // Prevent tfjs backend dynamic requires from producing /_next/undefined chunks
    if (!isServer) {
      config.resolve.alias = {
        ...config.resolve.alias,
        "@tensorflow/tfjs-backend-wasm": false,
        "@tensorflow/tfjs-node": false,
        "@tensorflow/tfjs-node-gpu": false,
      }
    }
    return config
  },
}

module.exports = nextConfig
