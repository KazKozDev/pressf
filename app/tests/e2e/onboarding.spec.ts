import { test, expect, _electron as electron, type ElectronApplication, type Page } from "@playwright/test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

async function launch(home: string, onboarding: boolean): Promise<{ app: ElectronApplication; page: Page }> {
  const env: Record<string, string> = { ...process.env, PRESSF_HOME: home, PRESSF_E2E: "1" };
  if (onboarding) env.PRESSF_E2E_ONBOARDING = "1";
  const app = await electron.launch({ args: ["."], env });
  return { app, page: await app.firstWindow() };
}

test("first run shows onboarding, second run does not", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-onb-"));
  // first run: opt in → welcome visible, dismiss it (persists onboardingSeen)
  let { app, page } = await launch(home, true);
  try {
    await expect(page.getByRole("heading", { name: "Welcome to PressF" })).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Start with the sample" })).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Get started", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Welcome to PressF" })).toHaveCount(0);
  } finally {
    await app.close();
  }
  // second run in the SAME home, still opted in: persisted seen → no welcome
  ({ app, page } = await launch(home, true));
  try {
    await page.waitForTimeout(600);
    await expect(page.getByRole("heading", { name: "Welcome to PressF" })).toHaveCount(0);
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("sample onboarding opens a document-backed finding directly", async () => {
  const home = mkdtempSync(path.join(tmpdir(), "pressf-sample-"));
  const { app, page } = await launch(home, true);
  try {
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await page.getByRole("button", { name: "Show the first real error", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Is the answer correct?" })).toBeVisible();
    await expect(page.getByText("Looks wrong", { exact: true })).toBeVisible();
  } finally {
    await app.close();
    rmSync(home, { recursive: true, force: true });
  }
});
