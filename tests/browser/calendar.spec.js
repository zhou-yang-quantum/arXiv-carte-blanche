import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const original = JSON.parse(readFileSync(new URL('../fixtures/2026-10-06.json', import.meta.url), 'utf8'));

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date('2026-10-16T12:00:00'));
  await page.route('**/data/archive.json', async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.days = ['2026-10-06', '2026-10-02', '2026-09-30', '2026-01-01', '2025-12-31', '2024-02-29'].map(date => ({ ...structuredClone(original), date, title: 'arXiv-' + date }));
    await route.fulfill({ response, json: data });
  });
});

test('current-month calendar highlights only digests and selecting a day resets filters', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  const calendar = page.locator('#archive-calendar');
  await expect(calendar.getByRole('table', { name: 'October 2026' })).toBeVisible();
  await expect(calendar.locator('[data-date]')).toHaveCount(31);
  await expect(calendar.locator('[data-date]:enabled')).toHaveCount(2);
  await expect(calendar.locator('[data-date="2026-10-16"]')).toBeDisabled();
  await expect(calendar.locator('[data-date="2026-10-16"]')).toHaveAttribute('aria-current', 'date');
  // October 1 falls on Thursday (the fifth column in a Sunday-first calendar).
  await expect(calendar.locator('tbody tr').first().locator('td').nth(4).locator('button')).toHaveText('1');
  await page.getByRole('button', { name: 'Saved 0' }).click();
  await calendar.locator('[data-date="2026-10-02"]').click();
  await expect(page.locator('#page-title')).toHaveText('Le menu · 2026/10/02');
  await expect(calendar.locator('[data-date="2026-10-02"]')).toHaveAttribute('aria-pressed', 'true');
  await expect(page).toHaveURL(/#date=2026-10-02$/);
  await expect(page.locator('.paper-card')).toHaveCount(10);
  await page.screenshot({ path: '.cache/calendar-desktop.png' });
});

test('month arrows skip gaps and year selectors offer only months with digests', async ({ page }) => {
  await page.goto('/');
  const calendar = page.locator('#archive-calendar');
  await calendar.getByRole('button', { name: 'Previous month' }).click();
  await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'September 2026');
  await expect(calendar.locator('[data-date]:enabled')).toHaveCount(1);
  await calendar.getByLabel('Month', { exact: true }).selectOption('0');
  await calendar.getByRole('button', { name: 'Previous month' }).click();
  await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'December 2025');
  await calendar.getByRole('button', { name: 'Next month' }).click();
  await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'January 2026');
  await calendar.getByLabel('Year', { exact: true }).selectOption('2024');
  await calendar.getByLabel('Month', { exact: true }).selectOption('1');
  await expect(calendar.locator('[data-date]')).toHaveCount(29);
  await calendar.locator('[data-date="2024-02-29"]').click();
  await expect(page.locator('#page-title')).toHaveText('Le menu · 2024/02/29');
  await calendar.getByLabel('Year', { exact: true }).selectOption('2025');
  await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'December 2025');
  await expect(calendar.locator('.calendar-month option')).toHaveText(['December']);
  await calendar.getByRole('button', { name: 'Previous month' }).click();
  await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'February 2024');
  await expect(calendar.getByRole('button', { name: 'Previous month' })).toBeDisabled();
  await calendar.getByRole('button', { name: 'Next month' }).click();
  await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'December 2025');
  await calendar.getByRole('button', { name: 'Today', exact: true }).click();
  await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'October 2026');
  // Today opens the latest available menu when today's menu is absent.
  await expect(page.locator('#page-title')).toHaveText('Le menu · 2026/10/06');
  await expect(page.locator('#toast')).toHaveText('No menu for today yet. Showing the latest available menu.');
});

test('hidden-sidebar title calendar selects a digest and dismisses on Escape or outside click', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  const button = page.getByRole('button', { name: 'Choose a digest date', exact: true });
  await expect(button).toBeHidden();
  await page.getByRole('button', { name: 'Hide sidebar', exact: true }).click();
  await button.click();
  const popup = page.getByRole('dialog', { name: 'Choose a digest date', exact: true });
  await expect(popup).toBeVisible();
  await popup.getByRole('button', { name: 'Previous month' }).click();
  await popup.locator('[data-date="2026-09-30"]').click();
  await expect(popup).toBeHidden();
  await expect(page.locator('#page-title')).toHaveText('Le menu · 2026/09/30');
  await button.click();
  await expect(popup.getByRole('table')).toHaveAttribute('aria-label', 'September 2026');
  await page.keyboard.press('Escape');
  await expect(popup).toBeHidden();
  await expect(button).toBeFocused();
  await button.click();
  await page.locator('#page-title').click();
  await expect(popup).toBeHidden();
  await page.reload();
  await expect(button).toBeVisible();
  await button.click();
  await page.screenshot({ path: '.cache/calendar-popover.png' });
});

test('mobile calendar stays within the screen in both themes and supports keyboard selection', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto('/');
  const button = page.getByRole('button', { name: 'Choose a digest date', exact: true });
  await button.click();
  const popup = page.getByRole('dialog', { name: 'Choose a digest date', exact: true });
  await expect(popup).toBeVisible();
  const rect = await popup.boundingBox();
  expect(rect.x).toBeGreaterThanOrEqual(0);
  expect(rect.x + rect.width).toBeLessThanOrEqual(320);
  expect(rect.y + rect.height).toBeLessThanOrEqual(700);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '.cache/calendar-mobile-dark.png' });
  await popup.locator('[data-date="2026-10-02"]').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#page-title')).toHaveText('Le menu · 2026/10/02');
  await expect(popup).toBeHidden();
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await button.click();
  await expect(popup).toBeVisible();
  await page.screenshot({ path: '.cache/calendar-mobile-light.png' });
});

test('both calendars prevent navigating before the first digest month', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.route('**/data/archive.json', async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.days = ['2026-10-16', '2026-10-08'].map(date => ({ ...structuredClone(original), date, title: 'arXiv-' + date }));
    await route.fulfill({ response, json: data });
  });
  await page.goto('/');
  for (const id of ['archive-calendar', 'popup-calendar']) {
    if (id === 'popup-calendar') {
      await page.getByRole('button', { name: 'Hide sidebar', exact: true }).click();
      await page.getByRole('button', { name: 'Choose a digest date', exact: true }).click();
    }
    const calendar = page.locator('#' + id);
    await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'October 2026');
    await expect(calendar.getByRole('button', { name: 'Previous month' })).toBeDisabled();
    await expect(calendar.locator('.calendar-year option')).toHaveText(['2026']);
    await expect(calendar.locator('.calendar-month option')).toHaveText(['October']);
    await expect(calendar.getByRole('button', { name: 'Next month' })).toBeDisabled();
  }
});

test('available months and years expand with new digests and skip empty years', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const dates = ['2026-10-08'];
  await page.route('**/data/archive.json', async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.days = dates.map(date => ({ ...structuredClone(original), date, title: 'arXiv-' + date }));
    await route.fulfill({ response, json: data });
  });
  await page.goto('/');
  await expect(page.locator('#archive-calendar .calendar-year option')).toHaveText(['2026']);
  dates.unshift('2028-11-03', '2028-03-01');
  await page.reload();
  for (const id of ['archive-calendar', 'popup-calendar']) {
    if (id === 'popup-calendar') {
      await page.getByRole('button', { name: 'Hide sidebar', exact: true }).click();
      await page.getByRole('button', { name: 'Choose a digest date', exact: true }).click();
    }
    const calendar = page.locator('#' + id);
    await expect(calendar.locator('.calendar-year option')).toHaveText(['2026', '2028']);
    await calendar.getByRole('button', { name: 'Next month' }).click();
    await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'March 2028');
    await expect(calendar.locator('.calendar-month option')).toHaveText(['March', 'November']);
    await calendar.getByRole('button', { name: 'Next month' }).click();
    await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'November 2028');
    await expect(calendar.getByRole('button', { name: 'Next month' })).toBeDisabled();
    await calendar.getByLabel('Year', { exact: true }).selectOption('2026');
    await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'October 2026');
    await expect(calendar.locator('.calendar-month option')).toHaveText(['October']);
  }
});

test('when the current month has no digests the calendar opens the latest available month', async ({ page }) => {
  await page.clock.setFixedTime(new Date('2030-01-15T12:00:00'));
  await page.goto('/');
  const calendar = page.locator('#archive-calendar');
  await expect(calendar.getByRole('table')).toHaveAttribute('aria-label', 'October 2026');
  await expect(calendar.getByRole('button', { name: 'Today', exact: true })).toBeEnabled();
  await expect(calendar.getByRole('button', { name: 'Next month' })).toBeDisabled();
  await calendar.locator('[data-date="2026-10-02"]').click();
  await calendar.getByRole('button', { name: 'Today', exact: true }).click();
  await expect(page.locator('#page-title')).toHaveText('Le menu · 2026/10/06');
});

for (const calendarId of ['archive-calendar', 'popup-calendar']) {
  test(`Today opens today's menu from ${calendarId} and excludes future menus after midnight`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.route('**/data/archive.json', async route => {
      const response = await route.fetch();
      const data = await response.json();
      data.days = ['2026-10-20', '2026-10-16', '2026-09-30'].map(date => ({ ...structuredClone(original), date, title: 'arXiv-' + date }));
      await route.fulfill({ response, json: data });
    });
    await page.goto('/#date=2026-09-30&saved=1');
    if (calendarId === 'popup-calendar') {
      await page.getByRole('button', { name: 'Hide sidebar', exact: true }).click();
      await page.getByRole('button', { name: 'Choose a digest date', exact: true }).click();
    }
    const calendar = page.locator('#' + calendarId);
    await calendar.getByRole('button', { name: 'Today', exact: true }).click();
    await expect(page.locator('#page-title')).toHaveText('Le menu · 2026/10/16');
    await expect(page).toHaveURL(/#date=2026-10-16$/);
    await expect(page.locator('#calendar-popover')).toBeHidden();
    // A page left open overnight must use the new local date.
    await page.clock.setFixedTime(new Date('2026-10-17T12:00:00'));
    if (calendarId === 'popup-calendar') await page.getByRole('button', { name: 'Choose a digest date', exact: true }).click();
    await calendar.getByRole('button', { name: 'Today', exact: true }).click();
    await expect(page.locator('#page-title')).toHaveText('Le menu · 2026/10/16');
    await expect(page.locator('#toast')).toHaveText('No menu for today yet. Showing the latest available menu.');
  });
}
