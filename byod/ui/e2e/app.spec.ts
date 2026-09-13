import { expect, test } from '@playwright/test';
import path from 'node:path';

test('workspace switcher takes keyboard focus and restores it on Escape', async ({ page }) => {
  await page.goto('/');
  const trigger = page.getByRole('button', { name: 'Workspaces Ctrl K' });
  await trigger.focus();
  await page.keyboard.press('Control+k');
  await expect(page.getByLabel('Find workspace')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
});

test('local document chat, real citations, persistence, and keyboard navigation', async ({ page, request }) => {
  const failures: string[] = [], externalRequests: string[] = [];
  page.on('pageerror', error => failures.push(error.message));
  page.on('console', message => { if (message.type() === 'error') failures.push(message.text()); });
  page.on('request', req => { if (new URL(req.url()).hostname !== '127.0.0.1') externalRequests.push(req.url()); });
  await page.goto('/');
  await expect(page.getByText('BYOD', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'New workspace', exact: true }).click();
  const workspaceName = `Biology acceptance ${Date.now()}`;
  await page.getByLabel('Workspace name').fill(workspaceName);
  const creation = page.waitForResponse(response => response.url().endsWith('/api/workspaces') && response.request().method() === 'POST');
  await page.getByRole('dialog', { name: 'New workspace', exact: true }).getByRole('button', { name: 'Create workspace', exact: true }).click();
  const workspace = (await (await creation).json()).id as number;
  try {
    await expect(page.getByRole('heading', { name: workspaceName, exact: true })).toBeVisible();
    await page.getByRole('button', { name: /^Documents/ }).click();
    const documents = page.getByRole('dialog', { name: 'Documents', exact: true });
    await documents.getByRole('button', { name: 'Add files', exact: true }).click();
    const files = ['reading.pdf', 'notes.docx', 'lecture.pptx'].map(file => path.resolve('../../tests/fixtures', file));
    await documents.getByLabel('File paths, one per line').fill(files.join('\n'));
    await documents.getByRole('button', { name: 'Add documents', exact: true }).click();
    await expect(documents.locator('.status.indexed')).toHaveCount(3, { timeout: 120000 });
    await page.keyboard.press('Escape');
    await expect(documents).not.toBeVisible();
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    const settings = page.getByRole('dialog', { name: 'Settings', exact: true });
    await settings.getByRole('button', { name: /Ollama/ }).click();
    await settings.getByRole('combobox', { name: 'Model', exact: true }).selectOption({ label: 'qwen3.6:latest' });
    await settings.getByRole('button', { name: 'Save settings', exact: true }).click();
    await expect(settings.getByText('Settings saved.', { exact: true })).toBeVisible();
    await settings.getByRole('button', { name: 'Close', exact: true }).click();
    await page.getByRole('combobox', { name: 'Document scope' }).selectOption({ label: 'lecture.pptx' });
    await page.getByLabel('Question', { exact: true }).fill('In one sentence, how do plants turn sunshine into stored energy? Cite the documents.');
    await page.getByRole('button', { name: 'Send question', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Stop reply', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Stop reply', exact: true })).not.toBeVisible({ timeout: 720000 });
    await expect(page.locator('.message.assistant .citation').first()).toBeVisible();
    await page.locator('.message.assistant .citation').first().click();
    const source = page.getByRole('dialog', { name: 'Source', exact: true });
    await expect(source.locator('.source-text')).toContainText(/sunlight|light energy|chemical energy/);
    await expect(source.locator('.locator-label')).toContainText(/p\. |slide |Plant Biology/);
    await page.screenshot({ path: '../../docs/evidence/source-preview.png', fullPage: true });
    await page.keyboard.press('Escape');
    await page.screenshot({ path: '../../docs/evidence/chat.png', fullPage: true });
    await page.reload();
    await page.getByRole('navigation', { name: 'Workspaces' }).getByRole('button', { name: `${workspaceName} 3`, exact: true }).click();
    await page.getByRole('navigation', { name: 'Chats', exact: true }).locator('.chat-select').first().click();
    await expect(page.locator('.message.assistant .citation').first()).toBeVisible();
    await page.keyboard.press('Control+k');
    await expect(page.getByLabel('Find workspace')).toBeFocused();
    await page.getByLabel('Find workspace').fill(workspaceName);
    await page.keyboard.press('Tab');
    await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog', { name: 'Switch workspace', exact: true })).not.toBeVisible();
    await page.keyboard.press('Control+n');
    await expect(page.getByLabel('Question', { exact: true })).toBeFocused();
    await expect(page.getByRole('heading', { name: workspaceName, exact: true })).toBeVisible();
    const outline = await page.getByLabel('Question', { exact: true }).evaluate(element => getComputedStyle(element).outlineStyle);
    expect(outline).not.toBe('none');
    await page.getByLabel('Question', { exact: true }).fill('What is the syntax of a Rust lifetime parameter?');
    await page.keyboard.press('Enter');
    await expect(page.getByText('Nothing in this workspace matches that question.', { exact: true })).toBeVisible();
    expect(failures).toEqual([]);
    expect(externalRequests).toEqual([]);
  } finally { await request.delete(`/api/workspaces/${workspace}`).catch(() => {}); }
});

test('workspace creation and removal keep the correct selection', async ({ page, request }) => {
  const ids: number[] = [];
  await page.goto('/');
  try {
    for (const label of ['First', 'Second']) {
      await page.getByRole('button', { name: 'New workspace', exact: true }).click();
      const name = `${label} selection ${Date.now()}`;
      await page.getByLabel('Workspace name').fill(name);
      const response = page.waitForResponse(r => r.url().endsWith('/api/workspaces') && r.request().method() === 'POST');
      await page.getByRole('dialog', { name: 'New workspace', exact: true }).getByRole('button', { name: 'Create workspace', exact: true }).click();
      ids.push((await (await response).json()).id);
      await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    }
    await page.getByRole('button', { name: /^Documents/ }).click();
    await page.getByRole('button', { name: 'Remove workspace', exact: true }).click();
    await page.getByRole('dialog', { name: 'Remove workspace', exact: true }).getByRole('button', { name: 'Remove workspace', exact: true }).click();
    await expect(page.getByRole('heading', { name: /^First selection/ })).toBeVisible();
  } finally { for (const id of ids) await request.delete(`/api/workspaces/${id}`); }
});
