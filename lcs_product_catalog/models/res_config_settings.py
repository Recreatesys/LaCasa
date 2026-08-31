from odoo import fields, models

from odoo.addons.lcs_product_catalog.models.google_geocoder import API_KEY_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    lcs_google_maps_api_key = fields.Char(
        string='Google Maps API Key',
        config_parameter=API_KEY_PARAM,
        help='Used by the delivery-zone lookup to geocode an event address '
             'and read back its Hong Kong district. Needs the Geocoding API '
             'enabled on a billing-enabled Google Cloud project. Without a '
             'key the wizard still works — the district is chosen by hand.',
    )
