import { expect, test } from "@playwright/test";

test("mobile navigation and reveal-first practice fit the viewport", async ({ page }) => {
  await page.goto("/static/");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const tabs = await page.getByRole("navigation", { name: "Primary" }).boundingBox();
  expect(tabs?.width).toBe(390);
  expect(tabs?.y).toBeGreaterThan(700);

  await page.getByRole("button", { name: "Practice", exact: true }).click();
  await expect(page.getByRole("button", { name: "Begin practice" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.setViewportSize({ width: 320, height: 740 });
  await expectNoHorizontalOverflow(page);
  await page.getByRole("button", { name: "Begin practice" }).click();
  await expect(page.locator(".question-card")).toBeVisible();
  await expect(page.locator(".question-card input")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  await page.getByRole("button", { name: "Reveal response" }).click();
  await expect(page.getByText("Correct response")).toBeVisible();
  await expect(page.getByRole("button", { name: /Knew it/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Hunch/ })).toBeVisible();
  await page.getByRole("button", { name: /Hunch/ }).click();
  await expect(page.locator(".clue-count")).toContainText("Clue 2");
  await expectNoHorizontalOverflow(page);
});

test("anytime practice keeps the response input focused after locking in", async ({ page }) => {
  await page.goto("/static/");
  await page.getByRole("button", { name: "Practice", exact: true }).click();
  await page.getByRole("button", { name: /Anytime test prep/ }).click();
  await page.getByRole("button", { name: "Begin practice" }).click();

  const input = page.getByLabel("Your response");
  await expect(page.locator(".clue-count")).toContainText("Clue 1");
  await expect(input).toBeFocused();

  await input.fill("first answer");
  await input.press("Enter");
  await expect(page.locator(".clue-count")).toContainText("Clue 2");
  await expect(input).toBeFocused();

  // Losing focus even briefly closes the mobile keyboard, so count blurs too.
  await input.evaluate((el) => {
    (window as unknown as { blurs: number }).blurs = 0;
    el.addEventListener("blur", () => (window as unknown as { blurs: number }).blurs++);
  });
  await input.fill("second answer");
  await page.getByRole("button", { name: "Lock in response" }).click();
  await expect(page.locator(".clue-count")).toContainText("Clue 3");
  await expect(input).toBeFocused();
  expect(await page.evaluate(() => (window as unknown as { blurs: number }).blurs)).toBe(0);
});

test("all primary screens fit a narrow phone viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/static/");

  for (const [label, heading] of [
    ["Subjects", "Subjects"],
    ["History", "History"],
    ["Settings", "Settings"],
    ["Overview", "Overview"],
  ]) {
    await page.getByRole("button", { name: label, exact: true }).click();
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }
});

async function expectNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const widths = await page.evaluate(() => ({
    document: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(widths.document).toBeLessThanOrEqual(widths.viewport);
}
