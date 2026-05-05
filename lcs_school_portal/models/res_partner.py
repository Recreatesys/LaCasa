from odoo import _, api, fields, models
from odoo.exceptions import UserError

DIET_PREFERENCE_SELECTION = [
    ('combo', 'Combo (no restriction)'),
    ('vegetarian', 'Vegetarian'),
    ('vegan', 'Vegan'),
    ('no_pork', 'No Pork'),
    ('no_beef', 'No Beef'),
    ('no_pork_no_beef', 'No Pork or Beef'),
    ('halal', 'Halal'),
    ('others', 'Others'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_student = fields.Boolean(
        string='Is Student', default=False, index=True,
    )
    chinese_name = fields.Char(string='Chinese Name')
    student_no = fields.Char(string='Student No.', index=True)
    guardian_name = fields.Char(string='Parent Name')
    guardian_phone = fields.Char(string='Parent Phone')

    allergy_ids = fields.Many2many(
        'lcs.allergy', 'res_partner_allergy_rel', 'partner_id', 'allergy_id',
        string='Allergies',
    )
    diet_preference = fields.Selection(
        DIET_PREFERENCE_SELECTION, string='Diet Preference', default='combo',
    )

    class_company_id = fields.Many2one(
        'res.company',
        string='Class',
        domain="[('is_class', '=', True)]",
        help='Class (Odoo company) this student belongs to.',
        index=True,
    )
    school_id = fields.Many2one(
        'lcs.school',
        string='School',
        related='class_company_id.school_id',
        store=True,
        index=True,
    )

    portal_granted = fields.Boolean(string='Portal Access Granted', readonly=True, copy=False)
    portal_user_id = fields.Many2one(
        'res.users', string='Portal User', readonly=True, copy=False,
        help='Internal portal user account created via "Grant Order Portal".',
    )

    @staticmethod
    def _normalize_student_phone(value):
        """Strip whitespace, dashes and HK country code prefix from a phone string.

        Used as the portal password — must be predictable. So '+852 9876 5001',
        '+852-9876-5001' and '98765001' all normalize to '98765001'.
        """
        if not value:
            return value
        cleaned = ''.join(value.split()).replace('-', '')
        for prefix in ('+852', '00852'):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break
        return cleaned

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_student') and vals.get('phone'):
                vals['phone'] = self._normalize_student_phone(vals['phone'])
        return super().create(vals_list)

    def write(self, vals):
        # Normalize student phone if it's being written
        if 'phone' in vals and vals.get('phone'):
            touches_student = bool(vals.get('is_student')) or any(p.is_student for p in self)
            if touches_student:
                vals = dict(vals)
                vals['phone'] = self._normalize_student_phone(vals['phone'])
        return super().write(vals)

    def _build_portal_login(self):
        """Portal login is the student's school email."""
        self.ensure_one()
        return (self.email or '').strip()

    def action_grant_order_portal(self):
        """Create portal user accounts for selected students.

        Login = student's school email (res.partner.email).
        Password = student's phone (res.partner.phone, normalized).
        Skips students missing email or phone, or already granted.
        """
        Users = self.env['res.users']
        portal_group = self.env.ref('base.group_portal')
        granted, skipped = [], []

        for partner in self:
            if not partner.is_student:
                skipped.append((partner, _('not a student')))
                continue
            if not partner.email:
                skipped.append((partner, _('missing email (used as login)')))
                continue
            if not partner.phone:
                skipped.append((partner, _('missing student phone (used as password)')))
                continue
            if partner.portal_granted and partner.portal_user_id:
                skipped.append((partner, _('already granted')))
                continue

            login = partner._build_portal_login()
            password = self._normalize_student_phone(partner.phone)

            existing = Users.with_context(active_test=False).search(
                [('login', '=', login)], limit=1,
            )
            if existing:
                if existing.partner_id == partner:
                    partner.write({'portal_granted': True, 'portal_user_id': existing.id})
                    granted.append(partner)
                else:
                    skipped.append((partner, _('login %s already in use') % login))
                continue

            user = Users.with_context(no_reset_password=True).create({
                'login': login,
                'password': password,
                'partner_id': partner.id,
                'name': partner.name,
                'group_ids': [(6, 0, [portal_group.id])],
            })
            partner.write({'portal_granted': True, 'portal_user_id': user.id})
            granted.append(partner)

        msg = []
        if granted:
            msg.append(_('Granted: %s') % len(granted))
        if skipped:
            msg.append(_('Skipped: %s') % len(skipped))
            for p, reason in skipped[:5]:
                msg.append('  • %s: %s' % (p.name, reason))
            if len(skipped) > 5:
                msg.append('  • ... and %s more' % (len(skipped) - 5))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Grant Order Portal'),
                'message': '\n'.join(msg) or _('Done'),
                'sticky': bool(skipped),
                'type': 'success' if granted and not skipped else ('warning' if skipped else 'info'),
            },
        }

    def action_revoke_order_portal(self):
        """Archive the portal user, leaving the partner record intact."""
        for partner in self:
            if partner.portal_user_id:
                partner.portal_user_id.active = False
            partner.write({'portal_granted': False, 'portal_user_id': False})

    @api.onchange('class_company_id')
    def _onchange_class_company_id(self):
        for partner in self:
            if partner.class_company_id:
                partner.parent_id = partner.class_company_id.partner_id
