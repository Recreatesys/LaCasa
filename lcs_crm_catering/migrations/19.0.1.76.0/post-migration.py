"""C17 (client comment, slide 17): "Hardware" is now "Utensil & Equipment".

The tab, field labels and helper text are renamed in the views/models, but
Sales Orders created before this version carry a literal section line named
"Hardware" on order_line. _sync_hardware_lines() only rewrites that section
when an equipment row is touched, so historical orders would keep showing the
old wording on screen and on the printed quotation. Re-stamp them here.
"""

from odoo.addons.lcs_crm_catering.models.sale_order import HARDWARE_SECTION_NAME


def migrate(cr, version):
    cr.execute(
        """
        UPDATE sale_order_line
           SET name = %s
         WHERE is_hardware_line IS TRUE
           AND display_type = 'line_section'
           AND name = 'Hardware'
        """,
        (HARDWARE_SECTION_NAME,),
    )
