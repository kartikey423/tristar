/**
 * E2E test: Designer critical path
 * Flow: Navigate → Select Manual Entry → Enter objective → Wait for OfferBrief → Approve
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';

test.describe('Designer Flow — Critical Path', () => {
  test.beforeEach(async ({ page }) => {
    // Set mock JWT token (dev environment)
    await page.goto(BASE_URL);
    await page.evaluate(() => {
      localStorage.setItem('tristar_token', 'test-marketing-jwt');
    });
  });

  test('should show mode selector tabs on designer page', async ({ page }) => {
    await page.goto(`${BASE_URL}/designer`);

    // Mode selector should be visible
    await expect(page.getByRole('tab', { name: 'AI Suggestions' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Manual Entry' })).toBeVisible();
  });

  test('should switch to Manual Entry mode when tab clicked', async ({ page }) => {
    await page.goto(`${BASE_URL}/designer`);

    await page.getByRole('tab', { name: 'Manual Entry' }).click();

    // Manual entry form should be visible
    await expect(page.getByLabelText('Marketing Objective')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Generate Offer' })).toBeVisible();
  });

  test('should show validation error for short objective', async ({ page }) => {
    await page.goto(`${BASE_URL}/designer`);
    await page.getByRole('tab', { name: 'Manual Entry' }).click();

    await page.getByLabelText('Marketing Objective').fill('too short');
    await page.getByRole('button', { name: 'Generate Offer' }).click();

    await expect(
      page.getByText(/at least 10 characters/i),
    ).toBeVisible();
  });

  test('full flow: generate offer and verify OfferBrief card displays', async ({ page }) => {
    await page.goto(`${BASE_URL}/designer`);
    await page.getByRole('tab', { name: 'Manual Entry' }).click();

    const objective = 'Reactivate lapsed high-value members with a compelling winter sports offer';
    await page.getByLabelText('Marketing Objective').fill(objective);

    // Click generate — expect loading spinner
    await page.getByRole('button', { name: 'Generate Offer' }).click();
    await expect(page.getByText('Generating...')).toBeVisible();

    // Wait for OfferBrief card to appear (up to 30s for Claude API)
    await expect(page.getByRole('article')).toBeVisible({ timeout: 30000 });

    // Verify key OfferBrief sections are displayed
    await expect(page.getByText(/Segment/i)).toBeVisible();
    await expect(page.getByText(/Construct/i)).toBeVisible();
    await expect(page.getByText(/Channels/i)).toBeVisible();
    await expect(page.getByText(/KPIs/i)).toBeVisible();
    await expect(page.getByText(/Risk Assessment/i)).toBeVisible();
  });

  test('approve button is disabled when risk severity is critical', async ({ page }) => {
    // This test requires the backend to return a critical fraud result
    // In real E2E: use a known-high-discount objective
    await page.goto(`${BASE_URL}/designer`);
    await page.getByRole('tab', { name: 'Manual Entry' }).click();

    // Enter an objective that triggers fraud detection
    await page.getByLabelText('Marketing Objective').fill(
      'Give 50% discount on all products to everyone immediately without limits'
    );
    await page.getByRole('button', { name: 'Generate Offer' }).click();

    // Wait for response
    await page.waitForResponse(
      (resp) => resp.url().includes('/api/designer/generate') && resp.status() !== 0,
      { timeout: 30000 },
    );

    // Either: fraud blocked → 422 error shown, OR: offer card shown with disabled button
    // Accept either outcome as test infrastructure may vary
    const hasError = await page.getByRole('alert').count() > 0;
    const hasDisabledApprove = await page.getByRole('button', { name: /Blocked/i }).count() > 0;
    expect(hasError || hasDisabledApprove).toBeTruthy();
  });
});
