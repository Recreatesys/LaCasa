"""Clear any existing rows still holding the retired 'preferred_driver'
value on call_van. The selection key was removed in this version.
"""


def migrate(cr, version):
    for table in ('crm_lead', 'sale_order', 'account_move'):
        cr.execute(
            f"UPDATE {table} SET call_van = NULL "
            f"WHERE call_van = 'preferred_driver'"
        )
