"""LCS accounting setup — chart of accounts, payment methods, payment
terms, and analytic Location plan.

Additive migration (see accounting-department Excel, 2026-07):
  - 83 pre-existing 6-digit HK accounts are LEFT ALONE.
  - New 4-digit LCS chart added ALONGSIDE them.
  - Idempotent: matched by code+company; re-runs are no-ops.
  - Targets the main company (id=1); the school-branch companies get
    nothing here.
"""
from odoo import SUPERUSER_ID, api


# ── Chart of Accounts ─────────────────────────────────────────────
# Each row: (code, name, account_type)
# account.group parents are declared separately below.
ACCOUNTS = [
    # Fixed Assets
    ('1000', 'Fixed Assets',                       'asset_fixed'),
    ('1001', 'Renovation',                         'asset_fixed'),
    ('1002', 'Set up Fee',                         'asset_fixed'),
    # Cash in Bank
    ('1100', 'Cash in Bank',                       'asset_current'),
    ('1101', 'BEA Savings',                        'asset_cash'),
    ('1102', 'BEA Current',                        'asset_cash'),
    ('1103', 'CCBI Savings',                       'asset_cash'),
    ('1104', 'CCBI Current',                       'asset_cash'),
    ('1105', 'DBS Savings',                        'asset_cash'),
    ('1106', 'DBS Current',                        'asset_cash'),
    # Petty Cash
    ('1200', 'Petty Cash',                         'asset_current'),
    ('1201', '818 Petty Cash',                     'asset_cash'),
    ('1202', '710 Petty Cash',                     'asset_cash'),
    ('1203', 'LTF Petty Cash',                     'asset_cash'),
    ('1204', 'PK Petty Cash',                      'asset_cash'),
    ('1205', 'DBS Petty Cash',                     'asset_cash'),
    ('1206', 'TDC Petty Cash',                     'asset_cash'),
    # Account Receivable
    ('1300', 'Account Receivable',                 'asset_current'),
    ('1301', 'C/A Director',                       'asset_receivable'),
    ('1302', 'C/A Meerkat',                        'asset_receivable'),
    ('1303', 'Deposit',                            'asset_current'),
    ('1304', 'Account Receivable',                 'asset_receivable'),
    # Current Liabilities
    ('3000', 'Current Liabilities',                'liability_current'),
    ('3001', 'Loan Replacement 1',                 'liability_current'),
    ('3002', 'Loan Replacement 2',                 'liability_current'),
    ('3003', 'Account Payable',                    'liability_payable'),
    # Cost of Sales
    ('7100', 'Cost of Sales',                      'expense'),
    ('7101', 'Food',                               'expense'),
    ('7102', 'BV',                                 'expense'),
    ('7103', 'Packaging',                          'expense'),
    ('7104', 'Kitchenware',                        'expense'),
    # Operation Expenses
    ('7200', 'Operation Expenses',                 'expense'),
    ('7201', 'Entertainment',                      'expense'),
    ('7202', 'Cleansing',                          'expense'),
    ('7203', 'Repair',                             'expense'),
    ('7204', 'Rental Tools',                       'expense'),
    # Expenses
    ('7300', 'Expenses',                           'expense'),
    ('7301', 'Audit Fee',                          'expense'),
    ('7302', 'Bank charge',                        'expense'),
    ('7303', 'Computer Expenses',                  'expense'),
    ('7304', 'Delivery',                           'expense'),
    ('7305', 'Interest Paid',                      'expense'),
    ('7306', 'Insurance',                          'expense'),
    ('7307', 'Legal & Prof fee',                   'expense'),
    ('7308', 'License',                            'expense'),
    ('7309', 'Loan Interest',                      'expense'),
    ('7310', 'Medical',                            'expense'),
    ('7311', 'Office Equipment',                   'expense'),
    ('7312', 'Office Expenses',                    'expense'),
    ('7313', 'Printing and stationery',            'expense'),
    ('7314', 'Promotion',                          'expense'),
    ('7315', 'Refund',                             'expense'),
    ('7316', 'Rent & Rates',                       'expense'),
    ('7317', 'Rental',                             'expense'),
    ('7318', 'Staff Meal',                         'expense'),
    ('7319', 'Sundries',                           'expense'),
    ('7320', 'Telecom',                            'expense'),
    ('7321', 'Training',                           'expense'),
    ('7322', 'Travelling',                         'expense'),
    ('7323', 'Utilities',                          'expense'),
    # Payroll
    ('7400', 'Payroll',                            'expense'),
    ('7401', "Director's Remuneration",            'expense'),
    ('7402', 'Part time Staff',                    'expense'),
    ('7403', 'Salary',                             'expense'),
    ('7404', 'Outsource Service',                  'expense'),
    ('7405', 'Consultant Fee',                     'expense'),
    ('7406', "Employee's MPF",                     'expense'),
    ('7407', "Employer's MPF",                     'expense'),
    # Income
    ('4000', 'Income',                             'income'),
    ('4001', 'Catering Income',                    'income'),
    ('4002', 'Interest Income',                    'income_other'),
    ('4003', 'Service Income',                     'income'),
    ('4004', 'Utensil Rental',                     'income'),
    # Bucket
    ('9999', 'Unknown',                            'expense'),
]

# ── Account groups (Mother account headers) ───────────────────────
# Odoo 19: account.group provides hierarchy in reports. Ranges cover
# the child codes above.
GROUPS = [
    ('1000', '1099', 'Fixed Assets'),
    ('1100', '1199', 'Cash in Bank'),
    ('1200', '1299', 'Petty Cash'),
    ('1300', '1399', 'Account Receivable'),
    ('3000', '3999', 'Current Liabilities'),
    ('4000', '4999', 'Income'),
    ('7100', '7199', 'Cost of Sales'),
    ('7200', '7299', 'Operation Expenses'),
    ('7300', '7399', 'Expenses'),
    ('7400', '7499', 'Payroll'),
]

# ── Payment Terms ────────────────────────────────────────────────
PAYMENT_TERMS = [
    'Cash on delivery',
    'Cheque on delivery',
    'FPS before/after delivery',
    'Weekly',
    '15 Days',
    'Monthly',
]

# ── Payment Methods ──────────────────────────────────────────────
# Outbound = pay vendors; inbound = receive from customers.
OUTBOUND_METHODS = ['Cheque', 'Petty Cash', 'FPS', 'Autopay']
INBOUND_METHODS = ['Cash', 'Cheque', 'Octopus', 'Credit Card', 'Stripe', 'Qfpay']

# ── Analytic Locations ───────────────────────────────────────────
ANALYTIC_PLAN_NAME = 'Location'
LOCATIONS = [
    'To Kwa Wan - 818',
    'To Kwa Wan - 710',
    'TDC',
    'Lam Tai Fai',
    'Pooi Kei',
    'DBS',
]

MAIN_COMPANY_ID = 1  # La Casa Management Company Limited


def _ensure_group(env, code_start, code_end, name, company):
    """Idempotent account.group upsert."""
    grp = env['account.group'].search([
        ('code_prefix_start', '=', code_start),
        ('code_prefix_end', '=', code_end),
        ('company_id', '=', company.id),
    ], limit=1)
    if not grp:
        env['account.group'].create({
            'name': name,
            'code_prefix_start': code_start,
            'code_prefix_end': code_end,
            'company_id': company.id,
        })


def _ensure_account(env, code, name, acc_type, company):
    """Idempotent account.account upsert. Matched by code + company via
    the code_store jsonb key on this company id."""
    env.cr.execute(
        """
        SELECT id FROM account_account
         WHERE code_store->>%s = %s
         LIMIT 1
        """,
        (str(company.id), code),
    )
    row = env.cr.fetchone()
    if row:
        return env['account.account'].browse(row[0])
    account = env['account.account'].with_company(company).create({
        'code': code,
        'name': name,
        'account_type': acc_type,
    })
    return account


def _ensure_payment_term(env, name, company):
    term = env['account.payment.term'].search([
        ('name', '=', name),
        ('company_id', '=', company.id),
    ], limit=1)
    if term:
        return term
    return env['account.payment.term'].create({
        'name': name,
        'company_id': company.id,
        'line_ids': [(0, 0, {
            'value': 'percent',
            'value_amount': 100.0,
            'nb_days': 0,
        })],
    })


def _ensure_analytic_plan(env, name, company):
    plan = env['account.analytic.plan'].search([
        ('name', '=', name),
    ], limit=1)
    if plan:
        return plan
    return env['account.analytic.plan'].create({
        'name': name,
    })


def _ensure_analytic_account(env, name, plan, company):
    acc = env['account.analytic.account'].search([
        ('name', '=', name),
        ('plan_id', '=', plan.id),
    ], limit=1)
    if acc:
        return acc
    return env['account.analytic.account'].create({
        'name': name,
        'plan_id': plan.id,
        'company_id': company.id,
    })


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    company = env['res.company'].browse(MAIN_COMPANY_ID)
    if not company.exists():
        return

    # 1. Account groups (hierarchy in Trial Balance and Chart of Accounts).
    for code_start, code_end, name in GROUPS:
        _ensure_group(env, code_start, code_end, name, company)

    # 2. Accounts.
    for code, name, acc_type in ACCOUNTS:
        _ensure_account(env, code, name, acc_type, company)

    # 3. Payment terms.
    for name in PAYMENT_TERMS:
        _ensure_payment_term(env, name, company)

    # 4. Analytic Location plan + accounts.
    plan = _ensure_analytic_plan(env, ANALYTIC_PLAN_NAME, company)
    for loc in LOCATIONS:
        _ensure_analytic_account(env, loc, plan, company)

    # 5. Payment methods — surface Cheque/FPS/Manual etc. on the main
    # bank journal so users can pick them. We don't create new payment
    # method records (they're base data); we just add lines to journals.
    # This is best-effort: journals are already created and configured.
    manual_in = env.ref('account.account_payment_method_manual_in', raise_if_not_found=False)
    manual_out = env.ref('account.account_payment_method_manual_out', raise_if_not_found=False)
    # Attach a labelled "manual" line for each requested name so the
    # dropdown shows Cheque / Petty Cash / FPS / Autopay etc. even
    # though the underlying method is "manual".
    bank_journals = env['account.journal'].search([
        ('type', 'in', ('bank', 'cash')),
        ('company_id', '=', company.id),
    ])
    if bank_journals and manual_in and manual_out:
        for jr in bank_journals:
            existing_in = set(jr.inbound_payment_method_line_ids.mapped('name'))
            for label in INBOUND_METHODS:
                if label not in existing_in:
                    env['account.payment.method.line'].create({
                        'name': label,
                        'payment_method_id': manual_in.id,
                        'journal_id': jr.id,
                    })
            existing_out = set(jr.outbound_payment_method_line_ids.mapped('name'))
            for label in OUTBOUND_METHODS:
                if label not in existing_out:
                    env['account.payment.method.line'].create({
                        'name': label,
                        'payment_method_id': manual_out.id,
                        'journal_id': jr.id,
                    })
