"""Save the current quotation's menu as a reusable set.

C21a (client comment, slide 21): "Possible to allow our sales to create their
own package template or to use back their own saved package during the time
they create package to our client?"

What is captured: the dishes, their unit prices, and the quantities. What is
NOT captured: anything that is not part of the menu — the set container line
itself, the auto-generated delivery charge, the Waiter Service line, and
utensil/equipment rows. Those belong to one particular job, not to a template.

Quantities are stored per the source order but the saved set is priced
per-head, so re-using it on another quotation rescales every dish to that
order's guest count — the same way the built-in menus behave.
"""

import math

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaveAsSetWizard(models.TransientModel):
    _name = 'lcs.catering.set.save.wizard'
    _description = 'Save Quotation as a Catering Set'

    order_id = fields.Many2one(
        'sale.order', string='Quotation', required=True, ondelete='cascade',
    )
    set_name = fields.Char(
        string='Set Name', required=True,
        help='Your name is appended automatically, so two people can both '
             'save a "Standard Buffet" without clashing.',
    )
    final_name = fields.Char(
        string='Will be saved as', compute='_compute_final_name', readonly=True,
    )
    line_count = fields.Integer(
        string='Dishes to Save', compute='_compute_preview', readonly=True,
    )
    preview = fields.Text(
        string='Preview', compute='_compute_preview', readonly=True,
    )
    guest_count = fields.Integer(
        related='order_id.guest_count', string='Saved at Guest Count',
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        order = self.env['sale.order'].browse(
            self.env.context.get('active_id')
        ).exists()
        if order:
            vals['order_id'] = order.id
        return vals

    @api.depends('set_name')
    def _compute_final_name(self):
        for wiz in self:
            wiz.final_name = wiz._build_name(wiz.set_name)

    def _build_name(self, base):
        """Append the owner's name so saved sets are distinguishable."""
        base = (base or '').strip()
        if not base:
            return ''
        return '%s (%s)' % (base, self.env.user.name)

    @api.depends('order_id')
    def _compute_preview(self):
        for wiz in self:
            lines = wiz._collect_lines()
            wiz.line_count = len(lines)
            wiz.preview = '\n'.join(
                '%s  x %s  @ %s' % (
                    (line.product_id.display_name or '').split('\n')[0],
                    line.product_uom_qty,
                    line.price_unit,
                )
                for line in lines[:12]
            ) + ('\n…' if len(lines) > 12 else '')

    def _collect_lines(self):
        """The order lines that make up the menu worth saving."""
        self.ensure_one()
        return self.order_id.order_line.filtered(
            lambda l: not l.display_type
            and l.product_id
            and not l.is_addon_piece
            # a set's own container carries the package price, not a dish
            and not self.env['lcs.catering.set'].search_count([
                ('product_id.product_variant_ids', 'in', [l.product_id.id]),
            ])
            # per-job extras, not part of a reusable menu
            and not getattr(l, 'is_lcs_delivery_line', False)
            and not getattr(l, 'is_waiter_service_line', False)
            and not getattr(l, 'is_hardware_line', False)
            # an expanded dish only counts if the customer actually picked it
            and (not l.is_set_line or l.dish_selected)
        )

    def action_save(self):
        self.ensure_one()
        lines = self._collect_lines()
        if not lines:
            raise UserError(_(
                'There is nothing to save. This quotation has no dish lines — '
                'delivery charges, waiter service and utensils are not part of '
                'a set.'
            ))

        name = self._build_name(self.set_name)
        if self.env['lcs.catering.set'].search_count([('name', '=ilike', name)]):
            raise UserError(_(
                'You already have a set called "%s". Choose another name.',
                name,
            ))

        guests = self.order_id.guest_count or 0
        catering_set = self.env['lcs.catering.set'].create({
            'name': name,
            'user_id': self.env.user.id,
            'is_user_template': True,
            'is_shared': False,
            'description': _(
                'Saved from quotation %(order)s on %(date)s.',
                order=self.order_id.name,
                date=fields.Date.context_today(self),
            ),
            'line_ids': [(0, 0, self._prepare_set_line(line, guests, index))
                         for index, line in enumerate(lines)],
            # Price everything per head so re-use rescales to the new order's
            # guest count, rather than falling through get_price_for_size's
            # size-ladder fallback and landing somewhere unpredictable.
            'size_rule_ids': [
                (0, 0, {'size_group': group, 'min_guests': 1,
                        'max_guests': 0, 'size': 'per_piece'})
                for group in ('salad_main', 'pasta_rice', 'canapes')
            ],
        })

        self.order_id.message_post(body=_(
            'Menu saved as the set "<b>%(name)s</b>" (%(count)s dishes). '
            'It is private to you until a Sales Manager publishes it.',
            name=name, count=len(lines),
        ))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'lcs.catering.set',
            'res_id': catering_set.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _prepare_set_line(self, line, guests, index):
        """One saved dish.

        The unit price goes into price_per_piece: combined with the per_piece
        size rules above, that is what makes expansion set the quantity to the
        new order's guest count.

        qty keeps what was on the source quotation. It is the fallback used
        when an order has no guest count, and it records what was actually
        sold.
        """
        return {
            'product_id': line.product_id.id,
            'code': line.set_line_code or '',
            'section': line.set_section or _('Menu'),
            'sequence': (index + 1) * 10,
            'qty': line.product_uom_qty,
            'unit': line.set_unit or line.product_uom_id.name,
            'unit_price': line.price_unit,
            'price_per_piece': line.price_unit,
            'description': (line.name or '').split('\n')[0],
        }
