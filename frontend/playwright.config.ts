import { defineConfig, devices } from "@playwright/test";

// Expects backend (AI_PROVIDER=mock) on :8000 and frontend on :3000. See README.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 180_000,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
