import { useQueries } from '@tanstack/react-query';
import { request, useAll } from './api';
import type { Assignment, Items, Project } from './types';
import { peakAllocation, planningToday } from './allocation';

export function useCapacity() {
  const projects = useAll<Project>('projects');
  const assignments = useQueries({
    queries: (projects.data || []).map((project) => ({
      queryKey: ['api', `/api/projects/${project.project_id}/assignments`],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        request<Items<Assignment>>(`/api/projects/${project.project_id}/assignments`, { signal }),
    })),
  });
  const totals = new Map<string, number>();
  const allAssignments: Assignment[] = [];
  const today = planningToday();
  for (const query of assignments)
    for (const item of query.data?.items || []) {
      allAssignments.push(item);
      totals.set(
        item.employee_id,
        (totals.get(item.employee_id) || 0) + peakAllocation([item], today, today),
      );
    }
  return {
    totals,
    limitFor: (employeeId: string, projectId: string, start: string, end: string) =>
      Math.max(
        0,
        100 -
          peakAllocation(
            allAssignments.filter(
              (a) => a.employee_id === employeeId && a.project_id !== projectId,
            ),
            start,
            end,
          ),
      ),
    hasData: !!projects.data && assignments.every((q) => q.data !== undefined),
    isPending: projects.isPending || assignments.some((q) => q.isPending),
    error: projects.error || assignments.find((q) => q.error)?.error,
    retry: () => {
      void projects.refetch();
      assignments.forEach((q) => void q.refetch());
    },
  };
}
