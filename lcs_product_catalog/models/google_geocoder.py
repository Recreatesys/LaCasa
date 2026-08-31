"""Thin wrapper over the Google Geocoding API.

base_geolocalize is deliberately not used: it hands back latitude and
longitude only, and what a delivery zone needs is the *district* — which lives
in the `address_components` of the raw response.

The API key is stored as the ir.config_parameter
`lcs_product_catalog.google_maps_api_key` (Settings ▸ Sales ▸ LCS Catering).
"""

import logging

import requests

from odoo import _, api, models

_logger = logging.getLogger(__name__)

GEOCODE_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
API_KEY_PARAM = 'lcs_product_catalog.google_maps_api_key'
TIMEOUT = 10

# Google's own status codes are not something to show a salesperson.
# Plain strings here, run through _() where they are used.
STATUS_MESSAGES = {
    'ZERO_RESULTS':
        'Google could not find that address. Check it, or choose the '
        'district below by hand.',
    'OVER_QUERY_LIMIT':
        'The Google Maps quota has been used up. Choose the district below '
        'by hand and tell your administrator.',
    'REQUEST_DENIED':
        'Google rejected the request — the Maps API key is missing, invalid, '
        'or has no access to the Geocoding API. Choose the district below by '
        'hand.',
    'INVALID_REQUEST':
        'The address was empty or malformed.',
    'UNKNOWN_ERROR':
        'Google had a temporary problem. Try again, or choose the district '
        'below by hand.',
}


class GoogleGeocoder(models.AbstractModel):
    _name = 'lcs.google.geocoder'
    _description = 'Google Geocoding helper'

    @api.model
    def _get_api_key(self):
        return (self.env['ir.config_parameter'].sudo()
                .get_param(API_KEY_PARAM) or '').strip()

    @api.model
    def geocode(self, address):
        """Geocode `address`, biased to Hong Kong.

        Returns a dict:
            {'ok': True,  'formatted': str, 'parts': [str, …],
             'lat': float, 'lng': float}
            {'ok': False, 'error': <message for the user>}

        Never raises for a bad address or an API problem — the caller offers a
        manual district choice instead, so a failed lookup cannot stop someone
        quoting.
        """
        address = (address or '').strip()
        if not address:
            return {'ok': False, 'error': _('Enter a delivery address first.')}

        api_key = self._get_api_key()
        if not api_key:
            return {'ok': False, 'error': _(
                'No Google Maps API key is configured. Set one in '
                'Settings ▸ Sales ▸ LCS Catering, or choose the district '
                'below by hand.'
            )}

        try:
            response = requests.get(
                GEOCODE_URL,
                params={
                    'address': address,
                    'key': api_key,
                    # Hong Kong only — without this, "Central" and "North"
                    # match places all over the world.
                    'components': 'country:HK',
                    'language': 'en',
                },
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.Timeout:
            _logger.warning('Google geocoding timed out for %r', address)
            return {'ok': False, 'error': _(
                'Google Maps did not respond in time. Try again, or choose '
                'the district below by hand.'
            )}
        except Exception:
            _logger.exception('Google geocoding failed for %r', address)
            return {'ok': False, 'error': _(
                'Could not reach Google Maps. Choose the district below by '
                'hand.'
            )}

        status = payload.get('status')
        if status != 'OK' or not payload.get('results'):
            raw = STATUS_MESSAGES.get(status)
            message = _(raw) if raw else _(
                'Google Maps returned "%s".', status or 'no status')
            _logger.info('Google geocoding %s for %r', status, address)
            return {'ok': False, 'error': message}

        result = payload['results'][0]
        parts = []
        for component in result.get('address_components', []):
            parts.append(component.get('long_name') or '')
            parts.append(component.get('short_name') or '')
        parts.append(result.get('formatted_address') or '')
        location = (result.get('geometry') or {}).get('location') or {}
        return {
            'ok': True,
            'formatted': result.get('formatted_address') or address,
            'parts': [p for p in parts if p],
            'lat': location.get('lat'),
            'lng': location.get('lng'),
        }
