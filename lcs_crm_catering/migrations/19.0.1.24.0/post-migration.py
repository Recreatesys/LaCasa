"""Migrate legacy setup_type (Selection) to waiter_service (Boolean).

setup_type = 'with_waiter'                     → waiter_service = True
setup_type = 'equipment_only' | 'simple_setup' → waiter_service = False (K-prefix retired)
setup_type IS NULL                             → waiter_service = False (default)

After copy, drop the legacy setup_type column on all three tables.
"""


def migrate(cr, installed_version):
    for table in ('crm_lead', 'sale_order', 'account_move'):
        cr.execute(
            f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND column_name = 'setup_type'
            """,
            (table,),
        )
        if not cr.fetchone():
            continue
        cr.execute(
            f"UPDATE {table} SET waiter_service = (setup_type = 'with_waiter') "
            f"WHERE setup_type IS NOT NULL"
        )
        cr.execute(f"ALTER TABLE {table} DROP COLUMN setup_type")
