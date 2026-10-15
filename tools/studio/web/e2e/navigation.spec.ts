import { expect, FAKE_ROOT_404, test, watchProblems } from './fixtures'

test('the Studio nav links to Pedalboard', async ({ page }) => {
  await page.goto('/speakers')
  await expect(page.getByRole('link', { name: 'Pedalboard' })).toBeVisible()
})

// A cheap regression net: the shared shell and router still load these pages on the fake data without console errors.
for (const path of ['/casting', '/voices', '/rt-voices', '/assignments']) {
  test(`${path} loads without console errors`, async ({ page }) => {
    const problems = watchProblems(page, FAKE_ROOT_404)
    await page.goto(path)
    await expect(page.locator('#app')).not.toBeEmpty()
    await page.waitForTimeout(800)
    expect(problems).toEqual([])
  })
}
