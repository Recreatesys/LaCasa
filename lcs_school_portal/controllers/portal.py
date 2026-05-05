from markupsafe import escape

from odoo import _, http
from odoo.http import request


def _render_login_html(email, redirect, error, csrf_token):
    """Render the login page as plain HTML (bypasses website layout)."""
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
                        <label for="email" class="form-label">School Email</label>
                        <input type="email" name="email" id="email"
                               class="form-control" value="{escape(email or '')}"
                               required="required" autocomplete="username"
                               autofocus="autofocus"
                               placeholder="student@school.example.com"/>
                    </div>

                    <div class="mb-3">
                        <label for="password" class="form-label">Phone (Password)</label>
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
    """Custom login page for school students/parents.

    URL: /school/login
    Form fields: School Email + Phone (Password).
    """

    @http.route('/school/login', type='http', auth='public', sitemap=False, csrf=True)
    def school_login(self, redirect=None, **kw):
        if request.session.uid:
            return request.redirect(redirect or '/my')

        email = (kw.get('email') or '').strip()
        error = None

        if request.httprequest.method == 'POST':
            password = (kw.get('password') or '').strip()
            if not email or not password:
                error = _('Please fill in all fields.')
            else:
                try:
                    credential = {'login': email, 'password': password, 'type': 'password'}
                    request.session.authenticate(request.env, credential)
                    return request.redirect(redirect or '/my')
                except Exception:
                    error = _('Invalid email or password.')

        html = _render_login_html(email, redirect, error, request.csrf_token())
        return request.make_response(
            html, headers=[('Content-Type', 'text/html; charset=utf-8')],
        )
