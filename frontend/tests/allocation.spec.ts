import { expect, test } from '@playwright/test';
import { mockApi } from './fixtures';
import { peakAllocation } from '../src/allocation';
import type { Assignment } from '../src/types';

test('calendar sweep keeps inclusive boundaries and does not sum disjoint periods', () => {
  const loads = [
    { allocation: 60, start_date: '2026-10-01', end_date: '2026-10-15' },
    { allocation: 60, start_date: '2026-10-16', end_date: '2026-10-31' },
  ] as Assignment[];
  expect(peakAllocation(loads, '2026-10-01', '2026-10-31')).toBe(60);
  loads[1].start_date = '2026-10-15';
  expect(peakAllocation(loads, '2026-10-01', '2026-10-31')).toBe(120);
  expect(peakAllocation(loads, '2026-11-01', '2026-11-30')).toBe(0);
  expect(peakAllocation([{ allocation: 20 } as Assignment], '', '9999-12-31')).toBe(20);
});

test('changing period updates capacity, rejects reversed dates and preserves failed draft', async ({
  page,
}) => {
  await mockApi(page);
  await page.route('**/api/projects/PROJ002/assignments', (route) =>
    route.fulfill({
      json: {
        total: 1,
        items: [
          {
            employee_id: 'EMP001',
            project_id: 'PROJ002',
            allocation: 100,
            start_date: '2026-10-01',
            end_date: '2026-10-31',
          },
        ],
      },
    }),
  );
  let writes = 0;
  await page.route('**/api/projects/PROJ003/assignments/EMP001', (route) => {
    writes += 1;
    expect(route.request().postDataJSON()).toMatchObject({
      start_date: '2026-11-01',
      end_date: '2026-11-30',
      allocation: 100,
      role: 'Planned advisor',
    });
    return route.fulfill({ status: 503, json: { detail: 'offline' } });
  });
  await page.goto('/projects/PROJ003?tab=assignments');
  await page.getByRole('button', { name: 'Phân công', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Nhân viên').selectOption('EMP001');
  await expect(dialog.locator('.capacity-note strong')).toHaveText('0%');
  await dialog.getByLabel('Vai trò trong dự án').fill('Planned advisor');
  await dialog.getByLabel('Ngày bắt đầu').fill('2026-11-01');
  await dialog.getByLabel('Ngày kết thúc').fill('2026-10-31');
  await expect(dialog.getByRole('alert')).toContainText('Ngày kết thúc phải bằng hoặc sau');
  await expect(dialog.getByRole('button', { name: 'Lưu thay đổi' })).toBeDisabled();
  await dialog.getByLabel('Ngày kết thúc').fill('2026-11-30');
  await expect(dialog.locator('.capacity-note strong')).toHaveText('100%');
  await dialog.getByLabel('Phân bổ (%)').fill('100');
  await dialog.getByRole('button', { name: 'Lưu thay đổi' }).click();
  await expect(dialog.getByRole('alert')).toContainText('chưa sẵn sàng');
  await expect(dialog.getByLabel('Ngày bắt đầu')).toHaveValue('2026-11-01');
  await expect(dialog.getByLabel('Ngày kết thúc')).toHaveValue('2026-11-30');
  await expect(dialog.getByLabel('Vai trò trong dự án')).toHaveValue('Planned advisor');
  expect(writes).toBe(1);
});

test('dated edit retains both dates, displays history, and excludes the replaced edge', async ({
  page,
}) => {
  await mockApi(page);
  await page.route('**/api/projects/PROJ001/assignments', (route) =>
    route.fulfill({
      json: {
        total: 1,
        items: [
          {
            employee_id: 'EMP002',
            employee_name: 'An Nguyen',
            project_id: 'PROJ001',
            project_name: 'Test',
            role: 'Developer',
            allocation: 80,
            start_date: '2020-01-01',
            end_date: '2020-01-31',
            employee_total_allocation: 20,
            employee_remaining_allocation: 80,
          },
        ],
      },
    }),
  );
  await page.goto('/projects/PROJ001?tab=assignments');
  await expect(page.getByRole('row').filter({ hasText: 'An Nguyen' })).toContainText('Đã kết thúc');
  await page.getByRole('button', { name: 'Sửa phân công An Nguyen' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel('Ngày bắt đầu')).toHaveValue('2020-01-01');
  await expect(dialog.getByLabel('Ngày kết thúc')).toHaveValue('2020-01-31');
  await expect(dialog.locator('.capacity-note strong')).toHaveText('80%'); // other legacy project 20
  await expect(dialog.getByLabel('Phân bổ (%)')).toHaveAttribute('max', '80');
});

test('recommendation filter sends the exact plan and carries it to assignment confirmation', async ({
  page,
}) => {
  await mockApi(page);
  const requests: URL[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/recommendations?')) requests.push(new URL(request.url()));
  });
  await page.goto('/');
  const form = page.getByRole('form', { name: 'Kế hoạch phân công' });
  await form.getByLabel('Từ ngày').fill('2026-11-01');
  await form.getByLabel('Đến ngày').fill('2026-11-30');
  await form.getByLabel('Cần phân bổ (%)').fill('15');
  await form.getByLabel('Chỉ người đủ dung lượng').uncheck();
  await form.getByRole('button', { name: 'Áp dụng kế hoạch' }).click();
  await expect(page.locator('.recommendations > .workflow-note')).toContainText(
    '2026-11-01 → 2026-11-30, cần 15%',
  );
  await expect(page.locator('.candidate-card')).toHaveCount(2);
  await page.getByRole('button', { name: 'Kiểm tra phân bổ' }).first().click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByLabel('Ngày bắt đầu')).toHaveValue('2026-11-01');
  await expect(dialog.getByLabel('Ngày kết thúc')).toHaveValue('2026-11-30');
  await expect(dialog.getByLabel('Phân bổ (%)')).toHaveValue('15');
  expect(Object.fromEntries(requests.at(-1)!.searchParams)).toEqual({
    start_date: '2026-11-01',
    end_date: '2026-11-30',
    required_allocation: '15',
    capacity_only: 'false',
  });
});

test('expired assignments do not reduce employee capacity today', async ({ page }) => {
  await mockApi(page);
  await page.route('**/api/projects/PROJ002/assignments', (route) =>
    route.fulfill({
      json: {
        total: 1,
        items: [
          {
            employee_id: 'EMP001',
            project_id: 'PROJ002',
            allocation: 100,
            start_date: '2020-01-01',
            end_date: '2020-01-31',
          },
        ],
      },
    }),
  );
  await page.goto('/employees/EMP001');
  await expect(page.locator('.profile-meta')).toContainText('0% đã phân bổ · còn 100%');
});
