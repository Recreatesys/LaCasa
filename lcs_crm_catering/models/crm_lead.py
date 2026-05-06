import logging
import re
from datetime import datetime

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
        when the sender is a known enquiry form (Mr.Mix or La Casa)."""
        custom_values = dict(custom_values or {})
        try:
            sender = (msg_dict.get('email_from') or '').lower()
            body = msg_dict.get('body') or ''
            text = html2plaintext(body) if '<' in body else body

            if 'info@mrmixcatering.com' in sender:
                self._parse_mrmix_form(text, custom_values)
                custom_values.setdefault('brand', 'mr_mix')
            elif 'sales@lacasacatering.com' in sender:
                self._parse_lacasa_form(text, custom_values)
                custom_values.setdefault('brand', 'lacasa')
        except Exception:
            _logger.exception('Failed to parse incoming enquiry email; falling back to default behavior.')

        return super().message_new(msg_dict, custom_values=custom_values)

    @staticmethod
    def _parse_date(value):
        """Try several common date formats. Return a date or None."""
        if not value:
            return None
        value = value.strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    @api.model
    def _parse_mrmix_form(self, text, vals):
        """Parse the Mr.Mix enquiry form (Chinese labels, value on same line).

        Example:
          姓名: Felix Testing
          電子郵件: polly@lacasacatering.com
          聯絡電話: 61004061
          送貨 / 活動日期: 2026-06-15
          送貨 / 活動地區: Central
          寫下你的查詢: <multi-line message>
        """
        # Same-line: label: value (allow Chinese or ASCII colon, optional spaces)
        def grab(label_pattern):
            m = re.search(label_pattern + r'\s*[:：]\s*(.+?)(?:\r?\n|$)', text)
            return m.group(1).strip() if m else None

        name = grab(r'姓名')
        email = grab(r'電子郵件')
        phone = grab(r'聯絡電話')
        event_date_raw = grab(r'送貨\s*/\s*活動日期')
        event_addr = grab(r'送貨\s*/\s*活動地區')

        # Enquiry can span multiple lines until the end of the message
        m = re.search(r'寫下你的查詢\s*[:：]\s*([\s\S]+?)(?:\Z|--\s*\n)', text)
        enquiry = m.group(1).strip() if m else None

        if name:
            vals.setdefault('contact_name', name)
            vals.setdefault('name', f'Mr.Mix enquiry — {name}')
        if email:
            vals.setdefault('email_from', email)
        if phone:
            vals.setdefault('phone', phone)
        if event_addr:
            vals.setdefault('event_street', event_addr)
        parsed_date = self._parse_date(event_date_raw) if event_date_raw else None
        if parsed_date:
            vals.setdefault('event_date', parsed_date)
        elif event_date_raw:
            # Couldn't parse — keep raw value in remark so it's not lost
            vals['event_remark'] = (vals.get('event_remark') or '') + \
                f'Event date (raw): {event_date_raw}\n'
        if enquiry:
            vals['description'] = (vals.get('description') or '') + enquiry

    @api.model
    def _parse_lacasa_form(self, text, vals):
        """Parse the La Casa Catering enquiry form (English labels, value on
        the line below the label).

        Example:
          Name
          Roberterutt
          Phone Number
          88582187274
          Email
          abbie@example.com
          Service Format
          Food Delivery (packed in foil / paper box)
          Event / Delivery Date
          1978-10-10
          Comment or Message
          <multi-line message>
        """
        def grab_below(label_pattern):
            # Match: <label-line>\n<value-line>
            m = re.search(
                label_pattern + r'\s*\r?\n\s*(.+?)(?:\r?\n|$)',
                text, flags=re.IGNORECASE,
            )
            return m.group(1).strip() if m else None

        name = grab_below(r'^\s*Name')
        phone = grab_below(r'^\s*Phone\s*Number')
        email = grab_below(r'^\s*Email')
        service_format_raw = grab_below(r'^\s*Service\s*Format')
        event_date_raw = grab_below(r'^\s*Event\s*/?\s*Delivery\s*Date')

        # Comment/Message can span multiple lines until end
        m = re.search(
            r'Comment\s+or\s+Message\s*\r?\n([\s\S]+?)(?:\Z|--\s*\n)',
            text, flags=re.IGNORECASE,
        )
        comment = m.group(1).strip() if m else None

        if name:
            vals.setdefault('contact_name', name)
            vals.setdefault('name', f'La Casa enquiry — {name}')
        if email:
            vals.setdefault('email_from', email)
        if phone:
            vals.setdefault('phone', phone)
        parsed_date = self._parse_date(event_date_raw) if event_date_raw else None
        if parsed_date:
            vals.setdefault('event_date', parsed_date)
        elif event_date_raw:
            vals['event_remark'] = (vals.get('event_remark') or '') + \
                f'Event date (raw): {event_date_raw}\n'

        # Service format and Comment go into description (free text)
        bits = []
        if service_format_raw:
            bits.append(f'Service Format: {service_format_raw}')
        if comment:
            bits.append(f'Comment / Message:\n{comment}')
        if bits:
            vals['description'] = (vals.get('description') or '') + '\n'.join(bits)
