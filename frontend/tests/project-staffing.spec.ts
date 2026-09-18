import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mockApi } from './fixtures';

const projectId = 'PROJ950';
const projectPath = `/api/projects/${projectId}`;
const requirement = {
  skill_id: 'SK007',
  skill: 'Docker',
  required_level: 3,
  best_team_level: 0,
  employee_count: 0,
  priority: 'MUST',
  status: 'MISSING',
};

function suggestion(url: URL, required: number, covered = false) {
  return {
    project_id: projectId,
    start_date: url.searchParams.get('start_date') || '2026-10-01',
    end_date: url.searchParams.get('end_date') || '2026-10-31',
    required_allocation: Number(url.searchParams.get('required_allocation') || 20),
    capacity_only: url.searchParams.get('capacity_only') === 'true',
    summary: {
      required_skill_count: required,
      uncovered_skill_count: required && !covered ? 1 : 0,
      candidate_count: 0,
    },
    uncovered_skills: required && !covered ? [requirement] : [],
    candidates: [] as object[],
  };
}

async function fillProject(page: Page) {
  await page.goto('/projects');
  await page.getByRole('button', { name: 'Thêm dự án', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Mã dự án').fill(projectId);
  await dialog.getByLabel('Tên dự án').fill('Staffing Demo');
  await dialog.getByLabel('Mô tả').fill('Dự án cần Docker, nhưng mô tả không tự tạo yêu cầu.');
  return dialog;
}

test('admin creates a project, adds requirements, evaluates a candidate and explicitly assigns', async ({
  page,
}, info) => {
  await mockApi(page);
  let hasRequirement = false;
  let assigned = false;
  const writes: string[] = [];
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method()))
      writes.push(new URL(request.url()).pathname);
  });
  // Isolated synthetic state, not a substitute for the dedicated real-graph suite.
  await page.route(`**${projectPath}/requirements/SK007`, async (route) => {
    expect(route.request().postDataJSON()).toEqual({ min_level: 3, priority: 'MUST' });
    hasRequirement = true;
    await route.fallback();
  });
  await page.route(`**${projectPath}/assignments/EMP001`, async (route) => {
    expect(route.request().postDataJSON()).toMatchObject({
      allocation: 20,
      start_date: '2026-10-01',
      end_date: '2026-10-31',
    });
    assigned = true;
    await route.fallback();
  });
  await page.route(`**${projectPath}/recommendations?*`, (route) => {
    const data = suggestion(new URL(route.request().url()), hasRequirement ? 1 : 0, assigned);
    if (hasRequirement && !assigned) {
      data.summary.candidate_count = 1;
      data.candidates = [
        {
          employee_id: 'EMP001',
          name: 'Nguyen Van Bac',
          title: 'Backend Developer',
          seniority: 'Middle',
          location: 'Ho Chi Minh City',
          rank: 1,
          matched_skill_count: 1,
          matched_skills: [{ ...requirement, level: 4, years_experience: 2.5 }],
          collaboration_count: 0,
          collaborators: [],
          period_remaining_allocation: 20,
          can_allocate: true,
        },
      ];
    }
    return route.fulfill({ json: data });
  });
  await page.route(`**${projectPath}/skill-gap`, (route) =>
    route.fulfill({
      json: {
        project_id: projectId,
        summary: {
          total: hasRequirement ? 1 : 0,
          covered: assigned ? 1 : 0,
          gap: 0,
          missing: hasRequirement && !assigned ? 1 : 0,
          coverage_percent: assigned ? 100 : 0,
        },
        skills: hasRequirement
          ? [
              {
                ...requirement,
                status: assigned ? 'COVERED' : 'MISSING',
                best_team_level: assigned ? 4 : 0,
              },
            ]
          : [],
      },
    }),
  );
  const dialog = await fillProject(page);
  await expect(dialog).toContainText('mô tả không được tự phân tích');
  await dialog.getByRole('button', { name: 'Lưu thay đổi' }).click();
  await expect(page.getByRole('region', { name: 'Bước tiếp theo cho dự án mới' })).toContainText(
    'Đã tạo dự án Staffing Demo',
  );
  await page.getByRole('link', { name: 'Khai báo yêu cầu cho dự án vừa tạo' }).click();
  await expect(page).toHaveURL(/PROJ950\?tab=requirements$/);
  await page.getByRole('tab', { name: 'Phân tích & gợi ý' }).click();
  await expect(
    page.getByRole('heading', { name: 'Chưa đủ thông tin để gợi ý nhân viên' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Đội ngũ đã đáp ứng kỹ năng' })).toHaveCount(0);
  await expect(page.getByRole('form', { name: 'Kế hoạch phân công' })).toHaveCount(0);
  await page
    .locator('.recommendations')
    .getByRole('link', { name: 'Khai báo yêu cầu kỹ năng' })
    .click();
  await page.getByRole('button', { name: 'Thêm yêu cầu', exact: true }).click();
  await page.getByRole('dialog').getByLabel('Kỹ năng').selectOption('SK007');
  await page.getByRole('dialog').getByRole('button', { name: 'Lưu thay đổi' }).click();
  await page.getByRole('link', { name: 'Xem ứng viên theo yêu cầu đã khai báo' }).click();
  const plan = page.getByRole('form', { name: 'Kế hoạch phân công' });
  await plan.getByLabel('Từ ngày').fill('2026-10-01');
  await plan.getByLabel('Đến ngày').fill('2026-10-31');
  await plan.getByRole('button', { name: 'Áp dụng kế hoạch' }).click();
  const card = page.locator('.candidate-card');
  await expect(card).toContainText('Có 4/5 · yêu cầu 3/5');
  await expect(card).toContainText('2.5 năm kinh nghiệm');
  await expect(card).toContainText('Đáp ứng 1/1 kỹ năng còn thiếu');
  await expect(card).toContainText('Còn tối thiểu 20%');
  await expect(card.getByRole('link', { name: 'Xem hồ sơ Nguyen Van Bac' })).toHaveAttribute(
    'href',
    '/employees/EMP001',
  );
  expect(writes.filter((path) => path.includes('/assignments/'))).toHaveLength(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(
    (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
      .violations,
  ).toEqual([]);
  await page.screenshot({
    path: info.outputPath('new-project-candidate-mobile.png'),
    fullPage: true,
  });
  await card.getByRole('button', { name: 'Kiểm tra phân bổ' }).click();
  await expect(page.getByRole('dialog').getByLabel('Ngày bắt đầu')).toHaveValue('2026-10-01');
  await page.getByRole('dialog').getByRole('button', { name: 'Lưu thay đổi' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('tab', { name: 'Đội ngũ', exact: true }).click();
  await expect(page.getByRole('row').filter({ hasText: 'Nguyen Van Bac' })).toContainText('20%');
  expect(writes.filter((path) => path.includes('/assignments/'))).toHaveLength(1);
});

test('viewer sees missing-requirements guidance without setup or assignment write controls', async ({
  page,
}) => {
  await mockApi(page, { role: 'VIEWER' });
  await page.route('**/api/projects/PROJ001/recommendations?*', (route) =>
    route.fulfill({ json: suggestion(new URL(route.request().url()), 0) }),
  );
  await page.goto('/projects/PROJ001');
  const panel = page.locator('.recommendations');
  await expect(panel).toContainText('Liên hệ Admin hoặc quản lý dự án');
  await expect(panel.getByRole('link', { name: 'Khai báo yêu cầu kỹ năng' })).toHaveCount(0);
  await expect(panel.getByRole('button', { name: 'Kiểm tra phân bổ' })).toHaveCount(0);
  await expect(panel.getByRole('heading', { name: 'Đội ngũ đã đáp ứng kỹ năng' })).toHaveCount(0);
});

for (const covered of [false, true]) {
  test(`configured project distinguishes ${covered ? 'covered team' : 'no eligible candidates'}`, async ({
    page,
  }) => {
    await mockApi(page);
    await page.route('**/api/projects/PROJ001/recommendations?*', (route) =>
      route.fulfill({ json: suggestion(new URL(route.request().url()), 1, covered) }),
    );
    await page.goto('/projects/PROJ001');
    await expect(
      page.locator('.recommendations').getByRole('heading', {
        name: covered ? 'Đội ngũ đã đáp ứng kỹ năng' : 'Chưa có ứng viên phù hợp',
      }),
    ).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Chưa đủ thông tin để gợi ý nhân viên' }),
    ).toHaveCount(0);
  });
}

test('failed project creation keeps draft and does not announce a created project', async ({
  page,
}) => {
  await mockApi(page);
  await page.route('**/api/projects', (route) =>
    route.request().method() === 'POST'
      ? route.fulfill({ status: 409, json: { detail: 'Project already exists.' } })
      : route.fallback(),
  );
  const dialog = await fillProject(page);
  await dialog.getByRole('button', { name: 'Lưu thay đổi' }).click();
  await expect(dialog.getByRole('alert')).toBeVisible();
  await expect(dialog.getByLabel('Tên dự án')).toHaveValue('Staffing Demo');
  await expect(page.getByRole('region', { name: 'Bước tiếp theo cho dự án mới' })).toHaveCount(0);
});

test('recommendation failure never becomes missing requirements or covered team', async ({
  page,
}) => {
  await mockApi(page);
  await page.route('**/api/projects/PROJ001/recommendations?*', (route) =>
    route.fulfill({ status: 503, json: { detail: 'Offline' } }),
  );
  await page.goto('/projects/PROJ001');
  await expect(page.locator('.recommendations').getByRole('alert')).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Chưa đủ thông tin để gợi ý nhân viên' }),
  ).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Đội ngũ đã đáp ứng kỹ năng' })).toHaveCount(0);
});
