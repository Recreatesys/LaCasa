import logging
import re
from datetime import datetime

from lxml import html as lxml_html

from odoo import api, fields, models
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
]

DELIVERY_TYPE_SELECTION = [
    ('event', 'Event'),
    ('drop_off_pickup', 'Drop-off (Pick-up from Driver)'),
    ('drop_off_door', 'Drop-off (Door to door)'),
]

SETUP_TYPE_SELECTION = [
    ('with_waiter', 'Event with Waiter Service'),
    ('equipment_only', 'Equipment Rental Only'),
    ('simple_setup', 'Simple Setup (No Waiter, Driver Only)'),
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # Event / Delivery fields
    event_date = fields.Date(string='Event / Delivery Date')
    delivery_time = fields.Float(
        string='Event / Delivery Time',
        help='Time of day the event starts / delivery is due (HH:MM).',
    )
    event_hour = fields.Float(
        string='Event Hour',
        help='Duration of the event, in hours (e.g. 3 or 3.5).',
    )
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
    setup_type = fields.Selection(
        SETUP_TYPE_SELECTION,
        string='Setup Type',
        help='Distinguishes equipment-only / simple-setup orders from full event service.',
    )
    is_wedding = fields.Boolean(
        string='Wedding-related',
        help='Tick if this food tasting is for a wedding (used for sequence prefix lacasaWFT).',
    )

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
            fields_map = self._extract_form_fields(html_body)

            if 'info@mrmixcatering.com' in sender:
                self._apply_mrmix_form(fields_map, html_body, custom_values)
                custom_values.setdefault('brand', 'mr_mix')
            elif 'sales@lacasacatering.com' in sender:
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
        # Be lenient about whitespace variations in Chinese form labels
        def get(*keys):
            for k in keys:
                if k in fields_map:
                    return fields_map[k]
            # Match any key that strips to one of the targets
            wanted = {re.sub(r'\s+', '', k) for k in keys}
            for label, value in fields_map.items():
                if re.sub(r'\s+', '', label) in wanted:
                    return value
            return None

        name = get('姓名')
        email = get('電子郵件')
        phone = get('聯絡電話')
        event_date_raw = get('送貨 / 活動日期', '送貨/活動日期', '活動日期')
        event_addr = get('送貨 / 活動地區', '送貨/活動地區', '活動地區')
        enquiry = get('寫下你的查詢', '查詢內容')

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
            vals['event_street'] = event_addr

        # Event date intentionally left empty for manual entry. Raw value goes
        # into the notes so it's not lost.
        bits = []
        if event_date_raw:
            bits.append(f'Requested Event / Delivery Date (please confirm and fill manually): {event_date_raw}')
        if enquiry:
            bits.append(enquiry)
        if bits:
            vals['description'] = (vals.get('description') or '') + '\n'.join(bits)
