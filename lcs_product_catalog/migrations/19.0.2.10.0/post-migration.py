"""Clear the "Recommended Selection" text on every catering set."""


def migrate(cr, version):
    cr.execute("UPDATE lcs_catering_set SET recommendation = NULL")
