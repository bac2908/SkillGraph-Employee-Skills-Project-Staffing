import { ArrowUpRight, CheckCheck, CircleDot, Sparkles, Users } from 'lucide-react';
import { useId, useState } from 'react';
import { useResource } from '../api';
import type { Candidate, Gap, Recommendations } from '../types';
import { Avatar, Badge, Empty, ErrorNotice, Loading, SectionHeading } from './ui';
import { useAuth } from '../auth';
import { planningToday } from '../allocation';

export function SkillCoverage({ projectId }: { projectId: string }) {
  const query = useResource<Gap>(`/api/projects/${projectId}/skill-gap`);
  if (query.isPending) return <Loading />;
  if (query.isError) return <ErrorNotice error={query.error} retry={() => void query.refetch()} />;
  const gap = query.data;
  if (!gap.skills.length)
    return (
      <Empty
        title="Chưa có yêu cầu kỹ năng"
        detail="Thêm kỹ năng dự án cần để bắt đầu phân tích mức độ đáp ứng."
      />
    );
  return (
    <div className="coverage-content">
      <div className="coverage-summary">
        <div className="coverage-number">
          {gap.summary.coverage_percent}
          <span>%</span>
        </div>
        <div>
          <strong>Kỹ năng được đáp ứng hôm nay (UTC+07)</strong>
          <p>
            {gap.summary.covered} / {gap.summary.total} kỹ năng đạt yêu cầu
          </p>
        </div>
        <span
          className={`coverage-alert ${gap.summary.covered === gap.summary.total ? 'complete' : ''}`}
        >
          {gap.summary.covered === gap.summary.total ? (
            <CheckCheck size={16} />
          ) : (
            <CircleDot size={16} />
          )}
          {gap.summary.gap + gap.summary.missing} kỹ năng cần bổ sung
        </span>
      </div>
      <div className="skill-bars">
        {gap.skills.map((skill) => (
          <div className="skill-bar-row" key={skill.skill_id}>
            <div>
              <strong>{skill.skill}</strong>
              <span>
                {skill.best_team_level} / {skill.required_level}
              </span>
            </div>
            <div
              className="level-track"
              role="img"
              aria-label={`${skill.skill}: đội ngũ cấp ${skill.best_team_level}, yêu cầu cấp ${skill.required_level}`}
            >
              <span
                className={skill.status === 'COVERED' ? '' : 'gap-fill'}
                style={{ width: `${Math.min(100, (skill.best_team_level / 5) * 100)}%` }}
              />
              <i style={{ left: `${(skill.required_level / 5) * 100}%` }} />
            </div>
            <Badge value={skill.status} />
          </div>
        ))}
      </div>
      <div className="chart-legend">
        <span>
          <i />
          Năng lực đội ngũ
        </span>
        <span>
          <i className="legend-required" />
          Mức yêu cầu · thang 1–5
        </span>
      </div>
    </div>
  );
}

export function CandidateSuggestions({
  projectId,
  onAssign,
  compact = false,
}: {
  projectId: string;
  onAssign: (candidate: Candidate) => void;
  compact?: boolean;
}) {
  const [plan, setPlan] = useState({
    start_date: planningToday(),
    end_date: planningToday(),
    required_allocation: '20',
    capacity_only: 'true',
  });
  const [planError, setPlanError] = useState('');
  const filterId = useId();
  const query = useResource<Recommendations>(
    `/api/projects/${projectId}/recommendations?${new URLSearchParams(plan)}`,
  );
  const { canManageProject } = useAuth();
  return (
    <section className="panel recommendations">
      <SectionHeading
        title="Những mảnh ghép phù hợp"
        detail="Đủ dung lượng trước, rồi kỹ năng còn thiếu, cộng tác và cấp độ. Không phải xếp hạng hiệu suất nhân viên."
        action={
          <span className="subtle-label">
            <Sparkles size={16} />
            Gợi ý từ SkillGraph
          </span>
        }
      />
      <form
        className="recommendation-filters"
        aria-label="Kế hoạch phân công"
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          const start = String(data.get('start_date'));
          const end = String(data.get('end_date'));
          if (end < start) {
            setPlanError('Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.');
            return;
          }
          setPlanError('');
          setPlan({
            start_date: start,
            end_date: end,
            required_allocation: String(data.get('required_allocation')),
            capacity_only: data.has('capacity_only') ? 'true' : 'false',
          });
        }}
      >
        <label htmlFor={`${filterId}-start`}>
          Từ ngày
          <input
            id={`${filterId}-start`}
            name="start_date"
            type="date"
            required
            defaultValue={plan.start_date}
          />
        </label>
        <label htmlFor={`${filterId}-end`}>
          Đến ngày
          <input
            id={`${filterId}-end`}
            name="end_date"
            type="date"
            required
            defaultValue={plan.end_date}
          />
        </label>
        <label htmlFor={`${filterId}-load`}>
          Cần phân bổ (%)
          <input
            id={`${filterId}-load`}
            name="required_allocation"
            type="number"
            required
            min="1"
            max="100"
            step="1"
            defaultValue="20"
          />
        </label>
        <label className="capacity-filter">
          <input name="capacity_only" type="checkbox" defaultChecked />
          Chỉ người đủ dung lượng
        </label>
        <button className="button secondary" type="submit">
          Áp dụng kế hoạch
        </button>
      </form>
      {planError && <p role="alert">{planError}</p>}
      <p className="workflow-note">
        Kế hoạch đang áp dụng: {plan.start_date} → {plan.end_date}, cần {plan.required_allocation}%
        mỗi ngày (UTC+07). Gợi ý có xét dung lượng trong toàn bộ kỳ; số liệu không giữ chỗ.
      </p>
      <details className="recommendation-explainer">
        <summary>Cách đọc gợi ý và giới hạn</summary>
        <p>
          Kỹ năng của đội chỉ tính người được phân công xuyên suốt kỳ nên kết quả có thể thận trọng
          hơn từng ngày. Được gợi ý không có nghĩa chắc chắn nhận thêm việc; hãy xác nhận với người
          quản lý. Bản ghi đã gắn dự án được điều chỉnh tại tab Phân công.
        </p>
      </details>
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => void query.refetch()} />
      ) : !query.data.candidates.length ? (
        <Empty
          title={
            query.data.summary.uncovered_skill_count
              ? 'Chưa có ứng viên phù hợp'
              : 'Đội ngũ đã đáp ứng kỹ năng'
          }
          detail={
            query.data.summary.uncovered_skill_count
              ? 'Thử điều chỉnh kỳ, tỷ lệ cần phân bổ hoặc bỏ lọc dung lượng. Kiểm tra năng lực và trạng thái sẵn sàng.'
              : 'Bạn có thể tiếp tục quản lý yêu cầu và phân công tại dự án.'
          }
        />
      ) : (
        <div className={`candidate-grid ${compact ? 'compact' : ''}`}>
          {query.data.candidates.map((candidate, index) => (
            <article className="candidate-card" key={candidate.employee_id}>
              <div className="candidate-heading">
                <Avatar name={candidate.name} index={index} />
                <span className="rank">#{candidate.rank} phù hợp</span>
              </div>
              <h3>{candidate.name}</h3>
              <p>
                {candidate.title} · {candidate.seniority}
              </p>
              <p className="workflow-note">
                Còn tối thiểu {candidate.period_remaining_allocation}% trong kỳ ·{' '}
                {candidate.can_allocate
                  ? 'Đủ dung lượng theo kế hoạch'
                  : 'Chưa đủ dung lượng theo kế hoạch'}
                .
              </p>
              <div className="chips">
                {candidate.matched_skills.map((skill) => (
                  <span className="chip" key={skill.skill_id}>
                    {skill.skill} <b>{skill.level}/5</b>
                  </span>
                ))}
              </div>
              <div className="collaboration">
                <Users size={15} />
                <span>
                  {candidate.collaboration_count
                    ? `Đã làm cùng ${candidate.collaborators.join(', ')}`
                    : 'Cơ hội kết nối mới trong đội ngũ'}
                </span>
              </div>
              {canManageProject(projectId) ? (
                <button
                  className="button secondary"
                  onClick={() =>
                    onAssign({
                      ...candidate,
                      suggested_start_date: query.data.start_date || plan.start_date,
                      suggested_end_date: query.data.end_date || plan.end_date,
                      suggested_allocation:
                        query.data.required_allocation || Number(plan.required_allocation),
                    })
                  }
                >
                  Kiểm tra phân bổ
                  <ArrowUpRight size={16} />
                </button>
              ) : (
                <small className="read-only-note">Cần quyền quản lý dự án để phân công</small>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
