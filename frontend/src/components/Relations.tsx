import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Pencil, Trash2 } from 'lucide-react';
import { request, save, useAll, useResource } from '../api';
import type {
  Assignment,
  Candidate,
  Employee,
  EmployeeSkill,
  Items,
  Requirement,
  Skill,
} from '../types';
import { useCapacity } from '../hooks';
import {
  AddButton,
  Avatar,
  Badge,
  Empty,
  ErrorNotice,
  FormDialog,
  Loading,
  Meter,
  SectionHeading,
  useWrite,
  type Field,
} from './ui';
import { options } from '../config';
import { useAuth } from '../auth';
import { planningToday } from '../allocation';

export function AssignmentDialog({
  projectId,
  employeeId,
  existing,
  suggestion,
  onClose,
}: {
  projectId: string;
  employeeId?: string;
  existing?: Assignment;
  suggestion?: Candidate;
  onClose: () => void;
}) {
  const employees = useAll<Employee>('employees');
  const capacity = useCapacity();
  const write = useWrite();
  const assignments = useResource<Items<Assignment>>(`/api/projects/${projectId}/assignments`);
  const [chosenId, setChosenId] = useState(existing?.employee_id || employeeId || '');
  const selectedId = existing?.employee_id || employeeId || chosenId;
  const [startDate, setStartDate] = useState(
    existing?.start_date || suggestion?.suggested_start_date || '',
  );
  const [endDate, setEndDate] = useState(
    existing?.end_date || suggestion?.suggested_end_date || '',
  );
  const currentAssignment =
    existing || assignments.data?.items.find((a) => a.employee_id === selectedId);
  const invalidDates = !!(startDate && endDate && endDate < startDate);
  const remaining = selectedId
    ? capacity.limitFor(selectedId, projectId, startDate, endDate)
    : null;
  const error = employees.error || capacity.error || assignments.error;
  // Keep form mounted only after capacity and selector data are available.
  const dataReady = !!employees.data && !!assignments.data && capacity.hasData;
  if (!dataReady)
    return (
      <FormDialog
        title="Phân công nhân viên"
        onClose={onClose}
        submitDisabled
        onSubmit={async () => {}}
      >
        {error ? (
          <ErrorNotice
            error={error}
            retry={() => {
              void employees.refetch();
              void assignments.refetch();
              capacity.retry();
            }}
          />
        ) : (
          <Loading />
        )}
      </FormDialog>
    );
  const fields: Field[] = [
    {
      name: 'employee_id',
      label: 'Nhân viên',
      type: 'select',
      disabled: !!existing || !!employeeId,
      options: (employees.data || [])
        .filter(
          (e) =>
            e.employee_id === selectedId ||
            !assignments.data?.items.some((a) => a.employee_id === e.employee_id),
        )
        .map((e) => ({
          value: e.employee_id,
          label: `${e.name} · tối đa ${capacity.limitFor(e.employee_id, projectId, startDate, endDate)}% trong kỳ`,
        })),
    },
    { name: 'role', label: 'Vai trò trong dự án', maxLength: 100 },
    {
      name: 'start_date',
      label: 'Ngày bắt đầu',
      type: 'date',
      required: false,
      hint: 'Tính cả ngày này. Để trống = không giới hạn bắt đầu.',
    },
    {
      name: 'end_date',
      label: 'Ngày kết thúc',
      type: 'date',
      required: false,
      hint: 'Tính cả ngày này. Để trống = không giới hạn kết thúc.',
    },
    {
      name: 'allocation',
      label: 'Phân bổ (%)',
      type: 'number',
      min: 1,
      max: remaining ?? 100,
      step: 1,
      hint: 'Tổng phân bổ tại bất kỳ ngày nào trong kỳ không vượt quá 100%. Không phải điểm hiệu suất.',
    },
  ];
  return (
    <FormDialog
      title={currentAssignment ? 'Điều chỉnh phân công' : 'Phân công nhân viên'}
      fields={fields}
      submitDisabled={remaining === 0 || !!error || invalidDates}
      onFieldChange={(field, value) => {
        if (field === 'employee_id') setChosenId(value);
        if (field === 'start_date') setStartDate(value);
        if (field === 'end_date') setEndDate(value);
      }}
      initial={{
        employee_id: selectedId || '',
        role:
          currentAssignment?.role ||
          employees.data?.find((e) => e.employee_id === selectedId)?.title ||
          '',
        allocation:
          currentAssignment?.allocation ||
          suggestion?.suggested_allocation ||
          (remaining && remaining > 0 ? Math.min(20, remaining) : ''),
        start_date: startDate,
        end_date: endDate,
      }}
      onClose={onClose}
      onSubmit={async (values) => {
        const targetId = selectedId || String(values.employee_id);
        const start = String(values.start_date || '');
        const end = String(values.end_date || '');
        if (start && end && end < start)
          throw new Error('Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.');
        const proposed =
          100 - capacity.limitFor(targetId, projectId, start, end) + Number(values.allocation);
        if (proposed > 100)
          throw new Error(
            `Nhân viên sẽ được phân bổ ${proposed}%. Hãy chọn tỷ lệ thấp hơn hoặc điều chỉnh dự án khác.`,
          );
        await write(
          () =>
            save(`/api/projects/${projectId}/assignments/${targetId}`, 'PUT', {
              role: values.role,
              allocation: values.allocation,
              start_date: start || null,
              end_date: end || null,
            }),
          'Đã cập nhật phân công.',
        );
      }}
    >
      {invalidDates && <p role="alert">Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.</p>}
      {error && (
        <ErrorNotice
          error={error}
          retry={() => {
            void employees.refetch();
            void assignments.refetch();
            capacity.retry();
          }}
        />
      )}
      {remaining !== null && (
        <div className="capacity-note">
          <strong>{remaining}%</strong>
          <span>
            {currentAssignment
              ? 'Giới hạn trong kỳ đã chọn; thay thế phân công hiện tại tại đây'
              : 'Dung lượng tối đa trong toàn bộ kỳ đã chọn'}
          </span>
        </div>
      )}
      <p className="workflow-note">
        {remaining === 0
          ? 'Nhân viên đã được phân bổ đủ 100% ở ít nhất một ngày trong kỳ. Hãy đổi thời gian hoặc điều chỉnh phân công khác.'
          : 'Số liệu có thể thay đổi khi người khác phân công. Backend kiểm tra lại khi lưu. Để trống cả hai ngày = không giới hạn thời gian, kể cả dữ liệu cũ.'}
      </p>
    </FormDialog>
  );
}

export function Assignments({ projectId }: { projectId: string }) {
  const { canManageProject } = useAuth();
  const canEdit = canManageProject(projectId);
  const path = `/api/projects/${projectId}/assignments`;
  const query = useResource<Items<Assignment>>(path);
  const write = useWrite();
  const [edit, setEdit] = useState<Assignment | 'new' | null>(null);
  const [remove, setRemove] = useState<Assignment | null>(null);
  return (
    <section className="panel">
      <SectionHeading
        title="Đội ngũ dự án"
        detail="Gồm phân công hiện tại, tương lai và đã kết thúc. Kết thúc bằng ngày để giữ lịch sử; gỡ sẽ xóa liên kết."
        action={canEdit && <AddButton onClick={() => setEdit('new')}>Phân công</AddButton>}
      />
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => void query.refetch()} />
      ) : !query.data.items.length ? (
        <Empty
          title="Đội ngũ đang chờ thành viên đầu tiên"
          detail="Phân công nhân viên để bắt đầu xây dựng năng lực dự án."
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Thành viên</th>
                <th>Vai trò</th>
                <th>Dự án này</th>
                <th>Thời gian (UTC+07)</th>
                <th>Tổng hôm nay</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((a, index) => (
                <tr key={a.employee_id}>
                  <td>
                    <div className="identity">
                      <Avatar name={a.employee_name} index={index} />
                      <div>
                        <strong>{a.employee_name}</strong>
                        <small>{a.employee_id}</small>
                      </div>
                    </div>
                  </td>
                  <td>{a.role}</td>
                  <td>
                    <strong>{a.allocation}%</strong>
                  </td>
                  <td>
                    <span>
                      {a.start_date || 'Không giới hạn'} → {a.end_date || 'Không giới hạn'}
                    </span>
                    <small>
                      {a.end_date && a.end_date < planningToday()
                        ? 'Đã kết thúc'
                        : a.start_date && a.start_date > planningToday()
                          ? 'Sắp bắt đầu'
                          : 'Đang hiệu lực'}
                    </small>
                  </td>
                  <td>
                    <div className="allocation-cell">
                      <span>
                        {a.employee_total_allocation}% · còn {a.employee_remaining_allocation}%
                      </span>
                      <Meter value={a.employee_total_allocation} />
                    </div>
                  </td>
                  <td>
                    {canEdit ? (
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          aria-label={`Sửa phân công ${a.employee_name}`}
                          onClick={() => setEdit(a)}
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          className="icon-button delete-button"
                          aria-label={`Gỡ phân công ${a.employee_name}`}
                          onClick={() => setRemove(a)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ) : (
                      <small>Chỉ xem</small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {edit && (
        <AssignmentDialog
          projectId={projectId}
          existing={edit === 'new' ? undefined : edit}
          onClose={() => setEdit(null)}
        />
      )}
      {remove && (
        <FormDialog
          title={`Gỡ phân công ${remove.employee_name}?`}
          description="Nhân viên sẽ được gỡ khỏi dự án này. Kết quả Skill Gap sẽ được tính lại."
          submitLabel="Gỡ phân công"
          danger
          onClose={() => setRemove(null)}
          onSubmit={() =>
            write(
              () => request(`${path}/${remove.employee_id}`, { method: 'DELETE' }),
              'Đã gỡ phân công.',
            )
          }
        />
      )}
    </section>
  );
}

export function SkillRelations({
  ownerId,
  kind,
}: {
  ownerId: string;
  kind: 'employee' | 'project';
}) {
  const isEmployee = kind === 'employee';
  const { isAdmin, canManageProject } = useAuth();
  const canEdit = isEmployee ? isAdmin : canManageProject(ownerId);
  const path = isEmployee
    ? `/api/employees/${ownerId}/skills`
    : `/api/projects/${ownerId}/requirements`;
  const query = useResource<Items<EmployeeSkill | Requirement>>(path);
  const skills = useAll<Skill>('skills');
  const write = useWrite();
  const [edit, setEdit] = useState<EmployeeSkill | Requirement | 'new' | null>(null);
  const [remove, setRemove] = useState<EmployeeSkill | Requirement | null>(null);
  const fields: Field[] = [
    {
      name: 'skill_id',
      label: 'Kỹ năng',
      type: 'select',
      disabled: edit !== 'new',
      options: (skills.data || []).map((skill) => ({
        value: skill.skill_id,
        label: `${skill.name} · ${skill.category}`,
      })),
    },
    {
      name: isEmployee ? 'level' : 'min_level',
      label: isEmployee ? 'Mức thành thạo (1–5)' : 'Mức yêu cầu (1–5)',
      type: 'number',
      min: 1,
      max: 5,
      step: 1,
    },
    isEmployee
      ? {
          name: 'years_experience',
          label: 'Số năm kinh nghiệm',
          type: 'number',
          min: 0,
          max: 80,
          step: 0.1,
        }
      : {
          name: 'priority',
          label: 'Độ ưu tiên',
          type: 'select',
          options: options(['MUST', 'SHOULD', 'NICE']),
        },
  ];
  return (
    <section className="panel">
      <SectionHeading
        title={isEmployee ? 'Hồ sơ kỹ năng' : 'Yêu cầu kỹ năng'}
        detail={
          isEmployee
            ? 'Ghi nhận mức thành thạo và kinh nghiệm thực tế.'
            : 'Khai báo kỹ năng, cấp độ tối thiểu và ưu tiên. Phần mô tả dự án không tự tạo những yêu cầu này.'
        }
        action={
          canEdit && (
            <AddButton onClick={() => setEdit('new')}>
              {isEmployee ? 'Gán kỹ năng' : 'Thêm yêu cầu'}
            </AddButton>
          )
        }
      />
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorNotice error={query.error} retry={() => void query.refetch()} />
      ) : !query.data.items.length ? (
        <Empty
          title={isEmployee ? 'Chưa có kỹ năng' : 'Chưa có yêu cầu'}
          detail="Thêm kỹ năng để SkillGraph hiểu rõ năng lực cần kết nối."
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Kỹ năng</th>
                <th>Nhóm</th>
                <th>Mức độ</th>
                <th>{isEmployee ? 'Kinh nghiệm' : 'Ưu tiên'}</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((item) => (
                <tr key={item.skill_id}>
                  <td>
                    <strong>{item.skill_name}</strong>
                    <small>{item.skill_id}</small>
                  </td>
                  <td>{item.category}</td>
                  <td>
                    <span
                      className="level-dots"
                      aria-label={`Cấp ${'level' in item ? item.level : item.min_level}/5`}
                    >
                      {[1, 2, 3, 4, 5].map((n) => (
                        <i
                          key={n}
                          className={
                            n <= ('level' in item ? item.level : item.min_level) ? 'filled' : ''
                          }
                        />
                      ))}
                    </span>
                  </td>
                  <td>
                    {'years_experience' in item ? (
                      `${item.years_experience} năm`
                    ) : (
                      <Badge value={item.priority} />
                    )}
                  </td>
                  <td>
                    {canEdit ? (
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          aria-label={`Sửa ${item.skill_name}`}
                          onClick={() => setEdit(item)}
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          className="icon-button delete-button"
                          aria-label={`Gỡ ${item.skill_name}`}
                          onClick={() => setRemove(item)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ) : (
                      <small>Chỉ xem</small>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {edit && (
        <FormDialog
          title={isEmployee ? 'Cập nhật kỹ năng nhân viên' : 'Cập nhật yêu cầu kỹ năng'}
          submitDisabled={skills.isPending || skills.isError || !skills.data?.length}
          fields={skills.data ? fields : []}
          initial={
            edit === 'new'
              ? { level: 3, min_level: 3, years_experience: 1, priority: 'MUST' }
              : { ...edit }
          }
          onClose={() => setEdit(null)}
          onSubmit={async (values) => {
            if (!skills.data) throw new Error('Danh mục kỹ năng chưa tải xong. Hãy thử lại.');
            const id = edit === 'new' ? String(values.skill_id) : edit.skill_id;
            const { skill_id: _, ...body } = values;
            await write(() => save(`${path}/${id}`, 'PUT', body));
          }}
        >
          {skills.isPending && <Loading />}
          {skills.error && <ErrorNotice error={skills.error} retry={() => void skills.refetch()} />}
          {skills.data?.length === 0 && (
            <p>Hãy thêm kỹ năng vào danh mục trước khi tạo liên kết.</p>
          )}
        </FormDialog>
      )}
      {!isEmployee && query.data && !query.isError && query.data.items.length > 0 && (
        <div className="panel-foot">
          <Link className="text-link" to={`/projects/${ownerId}?tab=analysis`}>
            Xem ứng viên theo yêu cầu đã khai báo →
          </Link>
        </div>
      )}
      {remove && (
        <FormDialog
          title={`Gỡ ${remove.skill_name}?`}
          description="Chỉ gỡ liên kết này. Kỹ năng vẫn được giữ trong danh mục chung."
          danger
          submitLabel="Gỡ kỹ năng"
          onClose={() => setRemove(null)}
          onSubmit={() =>
            write(
              () => request(`${path}/${remove.skill_id}`, { method: 'DELETE' }),
              'Đã gỡ liên kết kỹ năng.',
            )
          }
        />
      )}
    </section>
  );
}
