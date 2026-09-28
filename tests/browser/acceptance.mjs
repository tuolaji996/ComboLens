import { chromium } from 'playwright';
import { readFile } from 'fs/promises';
import { mkdir } from 'fs/promises';
import { strictEqual, deepStrictEqual, ok } from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:5173';
const API_URL = process.env.API_URL || 'http://127.0.0.1:8000';

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 1100 },
  { name: 'mobile', width: 390, height: 844 },
  { name: 'mobile-alt', width: 375, height: 812 }
];

async function checkOverflow(page) {
  const result = await page.evaluate(() => {
    const docWidth = document.documentElement.scrollWidth;
    const viewWidth = window.innerWidth;
    const main = document.querySelector('main');
    const mainWidth = main ? main.scrollWidth : 0;
    return { docWidth, viewWidth, mainWidth };
  });

  ok(result.docWidth <= result.viewWidth, `Document overflow: scrollWidth ${result.docWidth} > innerWidth ${result.viewWidth}`);
  ok(result.mainWidth <= result.viewWidth, `Main overflow: ${result.mainWidth} > ${result.viewWidth}`);
}

async function run() {
  console.log('Starting browser acceptance tests...');

  let browser;
  try {
    browser = await chromium.launch();
    const context = await browser.newContext({
      viewport: VIEWPORTS[0],
      timezoneId: 'America/Los_Angeles'
    });
    const page = await context.newPage();

    const jsErrors = [];
    const networkRequests = [];

    page.on('pageerror', err => jsErrors.push(err.message));
    page.on('console', msg => {
      if (msg.type() === 'error' && !msg.text().includes('net::ERR_')) {
        jsErrors.push(msg.text());
      }
    });
    page.on('request', req => {
      if (req.url().includes('/api/v1')) {
        networkRequests.push(req.method());
      }
    });

    // Navigate to app
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    // Assert no JS errors
    strictEqual(jsErrors.length, 0, `JS errors detected: ${jsErrors.join(', ')}`);

    // Verify tabs present
    const strategiesTab = page.getByRole('tab', { name: /strategies/i });
    const underlyingsTab = page.getByRole('tab', { name: /underlyings/i });
    const rawTab = page.getByRole('tab', { name: /raw/i });

    await strategiesTab.waitFor({ state: 'visible' });
    await underlyingsTab.waitFor({ state: 'visible' });
    await rawTab.waitFor({ state: 'visible' });

    // Verify default tab selected
    const isSelected = await strategiesTab.getAttribute('aria-selected');
    strictEqual(isSelected, 'true', 'Strategies tab must be selected by default');

    // Verify search and refresh
    await page.getByRole('textbox', { name: /search/i }).waitFor({ state: 'visible' });
    await page.getByRole('button', { name: /refresh/i }).waitFor({ state: 'visible' });

    // Fetch API data and fixture for comparison
    const apiResponse = await page.request.get(`${API_URL}/api/v1/positions`);
    const apiPositions = await apiResponse.json();
    const fixtureRaw = await readFile(join(__dirname, '../../fixtures/mock_portfolio.json'), 'utf-8');
    const fixtureData = JSON.parse(fixtureRaw);

    // Deep compare API with fixture
    deepStrictEqual(apiPositions, fixtureData.positions, 'API positions must match fixture positions exactly');
    console.log('✓ API positions match fixture');

    const strategiesResponse = await page.request.get(`${API_URL}/api/v1/strategies`);
    const strategiesInFixture = await strategiesResponse.json();

    // Check strategy cards visible
    const strategyCards = page.locator('[data-testid="strategy-card"]');
    await strategyCards.first().waitFor({ state: 'visible' });
    const totalCards = await strategyCards.count();
    strictEqual(totalCards, strategiesInFixture.length, `Expected ${strategiesInFixture.length} strategy cards, got ${totalCards}`);
    console.log('✓ Strategy card count matches expected');

    const unhCard = page.locator('[data-testid="strategy-card"]').filter({ hasText: 'UNH' }).filter({ hasText: 'Calendar Call' });
    await unhCard.waitFor({ state: 'visible' });

    const dramCard = page.locator('[data-testid="strategy-card"]').filter({ hasText: 'DRAM' }).filter({ hasText: 'Collar' });
    await dramCard.waitFor({ state: 'visible' });

    const nvdaCard = page.locator('[data-testid="strategy-card"]').filter({ hasText: 'NVDA' }).filter({ hasText: 'Long Call' });
    await nvdaCard.waitFor({ state: 'visible' });

    const spmoCard = page.locator('[data-testid="strategy-card"]').filter({ hasText: 'SPMO' }).filter({ hasText: 'Long Call' });
    await spmoCard.waitFor({ state: 'visible' });

    console.log('✓ Strategy cards visible');

    strictEqual(await page.title(), 'ComboLens');
    await page.getByRole('heading', { name: 'ComboLens', exact: true }).waitFor();
    await page.getByText('IBKR gives me legs. ComboLens tells me what I actually own.', { exact: true }).waitFor();
    async function assertMetric(card, label, expected) {
      const metric = card.locator('.card-metric').filter({ has: page.getByText(label, { exact: true }) });
      strictEqual(await metric.locator('.value').textContent(), expected);
    }
    await assertMetric(unhCard, 'Unrealized P&L', '-$34.70');
    await assertMetric(unhCard, 'Since opening (net)', '-$38.60');
    await assertMetric(nvdaCard, 'Unrealized P&L', '$320.00');
    await assertMetric(nvdaCard, 'Since opening (net)', '$363.05');
    await nvdaCard.getByText('Mock history', { exact: true }).waitFor();
    await nvdaCard.getByRole('button', { name: /expand/i }).click();
    const breakdown = nvdaCard.locator('.performance-breakdown');
    ok((await breakdown.textContent()).includes('$45.00'));
    ok((await breakdown.textContent()).includes('$1.95'));
    await nvdaCard.getByRole('button', { name: /collapse/i }).click();
    const unavailable = strategyCards.filter({ hasText: /QQQ|XYZ/ });
    for (let index = 0; index < await unavailable.count(); index++) {
      await assertMetric(unavailable.nth(index), 'Since opening (net)', '—');
    }
    console.log('✓ ComboLens branding and separate strategy P&L verified');

    // Expand UNH and verify legs with dates
    const expandButton = unhCard.getByRole('button', { name: /expand/i });
    await expandButton.click();

    const legsContainer = unhCard.locator('.legs');
    await legsContainer.waitFor({ state: 'visible' });

    const legsText = await legsContainer.textContent();

    // Check for -3 and +3 legs (short and long) and dates
    ok(legsText.includes('-3'), 'UNH should show -3 short leg');
    ok(legsText.includes('+3'), 'UNH should show +3 long leg');
    ok(legsText.includes('Oct') && legsText.includes('16'), 'UNH should show Oct 16 expiration');
    ok(legsText.includes('Nov') && legsText.includes('20'), 'UNH should show Nov 20 expiration');

    console.log('✓ UNH legs expanded and verified');

    // Screenshot after expansion (desktop)
    const screenshotsDir = join(__dirname, '../../docs/screenshots');
    await mkdir(screenshotsDir, { recursive: true });
    await page.screenshot({ animations: 'disabled', path: join(screenshotsDir, 'desktop-1440.png') });
    await page.screenshot({ animations: 'disabled', path: join(screenshotsDir, 'desktop-overview.png') });
    await page.screenshot({ animations: 'disabled', path: join(screenshotsDir, 'desktop-full.png'), fullPage: true });
    console.log('✓ Desktop screenshot saved');

    // Test search
    const searchBox = page.getByRole('textbox', { name: /search/i });
    await searchBox.fill('NVDA');
    await page.locator('[data-testid="strategy-card"]:visible').first().waitFor({ state: 'visible' });

    const visibleCards = await page.locator('[data-testid="strategy-card"]:visible').count();
    ok(visibleCards >= 1, 'NVDA search should show at least one card');

    // Check DRAM not visible
    const dramVisible = await dramCard.isVisible();
    strictEqual(dramVisible, false, 'DRAM should be filtered out by NVDA search');

    console.log('✓ Search filters working');

    // Empty search
    await searchBox.fill('ZZZNONEXISTENT');
    const noMatchesMsg = page.getByText(/No matching symbols/i);
    await noMatchesMsg.waitFor({ state: 'visible', timeout: 2000 });

    console.log('✓ Empty search message shown');

    // Clear search
    await searchBox.clear();
    await unhCard.waitFor({ state: 'visible' });

    console.log('✓ Search clear working');

    // Test Underlyings tab
    await underlyingsTab.click();
    await page.waitForLoadState('networkidle');

    const underlyingContent = await page.textContent('body');
    ok(underlyingContent.includes('UNH'), 'Underlyings view should show UNH');
    ok(underlyingContent.includes('DRAM'), 'Underlyings view should show DRAM');

    console.log('✓ Underlyings tab working');

    // Test Raw Positions tab
    await rawTab.click();
    await page.waitForLoadState('networkidle');

    // Look for details/summary element with specific text
    const detailsSummary = page.locator('summary').filter({ hasText: /Normalized record/i }).first();
    await detailsSummary.waitFor({ state: 'visible' });
    await detailsSummary.click();

    const bodyText = await page.textContent('body');
    ok(bodyText.includes('position_id') || bodyText.includes('id'), 'Normalized record JSON should show position_id or id');
    ok(bodyText.includes('quantity'), 'Normalized record JSON should show quantity');

    console.log('✓ Raw positions JSON details working');

    // Assert all network requests are GET only
    const allRequests = networkRequests.filter(method => method !== 'GET');
    strictEqual(allRequests.length, 0, `All /api/v1 requests must be GET, found: ${allRequests.join(', ')}`);
    console.log('✓ Network requests are GET-only');

    // Test error state (route API to abort)
    await strategiesTab.click();
    await page.waitForLoadState('networkidle');

    await page.route('**/api/v1/**', route => route.abort());
    await page.getByRole('button', { name: /refresh/i }).click();

    const errorAlert = page.locator('[role="alert"]');
    await errorAlert.waitFor({ state: 'visible', timeout: 3000 });
    console.log('✓ Error alert shown after API failure');

    // Recover by reload
    await page.unroute('**/api/v1/**');
    await page.reload();
    await page.waitForLoadState('networkidle');

      await unhCard.waitFor({ state: 'visible', timeout: 5000 });
    console.log('✓ Recovered from error state');

    // Check overflow on all viewports and all tabs
    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });

      // Check strategies tab
      await strategiesTab.click();
      await page.waitForLoadState('networkidle');
      await nvdaCard.getByRole('button', { name: /expand/i }).click();
      await checkOverflow(page);
      await nvdaCard.getByRole('button', { name: /collapse/i }).click();

      // Check underlyings tab
      await underlyingsTab.click();
      await page.waitForLoadState('networkidle');
      await checkOverflow(page);

      // Check raw tab
      await rawTab.click();
      await page.waitForLoadState('networkidle');
      await checkOverflow(page);

      console.log(`✓ No horizontal overflow at ${viewport.name} (${viewport.width}x${viewport.height}) across all tabs`);
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await strategiesTab.click();
    const mobileSearchBounds = await searchBox.boundingBox();
    ok(mobileSearchBounds.width >= 180, 'Mobile search must have usable input width');
    await searchBox.fill('NVDA');
    strictEqual(await strategyCards.count(), 1, 'Mobile symbol search should isolate NVDA');
    await searchBox.clear();

    // Take mobile screenshot
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.setViewportSize({ width: 390, height: 844 });
    await strategiesTab.click();
    await page.waitForLoadState('networkidle');
    await page.screenshot({ animations: 'disabled', path: join(screenshotsDir, 'mobile-full.png'), fullPage: true });
    await page.screenshot({ animations: 'disabled', path: join(screenshotsDir, 'mobile-390.png') });
    console.log('✓ Mobile screenshot saved');

    strictEqual(jsErrors.length, 0, `Unexpected browser errors: ${jsErrors.join(', ')}`);
    strictEqual(networkRequests.filter(method => method !== 'GET').length, 0);
    console.log('\n✅ All acceptance tests passed!');
  } finally {
    if (browser) {
      await browser.close();
    }
  }
}

run().catch(err => {
  console.error('\n❌ Test failed:', err.message);
  console.error(err.stack);
  process.exit(1);
});
