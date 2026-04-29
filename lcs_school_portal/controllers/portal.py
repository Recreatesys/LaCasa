import logging

from odoo import _, http
from odoo.http import request

_logger = logging.getLogger(__name__)
_logger.warning('===== LCS_SCHOOL_PORTAL CONTROLLER LOADED =====')


class LcsSchoolPortalLogin(http.Controller):
    """Custom login page for school parents.

    URL: /school/login
    Form fields: Class (dropdown) + Student Name (text) + Password.
    Backend authenticates as login = '<class>-<student_name>'.
    """

    @http.route('/school/ping', type='http', auth='none', sitemap=False, csrf=False)
    def school_ping(self, **kw):
        return 'pong'

    @http.route('/school/login', type='http', auth='public', sitemap=False, csrf=True)
    def school_login(self, redirect=None, **kw):
        if request.session.uid:
            return request.redirect(redirect or '/my')

        classes = request.env['res.company'].sudo().search(
            [('school_id', '!=', False)], order='name',
        )

        values = {
            'classes': classes,
            'class_label': kw.get('class_label', ''),
            'student_name': kw.get('student_name', ''),
            'redirect': redirect or '',
            'error': None,
        }

        if request.httprequest.method == 'POST':
            class_label = (kw.get('class_label') or '').strip()
            student_name = (kw.get('student_name') or '').strip()
            password = (kw.get('password') or '').strip()

            if not class_label or not student_name or not password:
                values['error'] = _('Please fill in all fields.')
            else:
                login = f"{class_label}-{student_name}"
                try:
                    credential = {'login': login, 'password': password, 'type': 'password'}
                    request.session.authenticate(request.session.db, credential)
                    return request.redirect(redirect or '/my')
                except Exception:
                    values['error'] = _('Invalid student name, class, or password.')

        return request.render('lcs_school_portal.school_login_template', values)
