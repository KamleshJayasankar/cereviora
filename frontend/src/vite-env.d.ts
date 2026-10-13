/// <reference types="vite/client" />

/**
 * CEREVIORA — Vite Environment Type Declarations
 *
 * This file tells TypeScript about Vite-specific globals like
 * import.meta.env and any custom environment variables.
 *
 * Variables prefixed with VITE_ are safe to expose to the browser.
 * Never put secrets in VITE_ variables.
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  // Add more env vars here as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
