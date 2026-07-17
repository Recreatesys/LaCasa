from odoo import _, api, fields, models
from odoo.addons.lcs_crm_catering.models.crm_lead import (
    BRAND_SELECTION,
    CALL_VAN_SELECTION,
    DELIVERY_TYPE_SELECTION,
    SERVICE_FORMAT_SELECTION,
    SERVICE_TYPE_SELECTION,
)
from odoo.addons.lcs_crm_catering.models.sale_order import PAYMENT_METHOD_SELECTION


class AccountMove(models.Model):
    _inherit = 'account.move'

    brand = fields.Selection(BRAND_SELECTION, string='Brand')
    attention_to_id = fields.Many2one(
        'res.partner',
        string='Attention To',
    )
    call_van = fields.Selection(CALL_VAN_SELECTION, string='Preferred Driver')
    delivery_time = fields.Float(string='Event / Delivery Time')
    event_hour = fields.Float(string='Event Hour', help='Duration of the event, in hours.')
    event_date = fields.Date(string='Event / Delivery Date')
    event_street = fields.Char(string='Delivery Street')
    event_street2 = fields.Char(string='Delivery Street 2')
    service_format = fields.Selection(SERVICE_FORMAT_SELECTION, string='Service Format')
    service_type = fields.Selection(SERVICE_TYPE_SELECTION, string='Service Type')
    delivery_type = fields.Selection(DELIVERY_TYPE_SELECTION, string='Delivery Type')
    guest_count = fields.Integer(string='No. of Guest')
    event_remark = fields.Text(string='Remark')
    payment_method = fields.Selection(PAYMENT_METHOD_SELECTION, string='Payment Method')
    no_logo = fields.Boolean(
        string='No Logo',
        help='Hide LaCasa branding from packaging / signage (white-label).',
    )
    waiter_service = fields.Boolean(string='Waiter Service')
    is_wedding = fields.Boolean(
        string='Wedding-related',
    )

    lcs_invoice_grouped_html = fields.Html(
        string='Grouped Preview',
        compute='_compute_lcs_invoice_grouped_html',
        sanitize=False,
    )

    @api.depends(
        'invoice_line_ids',
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.quantity',
        'invoice_line_ids.price_unit',
        'invoice_line_ids.name',
        'invoice_line_ids.display_type',
        'invoice_line_ids.product_id',
        'invoice_line_ids.sequence',
        'invoice_line_ids.sale_line_ids',
    )
    def _compute_lcs_invoice_grouped_html(self):
        Qweb = self.env['ir.qweb']
        for move in self:
            move.lcs_invoice_grouped_html = Qweb._render(
                'lcs_crm_catering.invoice_grouped_preview',
                {'move': move, 'groups': move.get_lcs_invoice_groups()},
            )

    def write(self, vals):
        res = super().write(vals)
        if 'call_van' in vals and not self.env.context.get('skip_call_van_sync'):
            for inv in self:
                sos = inv.line_ids.sale_line_ids.order_id
                sos = sos.filtered(lambda s: s.call_van != vals['call_van'])
                if sos:
                    sos.with_context(skip_call_van_sync=True).write({'call_van': vals['call_van']})
        return res

    def get_lcs_invoice_groups(self):
        """Bucket invoice lines by catering-set family for the LCS Invoice PDF.

        Walks self.invoice_line_ids in sequence order. Whenever a set
        container (a product whose template is used by any is_set_line
        SOL on the same invoice) is seen, a new group starts. Every
        subsequent line — dish, section, note — is folded into that
        group until the next container starts.

        Standalone products (Waiter Service, Corkage Fee, Free Delivery,
        etc.) each land in their own single-line group so they still show
        up in the summary table.

        Returns a list of dicts:
          {
            'label':        <container product name or standalone line name>,
            'subtotal':     <sum of price_subtotal across all lines in group>,
            'is_set':       <True if this group has a set container>,
            'container':    <account.move.line or False>,
            'detail_lines': <list of account.move.line for the detail table>,
          }
        """
        self.ensure_one()
        # Identify the product templates that act as set containers.
        set_srcs = self.invoice_line_ids.mapped('sale_line_ids').filtered('is_set_line')
        container_products = set_srcs.mapped('set_product_id')

        groups = []
        current = None
        # Iterate in stable order: (sequence, id).
        lines = self.invoice_line_ids.sorted(lambda l: (l.sequence, l.id))
        for line in lines:
            src = line.sale_line_ids[:1]
            is_container = (
                line.display_type == 'product'
                and line.product_id in container_products
            )

            if is_container:
                # Flush any in-progress group, then start a new one for the set.
                if current:
                    groups.append(current)
                current = {
                    'label': (line.name or line.product_id.display_name or '').split('\n')[0],
                    'subtotal': line.price_subtotal or 0.0,
                    'is_set': True,
                    'container': line,
                    'detail_lines': [],
                }
                continue

            # Section / note: attach to the current group if one is open.
            if line.display_type in ('line_section', 'line_note'):
                if current and current['is_set']:
                    current['detail_lines'].append(line)
                # If no set is open, ignore sections floating at the top.
                continue

            # Product line.
            if line.display_type != 'product':
                continue

            # Set child (dish selection): belongs to the currently-open set.
            if src and (src.is_set_line or src.set_product_id):
                if not current or not current['is_set']:
                    # Orphan child (no container seen yet) — start a group
                    # anonymously to keep it visible.
                    if current:
                        groups.append(current)
                    current = {
                        'label': _('Set items'),
                        'subtotal': 0.0,
                        'is_set': True,
                        'container': False,
                        'detail_lines': [],
                    }
                # Hide unselected dish rows and add-on-piece lines
                # (mirror the previous filter).
                if src.is_set_line and not src.dish_selected:
                    continue
                if src.is_addon_piece:
                    continue
                current['detail_lines'].append(line)
                current['subtotal'] += line.price_subtotal or 0.0
                continue

            # Standalone product (Waiter Service, Free Delivery, Corkage…).
            # Flush any in-progress set group and emit this line as its own.
            if current:
                groups.append(current)
                current = None
            groups.append({
                'label': (line.name or line.product_id.display_name or '').split('\n')[0],
                'subtotal': line.price_subtotal or 0.0,
                'is_set': False,
                'container': line,
                'detail_lines': [],
            })

        if current:
            groups.append(current)
        return groups
