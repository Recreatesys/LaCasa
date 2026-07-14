"""Down-payment invoice customisation for catering sets.

Standard behaviour: the invoice line reads "Down Payment" (or "Down payment of X%").

For catering SOs — where the SO carries one or more `lcs.catering.set`
records — the customer benefits from seeing WHICH set is being paid for
and what dishes it contains. So we:

  1. Rename the down-payment invoice line to
        "Down Payment of {Set Name(s)}"
       (or "Down Payment of X% — {Set Name(s)}" for percentage mode)
  2. Immediately after the down-payment line, append one
        display_type='line_section'  with the set name
     followed by one
        display_type='line_note'  per selected dish in that set.

The LCS Invoice print template renders these enriched rows below the
product line so both the on-screen invoice AND the printed PDF show
what the customer is putting a deposit on.
"""

from odoo import _, api, fields, models
from odoo.tools.misc import formatLang


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    # ── Rename the down-payment line to include the set name ──

    def _prepare_down_payment_invoice_line_values(self, order, so_line, account):
        vals = super()._prepare_down_payment_invoice_line_values(order, so_line, account)
        set_names = self._lcs_collect_set_names(order)
        if set_names:
            label = ', '.join(set_names)
            if self.advance_payment_method == 'percentage':
                vals['name'] = _(
                    "Down Payment of %(pct)s%% — %(sets)s",
                    pct=formatLang(self.env, self.amount),
                    sets=label,
                )
            else:
                vals['name'] = _("Down Payment of %s", label)
        return vals

    @staticmethod
    def _lcs_collect_set_names(order):
        seen_ids, names = set(), []
        for sol in order.order_line:
            cs = getattr(sol, 'catering_set_id', False)
            if cs and cs.id not in seen_ids:
                seen_ids.add(cs.id)
                names.append(cs.name or '')
        return [n for n in names if n]

    # ── Append set-name section + dish notes below the down-payment line ──

    def _create_invoices(self, sale_orders):
        invoice = super()._create_invoices(sale_orders)
        if not invoice:
            return invoice
        # Only augment down-payment invoices, not "regular delivered" invoices —
        # the base wizard's `delivered` branch returns invoices from
        # sale_orders._create_invoices(), and those don't need the set summary.
        if self.advance_payment_method in ('percentage', 'fixed'):
            invoices = invoice if hasattr(invoice, 'ids') and len(invoice) > 1 else [invoice]
            for inv in invoices:
                inv._lcs_append_downpayment_set_summary()
        return invoice


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _lcs_append_downpayment_set_summary(self):
        """Add a section header (set name) + one line_note per selected dish
        after each down-payment product line on this invoice.
        """
        self.ensure_one()
        AML = self.env['account.move.line']

        # The invoice may cover multiple source SOs; process each set once.
        source_orders = self.invoice_line_ids.mapped('sale_line_ids').order_id
        if not source_orders:
            return

        # Collect all catering sets across the source SOs
        sets = self.env['lcs.catering.set']
        for so in source_orders:
            for sol in so.order_line:
                cs = getattr(sol, 'catering_set_id', False)
                if cs and cs not in sets:
                    sets |= cs
        if not sets:
            return

        # Guard against re-running — bail if we've already added a section
        # whose name matches one of our sets
        existing_section_names = set(
            self.invoice_line_ids.filtered(
                lambda l: l.display_type == 'line_section'
            ).mapped('name')
        )

        max_seq = max(self.invoice_line_ids.mapped('sequence') + [0])
        seq = max_seq + 10

        for cs in sets:
            if cs.name in existing_section_names:
                continue
            # Section header for the set
            AML.create({
                'move_id': self.id,
                'display_type': 'line_section',
                'name': cs.name,
                'sequence': seq,
            })
            seq += 1
            # Dish note lines — only selected dishes from any of the source SOs
            for so in source_orders:
                for sol in so.order_line:
                    if getattr(sol, 'catering_set_id', False) != cs:
                        continue
                    if getattr(sol, 'is_addon_piece', False):
                        continue
                    if not getattr(sol, 'dish_selected', True):
                        continue
                    if sol.display_type:
                        continue
                    name = (sol.name or (
                        sol.product_id.display_name
                        if sol.product_id else ''
                    )).strip()
                    if not name:
                        continue
                    AML.create({
                        'move_id': self.id,
                        'display_type': 'line_note',
                        'name': name,
                        'sequence': seq,
                    })
                    seq += 1
