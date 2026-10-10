import { expect, test } from "@playwright/test";

test("sign up → onboarding → lesson → progress persists", async ({ page }) => {
  const email = `e2e${Date.now()}@example.com`;
  await page.goto("/signup");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign up" }).click();

  await expect(page.getByText("Have you studied Japanese before?")).toBeVisible();
  for (let i = 0; i < 10; i++) {
    const options = page.locator("[role=radio], [role=checkbox]");
    await options.first().click();
    if (i < 9) await page.getByRole("button", { name: "Continue" }).click();
  }
  await page.getByRole("button", { name: "Start from scratch" }).click();

  await expect(page.getByText("Today's next step")).toBeVisible();
  await page.getByRole("link", { name: /Start lesson/ }).click();
  await page.getByRole("button", { name: "Start lesson" }).click();

  const cont = page.getByRole("button", { name: "Continue" });
  const finish = page.getByRole("button", { name: /Finish lesson/ });
  const counter = page.locator("main").getByText(/^\d+\/\d+$/);
  for (let step = 0; step < 30; step++) {
    if (await finish.isVisible().catch(() => false) && await finish.isEnabled()) break;
    if ((await cont.isVisible()) && (await cont.isEnabled())) {
      const before = await counter.textContent();
      await cont.click();
      await expect(counter).not.toHaveText(before ?? "");
      continue;
    }
    const typed = page.getByLabel(/Your answer|Type your answer/).first();
    const choice = page.locator("main button.jp:not([disabled])").first();
    if (await page.getByText("Type instead").isVisible().catch(() => false)) {
      await page.getByText("Type instead").click();
    }
    if (await typed.isVisible().catch(() => false)) {
      await typed.fill("こんにちは");
      await page.getByRole("button", { name: "Check" }).click();
    } else {
      await choice.click();
      const check = page.getByRole("button", { name: "Check" });
      if (await check.isVisible()) {
        while (await page.locator("main button.jp:not([disabled])").count()) {
          await page.locator("main button.jp:not([disabled])").first().click();
        }
        await check.click();
      }
    }
    await expect(cont.or(finish).first()).toBeEnabled();
  }
  await page.getByRole("button", { name: /Finish lesson/ }).click();
  await expect(page.getByText(/Lesson (complete|finished)/)).toBeVisible();

  await page.goto("/progress");
  await expect(page.getByText("Exercises")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Lessons").first()).toBeVisible();
  await expect(page.getByText(/1\/13/)).toBeVisible();
});

test("protected routes redirect to login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});
