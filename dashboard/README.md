# Manager Dashboard — Stage 1

Endpoints:

- `GET /api/dashboard/overview/`
- `GET /api/dashboard/activity/`

Both endpoints require authentication and a workspace admin or project manager/admin role.

Optional overview filter:

- `workspace_id`

Activity filters:

- `workspace_id`
- `employee_id`
- `action`
- `date_from=YYYY-MM-DD`
- `date_to=YYYY-MM-DD`
- `page`
- `page_size`

The activity endpoint reuses the existing `users.ActivityLog` model so existing mobile services remain compatible.

## Stage 2: Performance and charts

### Endpoints

- `GET /api/dashboard/performance/`
- `GET /api/dashboard/performance/employees/<employee_id>/`
- `GET /api/dashboard/performance/workspaces/<workspace_id>/`
- `GET /api/dashboard/performance/projects/<project_id>/`
- `GET /api/dashboard/charts/`

### Filters

The general performance and charts endpoints support:

- `workspace_id`
- `project_id`
- `employee_id`
- `date_from=YYYY-MM-DD`
- `date_to=YYYY-MM-DD`

Performance responses include the employee identity, workspace membership context,
project/role context, task counts, completion and overdue rates, report review
statistics, and average expected/actual/completion durations in seconds.

Chart responses are ready for frontend chart libraries and contain task status,
priority, report status, and a 30-day created/completed task timeline.

All queries are restricted to workspaces/projects that the authenticated workspace
admin or project manager/admin can manage.

## Stage 3 endpoints

- `POST /api/dashboard/tasks/bulk-action/`
- `GET /api/dashboard/export/?resource=tasks&format=csv`
- `GET /api/dashboard/export/?resource=reports&format=xlsx`
- `GET /api/dashboard/export/?resource=tasks&format=pdf`
- `POST /api/dashboard/archive/workspace/<id>/`
- `POST /api/dashboard/archive/project/<id>/`
- `POST /api/dashboard/archive/task/<id>/`

Archive request body:

```json
{"archive": true}
```

Bulk actions support assignment, reassignment, status changes, priority changes,
archiving, restoring, and soft deletion. All operations are restricted to the
workspaces and projects managed by the authenticated user.
