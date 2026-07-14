import logging
import re
from datetime import datetime

from lxml import html as lxml_html

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


BRAND_SELECTION = [
    ('lacasa', 'Lacasa'),
    ('mr_mix', 'Mr Mix'),
    ('meerkat', 'Meerkat'),
]

CLIENT_TYPE_SELECTION = [
    ('corporate', 'Corporate'),
    ('private', 'Private'),
    ('organization', 'Organization'),
    ('partner', 'Partner'),
]

SERVICE_FORMAT_SELECTION = [
    ('food_delivery', 'Food Delivery'),
    ('event_catering', 'Event Catering'),
]

SERVICE_TYPE_SELECTION = [
    ('canapes', 'Canapes'),
    ('party_food', 'Party Food'),
    ('meal_box', 'Meal Box'),
    ('buffet', 'Buffet'),
    ('cocktail', 'Cocktail'),
    ('wedding_buffet', 'Wedding Buffet'),
    ('wedding_cocktail', 'Wedding Cocktail'),
    ('breakfast_refreshment', 'Breakfast / Refreshment Break'),
    ('sit_down_menu', 'Sit-down Menu'),
    ('utensil', 'Utensil'),
    ('waiter_service', 'Waiter Service'),
    ('oem', 'OEM'),
    ('school_meal', 'School Meal'),
    ('food_tasting', 'Food Tasting'),
    ('staff_meal', 'Staff Meal'),
    ('event', 'Event'),
]

DELIVERY_TYPE_SELECTION = [
    ('event', 'Event'),
    ('drop_off_pickup', 'Drop-off (Pick-up from Driver)'),
    ('drop_off_door', 'Drop-off (Door to door)'),
]

CALL_VAN_SELECTION = [
    ('ah_yuen', '阿源'),
    ('no_need', 'No need'),
    ('event_team', 'Arranged by event team'),
    ('man_zai', '文仔'),
    ('lalamove', 'Lalamove'),
    ('hang_gor', '恆哥'),
    ('self_deliver', '自己送'),
    ('roy', 'Roy'),
    ('lik_pak', '力柏'),
    ('self_pickup', 'Self Pick-up'),
    ('dat', '達'),
    ('fu_gor', '虎哥'),
    ('supervan', 'SuperVan'),
    ('gogovan', 'GoGoVan'),
    ('leopard', 'Leopard'),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ── Event / Delivery — date range ──
    event_date_start = fields.Date(
        string='Event / Delivery Date (Start)',
    )
    event_date_end = fields.Date(
        string='Event / Delivery Date (End)',
        help='Leave blank for a single-day event.',
    )
    event_day_count = fields.Integer(
        string='# Days',
        compute='_compute_event_day_count', store=True,
    )
    # Back-compat alias for existing code, imports and integrations.
    event_date = fields.Date(
        string='Event / Delivery Date',
        related='event_date_start', store=True, readonly=False,
    )

    # ── Event / Delivery — time slot ──
    event_time_start = fields.Float(
        string='Event / Delivery Time (Start)',
        help='Time of day the event starts / delivery is due (HH:MM).',
    )
    event_time_end = fields.Float(
        string='Event / Delivery Time (End)',
        help='Time of day the event ends (HH:MM).',
    )
    # Back-compat alias — old name still used by lcs_event_order sync + imports.
    delivery_time = fields.Float(
        string='Event / Delivery Time',
        related='event_time_start', store=True, readonly=False,
    )

    event_hour = fields.Float(
        string='Event Hour',
        help='Duration of the event, in hours (e.g. 3 or 3.5). '
             'Auto-derived from Event / Delivery Time (end - start) when '
             'both times are entered; still editable manually.',
    )

    @api.onchange('event_time_start', 'event_time_end')
    def _onchange_event_time_derive_hour(self):
        """When both start and end are set, auto-fill Event Hour from
        the interval. If end <= start, leave Event Hour untouched (user
        may still be typing)."""
        for rec in self:
            if rec.event_time_start and rec.event_time_end \
                    and rec.event_time_end > rec.event_time_start:
                rec.event_hour = rec.event_time_end - rec.event_time_start

    @api.depends('event_date_start', 'event_date_end')
    def _compute_event_day_count(self):
        for rec in self:
            start = rec.event_date_start
            end = rec.event_date_end or start
            if not start:
                rec.event_day_count = 0
            elif end < start:
                rec.event_day_count = 1
            else:
                rec.event_day_count = (end - start).days + 1

    @api.constrains('event_date_start', 'event_date_end')
    def _check_event_date_range(self):
        for rec in self:
            if rec.event_date_end and rec.event_date_start and \
                    rec.event_date_end < rec.event_date_start:
                raise UserError(_(
                    'Event end date must be on or after the start date.'
                ))
            if rec.event_day_count > 7:
                raise UserError(_(
                    'Event range is limited to 7 consecutive days.'
                ))
    event_street = fields.Char(string='Street')
    event_street2 = fields.Char(string='Street 2')
    event_country_id = fields.Many2one(
        'res.country',
        string='Country',
        default=lambda self: self.env.ref('base.hk', raise_if_not_found=False),
    )

    # Catering fields
    brand = fields.Selection(BRAND_SELECTION, string='Brand')
    client_type = fields.Selection(CLIENT_TYPE_SELECTION, string='Client Type')
    service_format = fields.Selection(SERVICE_FORMAT_SELECTION, string='Service Format')
    service_type = fields.Selection(SERVICE_TYPE_SELECTION, string='Service Type')
    delivery_type = fields.Selection(DELIVERY_TYPE_SELECTION, string='Delivery Type')
    guest_count = fields.Integer(string='No. of Guest')
    event_remark = fields.Text(string='Remark')
    no_logo = fields.Boolean(
        string='No Logo',
        help='Hide LaCasa branding from packaging / signage (white-label).',
    )
    waiter_service = fields.Boolean(
        string='Waiter Service',
        help='Tick if this event requires waiter staffing. Reveals the Waiters tab on the SO.',
    )
    call_van = fields.Selection(
        CALL_VAN_SELECTION, string='Preferred Driver',
        help='Preferred driver / van arrangement for the delivery. '
             'Can be changed later on the SO or Event Order.',
    )
    is_wedding = fields.Boolean(
        string='Wedding-related',
        help='Tick if this food tasting is for a wedding (used for sequence prefix lacasaWFT).',
    )

    # ──────────────────────────────────────────────────────────
    # Stage-reverse guard: salespeople can only advance, not regress
    # ──────────────────────────────────────────────────────────

    def write(self, vals):
        if 'stage_id' in vals and vals['stage_id']:
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            is_manager = self.env.user.has_group('sales_team.group_sale_manager')
            if not is_manager and not self.env.is_superuser():
                for lead in self:
                    if lead.stage_id and new_stage.sequence < lead.stage_id.sequence:
                        raise UserError(_(
                            'Only Sales Managers can move "%(lead)s" back from '
                            '"%(curr)s" to an earlier stage ("%(target)s").'
                        ) % {
                            'lead': lead.name or _('this opportunity'),
                            'curr': lead.stage_id.display_name,
                            'target': new_stage.display_name,
                        })
        return super().write(vals)

    # ──────────────────────────────────────────────────────────
    # Email-to-Lead parsers for known catering enquiry forms
    # ──────────────────────────────────────────────────────────

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Hook into incoming-mail lead creation to pre-fill structured fields
        when the sender is a known enquiry form (Mr.Mix or La Casa).

        mail.thread.message_new forcibly sets email_from = sender after
        custom_values is applied, so any parsed email from the form body
        gets clobbered. Workaround: track the parsed email and re-write it
        after super() returns.
        """
        custom_values = dict(custom_values or {})
        parsed_overrides = {}
        try:
            sender = (msg_dict.get('email_from') or '').lower()
            html_body = msg_dict.get('body') or ''

            if 'info@mrmixcatering.com' in sender:
                # Mr.Mix uses <br>-separated "Label: Value" lines, not <strong>
                fields_map = self._extract_br_label_value_pairs(html_body)
                self._apply_mrmix_form(fields_map, html_body, custom_values)
                custom_values.setdefault('brand', 'mr_mix')
            elif 'sales@lacasacatering.com' in sender:
                # La Casa uses <strong>label</strong> + value-row HTML tables
                fields_map = self._extract_form_fields(html_body)
                self._apply_lacasa_form(fields_map, html_body, custom_values)
                custom_values.setdefault('brand', 'lacasa')

            # Capture fields that mail.thread.message_new will overwrite so
            # we can re-apply them post-create.
            if custom_values.get('email_from'):
                parsed_overrides['email_from'] = custom_values['email_from']
            if custom_values.get('phone'):
                parsed_overrides['phone'] = custom_values['phone']
        except Exception:
            _logger.exception('Failed to parse incoming enquiry email; falling back to default behavior.')

        new_lead = super().message_new(msg_dict, custom_values=custom_values)

        if parsed_overrides:
            new_lead.write(parsed_overrides)
        return new_lead

    @staticmethod
    def _parse_date(value):
        """Try several common date formats. Return a date or None."""
        if not value:
            return None
        value = value.strip()
        for fmt in (
            '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d',
            '%-d/%-m/%Y', '%-d-%-m-%Y',
            '%d %b %Y', '%d %B %Y',
        ):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        # Last-ditch: try to be lenient about single-digit day/month
        m = re.match(r'^\s*(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\s*$', value)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return datetime(y, mo, d).date()
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_form_fields(html_body):
        """Extract {label: value} pairs from a form-style HTML email.

        The two forms we support both render each field as:
          <strong>Label</strong>            (in one row of a table)
          Value                              (in the next row)

        We find every <strong> tag and grab the text of the *next* <tr> within
        the same enclosing <table>. Falls back to the next sibling row if the
        table layout is non-standard.
        """
        if not html_body:
            return {}
        try:
            tree = lxml_html.fromstring(html_body)
        except Exception:
            _logger.warning('Could not parse email HTML; skipping form extraction.')
            return {}

        result = {}
        for strong in tree.xpath('//strong'):
            label = (strong.text_content() or '').strip()
            if not label:
                continue
            # Find the closest enclosing <table>, then the next <tr> after the
            # one that contains this <strong>.
            tables = strong.xpath('ancestor::table[1]')
            if not tables:
                continue
            table = tables[0]
            rows = table.xpath('.//tr')
            value = None
            for i, row in enumerate(rows):
                if strong in row.iter():
                    if i + 1 < len(rows):
                        value = (rows[i + 1].text_content() or '').strip()
                    break
            if value:
                result[label] = value
        return result

    @staticmethod
    def _extract_br_label_value_pairs(html_body):
        """Extract {label: value} pairs from a <br>-separated HTML body.

        Used for plain-form emails like Mr.Mix's, where each form field is
        on its own line as 'Label: Value', separated by <br> tags. Stops at
        the first '---' line so submission-metadata footer (date/time/URL/IP/
        user agent / Powered by) is excluded.

        Labels are returned with all whitespace stripped so that
        '送貨 /活動日期' and '送貨 / 活動日期' both map to the same key.
        """
        if not html_body:
            return {}
        # <br>, <br/>, <br /> → newline
        text = re.sub(r'<br\s*/?>', '\n', html_body, flags=re.IGNORECASE)
        # Strip remaining HTML tags (<p>, etc.) → plain text
        if '<' in text:
            text = html2plaintext(text)

        result = {}
        for raw_line in text.split('\n'):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('---'):
                break  # footer metadata starts here
            # Split on first colon (ASCII or full-width)
            m = re.match(r'^([^:：]+?)[:：]\s*(.*)$', line)
            if not m:
                continue
            label = re.sub(r'\s+', '', m.group(1).strip())
            value = m.group(2).strip()
            if value:
                result[label] = value
        return result

    @api.model
    def _apply_lacasa_form(self, fields_map, html_body, vals):
        """Map a La Casa enquiry form's {label: value} into lead fields.

        Expected labels: Name, Phone Number, Email, Service Format,
        Event / Delivery Date, Comment or Message.
        """
        name = fields_map.get('Name')
        phone = fields_map.get('Phone Number')
        email = fields_map.get('Email')
        service_format = fields_map.get('Service Format')
        event_date_raw = fields_map.get('Event / Delivery Date')
        comment = fields_map.get('Comment or Message')

        # Email/phone come from the form body (the real customer contact),
        # not the website's sender envelope address. Force-overwrite so the
        # sender's email_from from msg_dict doesn't win.
        # Opportunity name = customer's Name (overrides email subject default)
        if name:
            vals['contact_name'] = name
            vals['name'] = name
        if email:
            vals['email_from'] = email
        if phone:
            vals['phone'] = phone

        # Event date is intentionally left empty for manual entry. Put the raw
        # value into the notes/description so it's not lost.
        bits = []
        if event_date_raw:
            bits.append(f'Requested Event / Delivery Date (please confirm and fill manually): {event_date_raw}')
        if service_format:
            bits.append(f'Service Format: {service_format}')
        if comment:
            bits.append(f'Comment / Message:\n{comment}')
        if bits:
            vals['description'] = (vals.get('description') or '') + '\n'.join(bits)

    @api.model
    def _apply_mrmix_form(self, fields_map, html_body, vals):
        """Map a Mr.Mix enquiry form's {label: value} into lead fields.

        Expected labels: 姓名, 電子郵件, 聯絡電話, 送貨 / 活動日期,
        送貨 / 活動地區, 寫下你的查詢.
        """
        # Mr.Mix labels are whitespace-stripped by _extract_br_label_value_pairs.
        # 姓名 -> contact_name + opportunity name
        # 電子郵件 -> email_from
        # 聯絡電話 -> phone
        # 送貨/活動日期 -> event_date (auto-filled if parseable)
        # 送貨/活動地區 -> event_street2 (Street 2)
        # 寫下你的查詢 -> description (notes)
        name = fields_map.get('姓名')
        email = fields_map.get('電子郵件')
        phone = fields_map.get('聯絡電話')
        event_date_raw = fields_map.get('送貨/活動日期') or fields_map.get('活動日期')
        event_addr = fields_map.get('送貨/活動地區') or fields_map.get('活動地區')
        enquiry = fields_map.get('寫下你的查詢') or fields_map.get('查詢內容')

        # Force-overwrite name/email/phone so the sender's envelope and email
        # subject default don't win.
        if name:
            vals['contact_name'] = name
            vals['name'] = name
        if email:
            vals['email_from'] = email
        if phone:
            vals['phone'] = phone
        if event_addr:
            vals['event_street2'] = event_addr

        parsed_date = self._parse_date(event_date_raw) if event_date_raw else None
        if parsed_date:
            vals['event_date'] = parsed_date
        elif event_date_raw:
            # Couldn't parse — fall back to a note so the date isn't lost.
            vals['event_remark'] = (vals.get('event_remark') or '') + \
                f'Event date (raw): {event_date_raw}\n'

        if enquiry:
            vals['description'] = (vals.get('description') or '') + enquiry
