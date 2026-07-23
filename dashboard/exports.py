import csv
from io import BytesIO, StringIO

from django.http import HttpResponse
from django.utils import timezone

from users.models import Task, TechnicalReportForm
from .performance import get_scope_projects


def export_queryset(user, resource, workspace=None, project=None, employee_id=None, date_from=None, date_to=None, include_archived=False):
    projects = get_scope_projects(user, workspace, project)
    if resource == "tasks":
        qs = Task.objects.select_related("project", "project__workspace", "assigned_to").filter(project__in=projects, is_deleted=False)
        if not include_archived:
            qs = qs.filter(is_archived=False)
        if employee_id:
            qs = qs.filter(assigned_to_id=employee_id)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs.order_by("-created_at")
    qs = TechnicalReportForm.objects.select_related("task", "task__project", "task__project__workspace", "user").filter(task__project__in=projects)
    if employee_id:
        qs = qs.filter(user_id=employee_id)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs.order_by("-created_at")


def rows_for(resource, queryset):
    if resource == "tasks":
        headers = ["id", "title", "workspace", "project", "assigned_to", "status", "priority", "due_date", "created_at", "archived"]
        rows = [[t.id, t.title, t.project.workspace.name if t.project.workspace else "", t.project.name, t.assigned_to.email if t.assigned_to else "", t.status, t.priority, t.due_date.isoformat() if t.due_date else "", t.created_at.isoformat(), t.is_archived] for t in queryset]
    else:
        headers = ["id", "task", "workspace", "project", "employee", "status", "quality", "duration_time", "created_at"]
        rows = [[r.id, r.task.title, r.task.project.workspace.name if r.task.project.workspace else "", r.task.project.name, r.user.email, r.status, r.quality or "", str(r.duration_time or ""), r.created_at.isoformat()] for r in queryset]
    return headers, rows


def csv_response(resource, queryset):
    output = StringIO()
    writer = csv.writer(output)
    headers, rows = rows_for(resource, queryset)
    writer.writerow(headers)
    writer.writerows(rows)
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="dashboard_%s_%s.csv"' % (resource, timezone.localdate())
    return response


def xlsx_response(resource, queryset):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = resource.title()
    headers, rows = rows_for(resource, queryset)
    ws.append(headers)
    for row in rows:
        ws.append(row)
    for column in ws.columns:
        width = max(len(str(cell.value or "")) for cell in column) + 2
        ws.column_dimensions[column[0].column_letter].width = min(width, 50)
    output = BytesIO()
    wb.save(output)
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="dashboard_%s_%s.xlsx"' % (resource, timezone.localdate())
    return response


def pdf_response(resource, queryset):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    headers, rows = rows_for(resource, queryset)
    styles = getSampleStyleSheet()
    story = [Paragraph("Dashboard %s export" % resource.title(), styles["Title"]), Spacer(1, 12)]
    data = [headers] + [[str(value) for value in row] for row in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.lightgrey), ("GRID", (0,0), (-1,-1), 0.5, colors.grey), ("FONTSIZE", (0,0), (-1,-1), 7), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story.append(table)
    doc.build(story)
    response = HttpResponse(output.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="dashboard_%s_%s.pdf"' % (resource, timezone.localdate())
    return response
