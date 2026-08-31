"""Delivery zones — C08 (client comment, slide 8).

    "Possible to map the delivery charge directly by tracking Event address
     & delivery type?"

LCS prices delivery by four zones (A HK Island, B Kowloon / Kwai Tsing,
C other N.T., D Tung Chung / Discovery Bay) crossed with how it is delivered.
The zone is a *category*, not a distance, so the whole job is: turn a written
address into one of four buckets, then look up (zone × delivery type) in a
rate table.

Both halves are data, not code:

  lcs.delivery.district  maps a place name to a zone. Seeded with Hong Kong's
                         18 administrative districts plus the two localities
                         that get their own zone (Tung Chung, Discovery Bay,
                         which sit inside Islands District but cost more).
  lcs.delivery.zone.rate maps (zone, delivery type) to the product to charge.

So when LCS supplies the missing Simple Set-up and Event rates, ops adds rows
— no code change, no deployment.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.lcs_crm_catering.models.crm_lead import DELIVERY_TYPE_SELECTION


class DeliveryZone(models.Model):
    _name = 'lcs.delivery.zone'
    _description = 'Delivery Zone'
    _order = 'sequence, code'

    name = fields.Char(string='Zone', required=True)
    code = fields.Char(
        string='Code', required=True,
        help='Short zone code as used on the delivery products, e.g. "A".',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    district_ids = fields.One2many(
        'lcs.delivery.district', 'zone_id', string='Districts / Localities',
    )
    rate_ids = fields.One2many(
        'lcs.delivery.zone.rate', 'zone_id', string='Rates',
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Each delivery zone code must be unique.'),
    ]

    def _get_rate_product(self, delivery_type):
        """The product to charge for this zone and delivery type, or empty.

        Empty is a legitimate answer: Simple Set-up (Round-trip / One-trip)
        and Event have no agreed rate yet, and Self Pick-up should never carry
        a charge. Callers surface that rather than guessing a price.
        """
        self.ensure_one()
        rate = self.rate_ids.filtered(
            lambda r: r.delivery_type == delivery_type
        )[:1]
        return rate.product_id


class DeliveryDistrict(models.Model):
    _name = 'lcs.delivery.district'
    _description = 'Delivery District / Locality'
    _order = 'sequence, name'

    name = fields.Char(string='District / Locality', required=True)
    name_zh = fields.Char(string='Chinese Name')
    zone_id = fields.Many2one(
        'lcs.delivery.zone', string='Zone', required=True, ondelete='cascade',
    )
    sequence = fields.Integer(
        default=20,
        help='Checked in this order when matching a geocoded address. '
             'Localities that override their district (Tung Chung and '
             'Discovery Bay, inside Islands District) sort first.',
    )
    active = fields.Boolean(default=True)
    match_keys = fields.Char(
        string='Match Keys',
        help='Comma-separated aliases matched against the components Google '
             'returns, e.g. "Central and Western,Central,中西區,中環". Matching '
             'is case-insensitive and ignores surrounding text.',
    )

    def _iter_match_keys(self):
        """Every string this record should match on, longest first.

        Longest-first so "Tsim Sha Tsui" is preferred over a bare "Tsim" if
        both were configured, and so a longer alias cannot be shadowed by a
        shorter substring of itself.
        """
        self.ensure_one()
        keys = [self.name or '', self.name_zh or '']
        keys += (self.match_keys or '').split(',')
        cleaned = {k.strip().lower() for k in keys if k and k.strip()}
        return sorted(cleaned, key=len, reverse=True)

    @api.model
    def _match_address_parts(self, parts):
        """First district whose alias appears in any of `parts`.

        `parts` are the address components Google returned plus the formatted
        address. Returns an empty recordset when nothing matches — the wizard
        then asks the user to choose, rather than guessing a zone and silently
        billing the wrong rate.
        """
        haystack = [p.lower() for p in parts if p]
        if not haystack:
            return self.browse()
        for district in self.search([]):
            for key in district._iter_match_keys():
                if any(key in part for part in haystack):
                    return district
        return self.browse()


class DeliveryZoneRate(models.Model):
    _name = 'lcs.delivery.zone.rate'
    _description = 'Delivery Zone Rate'
    _order = 'zone_id, delivery_type'

    zone_id = fields.Many2one(
        'lcs.delivery.zone', string='Zone', required=True, ondelete='cascade',
    )
    delivery_type = fields.Selection(
        DELIVERY_TYPE_SELECTION, string='Delivery Type', required=True,
    )
    product_id = fields.Many2one(
        'product.product', string='Delivery Product', required=True,
        domain="[('type', '=', 'service')]",
    )
    price = fields.Float(
        related='product_id.lst_price', string='Price', readonly=True,
    )

    _sql_constraints = [
        ('zone_type_uniq', 'unique(zone_id, delivery_type)',
         'A zone can only have one rate per delivery type.'),
    ]

    @api.constrains('product_id')
    def _check_product_is_service(self):
        for rate in self:
            if rate.product_id and rate.product_id.type != 'service':
                raise ValidationError(_(
                    'The delivery product "%s" must be a service.',
                    rate.product_id.display_name,
                ))
