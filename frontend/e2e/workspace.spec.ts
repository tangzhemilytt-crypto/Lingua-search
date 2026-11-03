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
const ownerToken = "test-owner-token-for-public-demo-32-characters";
async function ownerLogin(page: any) {
  const menu = page.getByRole("button", { name: "Toggle navigation" });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole("button", { name: "Settings & connection" }).click();
  await page.getByRole("textbox", { name: "Workspace access token", exact: true }).fill(ownerToken);
  await page.getByRole("button", { name: "Save connection", exact: true }).click();
  await expect(page.locator(".private-access")).toBeVisible();
}
test("public demo hides management; owner can sign in and upload", async ({page}) => {
  await page.goto("/");
  await expect(page.getByText("Public demo · No login needed", {exact:true})).toBeVisible();
  await expect(page.getByLabel("Upload PDF", {exact:true})).toHaveCount(0);
  await navigate(page, "Document library");
  await expect(page.getByText("Read-only sample collection", {exact:true})).toBeVisible();
  await expect(page.getByRole("button", {name:/^Delete /})).toHaveCount(0);
  await expect(page.getByRole("button", {name:/^Rename /})).toHaveCount(0);
  await ownerLogin(page);
  await page.getByLabel("Upload PDF", {exact:true}).setInputFiles({name:"bad.txt",mimeType:"text/plain",buffer:Buffer.from("bad")});
  await expect(page.getByRole("alert")).toContainText("Please choose a PDF");
  await page.getByRole("button", {name:"Sign out to public demo",exact:true}).click();
  await expect(page.getByText("Public demo · No login needed", {exact:true})).toBeVisible();
  await expect(page.getByLabel("Upload PDF", {exact:true})).toHaveCount(0);
});
test("invalid saved token does not block public access", async ({page}) => {
  await page.addInitScript(()=>sessionStorage.setItem("lingua-token","invalid-token"));
  await page.goto("/");
  await expect(page.getByText("The multilingual mind", {exact:true})).toBeVisible();
  await expect(page.getByText("Public demo · No login needed", {exact:true})).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("alert")).toHaveCount(0);
});
test("a late private answer cannot leak into the public view after sign-out", async ({page}) => {
  await page.goto("/");
  await ownerLogin(page);
  await navigate(page,"Ask your documents");
  let release!:()=>void;
  let reached!:()=>void;
  const gate=new Promise<void>(resolve=>{release=resolve;});
  const intercepted=new Promise<void>(resolve=>{reached=resolve;});
  await page.route("**/api/ask",async route=>{
    reached(); await gate;
    await route.fulfill({json:{answer:"PRIVATE_CANARY_RESPONSE",citations:[],mode:"ai"}});
  });
  await page.getByRole("textbox",{name:"What would you like to understand?"}).fill("private question");
  await page.getByRole("button",{name:"Ask question",exact:true}).click();
  await intercepted;
  await page.getByRole("button",{name:"Sign out to public demo",exact:true}).click();
  await expect(page.getByText("Public demo · No login needed",{exact:true})).toBeVisible();
  const response=page.waitForResponse("**/api/ask");release();await response;
  await expect(page.getByText("PRIVATE_CANARY_RESPONSE",{exact:true})).toHaveCount(0);
  await expect(page.locator(".answer-panel")).toHaveCount(0);
});
