import { test, expect } from "@playwright/test";
async function navigate(page: any, name: string) {
  const menu = page.getByRole("button", { name: "Toggle navigation" });
  if (await menu.isVisible()) await menu.click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name, exact: false })
    .click();
}
test("library, multilingual excerpt search, answer citations, and empty state", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Big ideas. No language barriers." }),
  ).toBeVisible();
  await expect(
    page.getByText("The multilingual mind", { exact: true }),
  ).toBeVisible();
  await navigate(page, "Document library");
  await page.getByRole("textbox", { name: "Filter documents" }).fill("RAG");
  await expect(
    page.getByRole("button", { name: "A field guide to RAG", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "A field guide to RAG", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Retrieval-augmented generation",
  );
  await page.getByRole("button", { name: "Close dialog" }).click();
  await navigate(page, "Explore & search");
  await page
    .getByRole("textbox", { name: "What are you looking for?" })
    .fill("检索");
  await page
    .getByRole("button", { name: "Search library", exact: true })
    .click();
  await expect(page.locator(".source-card").first()).toBeVisible();
  await page
    .getByRole("textbox", { name: "What are you looking for?" })
    .fill("zxqv-unmatched");
  await page
    .getByRole("button", { name: "Search library", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "No supporting passages found" }),
  ).toBeVisible();
  await navigate(page, "Ask your documents");
  await page
    .getByRole("textbox", { name: "What would you like to understand?" })
    .fill("language identity");
  await page.getByRole("button", { name: "Ask question", exact: true }).click();
  await expect(
    page.getByText("EVIDENCE PREVIEW", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Open citation 1", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("PAGE 1");
  await page.getByRole("button", { name: "Close dialog" }).click();
  expect(errors).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("settings explains model keys and rejects invalid file types", async ({
  page,
}) => {
  await page.goto("/");
  const menu = page.getByRole("button", { name: "Toggle navigation" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Settings & connection" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Never paste a model API key",
  );
  await page.keyboard.press("Escape");
  await page
    .getByLabel("Upload PDF", { exact: true })
    .setInputFiles({
      name: "bad.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("bad"),
    });
  await expect(page.getByRole("alert")).toContainText("Please choose a PDF");
});
