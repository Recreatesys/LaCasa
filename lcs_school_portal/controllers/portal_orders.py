from datetime import date, timedelta

from markupsafe import escape

from odoo import _, http
from odoo.http import request

# Show a 4-week (28-day) window in the portal calendar
WINDOW_DAYS = 28
CUTOFF_DAYS = 3


def _format_money(amount):
    if amount is None:
        return ''
    return f'${amount:,.2f}'


def _render_orders_page_html(student, days, alerts, csrf_token):
    """Server-render the portal calendar page as plain HTML.

    Each row represents one date in the window with:
      - Date
      - Open/Closed/Holiday/Exam status
      - Menu items available
      - Student's existing order for that date
      - Cut-off status
    """
    class_label = student.class_company_id.name or ''

    alert_html = ''
    if alerts:
        items = ''.join(
            f'<li><strong>{escape(d.strftime("%a, %d %b %Y"))}</strong> — '
            f'cut-off in {hours_left} day(s). No order placed yet.</li>'
            for (d, hours_left) in alerts
        )
        alert_html = (
            f'<div class="alert alert-warning" role="alert">'
            f'<strong>⏰ Cut-off approaching:</strong>'
            f'<ul class="mb-0">{items}</ul>'
            f'</div>'
        )

    rows_html = []
    for row in days:
        d = row['date']
        weekday = d.strftime('%a')
        open_badge = (
            '<span class="badge text-bg-success">Open</span>'
            if row['is_open']
            else f'<span class="badge text-bg-secondary">{escape(row["closed_reason"] or "Closed")}</span>'
        )
        cutoff_badge = ''
        if row['cutoff_passed']:
            cutoff_badge = '<span class="badge text-bg-light text-muted ms-1">Cut-off passed</span>'
        elif row['days_to_cutoff'] is not None and row['days_to_cutoff'] <= 1:
            cutoff_badge = '<span class="badge text-bg-warning ms-1">Cut-off soon</span>'

        menu_html = ''
        if row['is_open'] and row['menu_items']:
            menu_html = (
                '<ul class="mb-0 small">'
                + ''.join(
                    f'<li>{escape(it.name)}'
                    + (f' — {escape(_format_money(it.price))}' if it.price else '')
                    + '</li>'
                    for it in row['menu_items']
                )
                + '</ul>'
            )
        elif row['is_open']:
            menu_html = '<em class="text-muted small">No menu published yet.</em>'

        order_html = ''
        if row['order']:
            o = row['order']
            state_label = dict(o._fields['state']._description_selection(o.env)).get(o.state, o.state)
            order_html = (
                f'<strong>{escape(o.menu_item_id.name)}</strong>'
                f' <span class="text-muted small">— {escape(_format_money(o.price_unit))}'
                f' · {escape(state_label)}</span>'
            )

        no_order_html = '<em class="text-muted small">No order</em>'
        rows_html.append(
            f'<tr>'
            f'<td><strong>{escape(d.strftime("%Y-%m-%d"))}</strong><br/>'
            f'<small class="text-muted">{escape(weekday)}</small></td>'
            f'<td>{open_badge}{cutoff_badge}</td>'
            f'<td>{menu_html}</td>'
            f'<td>{order_html or no_order_html}</td>'
            f'</tr>'
        )

    table_html = (
        '<table class="table table-striped">'
        '<thead><tr>'
        '<th style="width:120px;">Date</th>'
        '<th style="width:140px;">Status</th>'
        '<th>Menu</th>'
        '<th style="width:240px;">Your Order</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        '</table>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>School Portal — Orders</title>
    <link rel="stylesheet" type="text/css"
          href="/web/static/lib/bootstrap/dist/css/bootstrap.min.css"/>
    <style>
        body {{ background: #f4f5f7; }}
        .wrapper {{ max-width: 1000px; margin: 2rem auto; padding: 0 1rem; }}
        .student-card {{ background:#fff; border-radius:.5rem; padding:1.25rem; margin-bottom:1rem; }}
        .student-card h1 {{ margin: 0; font-size: 1.5rem; }}
        .nav-bar {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="nav-bar">
            <div>
                <a href="/my" class="text-decoration-none">← Portal Home</a>
            </div>
            <div>
                <a href="/web/session/logout?redirect=/school/login" class="btn btn-sm btn-outline-secondary">Logout</a>
            </div>
        </div>
        <div class="student-card">
            <h1>{escape(student.name or "")} <small class="text-muted">· {escape(class_label)}</small></h1>
            <div class="text-muted small">School Portal — order calendar (read-only preview)</div>
        </div>
        {alert_html}
        {table_html}
        <p class="text-muted small mt-3">
            This is a preview. Order submission and cancellation will be enabled in the next release.
            Orders must be placed at least <strong>{CUTOFF_DAYS} days</strong> in advance.
        </p>
    </div>
</body>
</html>"""


class LcsSchoolPortalOrders(http.Controller):
    """Read-only portal calendar for the student's lunch orders."""

    @http.route('/my/school/orders', type='http', auth='user', sitemap=False, csrf=False)
    def my_school_orders(self, **kw):
        user = request.env.user
        student = user.partner_id
        if not student.is_student:
            # Not a portal student account → redirect to standard portal home
            return request.redirect('/my')

        Order = request.env['lcs.school.order'].sudo()
        Calendar = request.env['lcs.school.calendar.entry'].sudo()
        School = request.env['lcs.school'].sudo()

        today = date.today()
        end = today + timedelta(days=WINDOW_DAYS)
        school_id = student.school_id.id
        class_id = student.class_company_id.id if student.class_company_id else False

        # Pre-load orders for this student in window
        orders_by_date = {
            o.date: o
            for o in Order.search([
                ('student_id', '=', student.id),
                ('date', '>=', today),
                ('date', '<=', end),
            ])
        }

        days = []
        d = today
        while d <= end:
            is_open = Calendar.is_day_open_for_class(school_id, class_id, d)
            closed_reason = None
            if not is_open:
                # Look up a calendar entry to label the reason
                entry = Calendar.search([
                    ('school_id', '=', school_id),
                    ('date', '<=', d),
                    '|', ('date_end', '=', False), ('date_end', '>=', d),
                ], limit=1)
                if entry:
                    closed_reason = dict(
                        entry._fields['day_type']._description_selection(entry.env)
                    ).get(entry.day_type, 'Closed')
                else:
                    closed_reason = 'Weekend' if d.weekday() >= 5 else 'Closed'

            menu_items = School.resolve_menu_for_date(school_id, class_id, d) if is_open else []

            cutoff_date = d - timedelta(days=CUTOFF_DAYS)
            days_to_cutoff = (cutoff_date - today).days
            cutoff_passed = today > cutoff_date

            days.append({
                'date': d,
                'is_open': is_open,
                'closed_reason': closed_reason,
                'menu_items': menu_items,
                'order': orders_by_date.get(d),
                'cutoff_date': cutoff_date,
                'days_to_cutoff': days_to_cutoff,
                'cutoff_passed': cutoff_passed,
            })
            d += timedelta(days=1)

        alerts = School.upcoming_cutoff_alerts(student.id)

        html = _render_orders_page_html(student, days, alerts, request.csrf_token())
        return request.make_response(
            html, headers=[('Content-Type', 'text/html; charset=utf-8')],
        )
