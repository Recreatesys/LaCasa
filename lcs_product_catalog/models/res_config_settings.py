from odoo import fields, models

from odoo.addons.lcs_product_catalog.models.google_geocoder import API_KEY_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── C21c: manager approval for low-margin quotations ──
    lcs_margin_approval_active = fields.Boolean(
        string='Require Approval on Low Margin',
        config_parameter='lcs_product_catalog.margin_approval_active',
        help='When on, confirming a quotation that has any priced line below '
             'the margin floor needs a Sales Manager.',
    )
    lcs_margin_approval_threshold = fields.Float(
        string='Minimum Line Margin (%)',
        config_parameter='lcs_product_catalog.margin_approval_threshold',
        default=0.0,
        help='A priced order line whose margin falls below this percentage '
             'needs a Sales Manager to confirm the quotation. Margin is '
             '(subtotal - cost) / subtotal, as computed by Odoo\'s Margins '
             'feature. Lines with no revenue — unpicked set dishes and '
             'section headers — are ignored.',
    )

    lcs_google_maps_api_key = fields.Char(
        string='Google Maps API Key',
        config_parameter=API_KEY_PARAM,
        help='Used by the delivery-zone lookup to geocode an event address '
             'and read back its Hong Kong district. Needs the Geocoding API '
             'enabled on a billing-enabled Google Cloud project. Without a '
             'key the wizard still works — the district is chosen by hand.',
    )
