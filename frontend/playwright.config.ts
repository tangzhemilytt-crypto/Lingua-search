import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: "http://127.0.0.1:8001", trace: "retain-on-failure" },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: {
    command: "python3 -m uvicorn src.app:app --host 127.0.0.1 --port 8001",
    cwd: "..",
    url: "http://127.0.0.1:8001/health",
    reuseExistingServer: !process.env.CI,
    env: {
      DATABASE_PATH: "runtime/e2e.sqlite",
      DEMO_SEED: "true",
      APP_ENV: "development",
      OPENAI_API_KEY: "",
      WORKSPACE_TOKEN: "",
    },
  },
});
