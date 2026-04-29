from markupsafe import escape

from odoo import _, http
from odoo.http import request


def _render_login_html(classes, class_label, student_name, redirect, error, csrf_token):
    """Render the login page as plain HTML (bypasses website layout)."""
    options = []
    for c in classes:
        full = c.name or ''
        lbl = full.split('-')[-1].strip() if '-' in full else full
        sel = ' selected="selected"' if lbl == class_label else ''
        options.append(
            f'<option value="{escape(lbl)}"{sel}>{escape(full)}</option>'
        )
    options_html = '\n                                    '.join(options)
    error_html = (
        f'<div class="alert alert-danger" role="alert">{escape(error)}</div>'
        if error else ''
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>School Portal Login</title>
    <link rel="stylesheet" type="text/css"
          href="/web/static/lib/bootstrap/dist/css/bootstrap.min.css"/>
    <style>
        body {{ background: #f4f5f7; }}
        .login-card {{ max-width: 420px; margin: 8vh auto; }}
        .login-card .card-body {{ padding: 2rem; }}
        .login-card h2 {{ font-weight: 600; margin-bottom: 1.5rem; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card shadow-sm login-card">
            <div class="card-body">
                <h2>School Portal</h2>
                <form role="form" action="/school/login" method="post">
                    <input type="hidden" name="csrf_token" value="{escape(csrf_token)}"/>
                    <input type="hidden" name="redirect" value="{escape(redirect or '')}"/>

                    <div class="mb-3">
                        <label for="class_label" class="form-label">Class</label>
                        <select name="class_label" id="class_label" class="form-select" required="required">
                            <option value="">— Select Class —</option>
                            {options_html}
                        </select>
                    </div>

                    <div class="mb-3">
                        <label for="student_name" class="form-label">Student Name</label>
                        <input type="text" name="student_name" id="student_name"
                               class="form-control" value="{escape(student_name or '')}"
                               required="required" autocomplete="off"
                               autofocus="autofocus" placeholder="e.g. 陳大文"/>
                    </div>

                    <div class="mb-3">
                        <label for="password" class="form-label">Parent Phone (Password)</label>
                        <input type="password" name="password" id="password"
                               class="form-control" required="required"
                               autocomplete="current-password"/>
                    </div>

                    {error_html}

                    <div class="d-grid gap-2 mt-3">
                        <button type="submit" class="btn btn-primary">Log in</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</body>
</html>"""


class LcsSchoolPortalLogin(http.Controller):
    """Custom login page for school parents.

    URL: /school/login
    Form fields: Class (dropdown) + Student Name (text) + Password.
    Backend authenticates as login = '<class>-<student_name>'.
    """

    @http.route('/school/login', type='http', auth='public', sitemap=False, csrf=True)
    def school_login(self, redirect=None, **kw):
        if request.session.uid:
            return request.redirect(redirect or '/my')

        classes = request.env['res.company'].sudo().search(
            [('school_id', '!=', False)], order='name',
        )
        class_label = (kw.get('class_label') or '').strip()
        student_name = (kw.get('student_name') or '').strip()
        error = None

        if request.httprequest.method == 'POST':
            password = (kw.get('password') or '').strip()
            if not class_label or not student_name or not password:
                error = _('Please fill in all fields.')
            else:
                login = f"{class_label}-{student_name}"
                try:
                    credential = {'login': login, 'password': password, 'type': 'password'}
                    request.session.authenticate(request.session.db, credential)
                    return request.redirect(redirect or '/my')
                except Exception:
                    error = _('Invalid student name, class, or password.')

        html = _render_login_html(
            classes, class_label, student_name, redirect, error, request.csrf_token(),
        )
        return request.make_response(
            html, headers=[('Content-Type', 'text/html; charset=utf-8')],
        )
