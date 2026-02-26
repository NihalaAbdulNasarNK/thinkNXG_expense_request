
import frappe
from frappe.utils import flt
from erpnext.accounts.report.financial_statements import get_period_list


def execute(filters=None):

    period_list = get_period_list(
        filters.from_fiscal_year,
        filters.to_fiscal_year,
        filters.period_start_date,
        filters.period_end_date,
        filters.filter_based_on,
        filters.periodicity,
        company=filters.company,
    )

    columns = get_columns()
    data, summary = get_data(filters, period_list)

    return columns, data, None, None, summary


# ---------------------------------------------------------
# Columns
# ---------------------------------------------------------

def get_columns():
    return [
        {
            "label": "Particulars",
            "fieldname": "particulars",
            "fieldtype": "Data",
            "width": 500,
        },
        {
            "label": "Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 200,
        },
    ]


# ---------------------------------------------------------
# Account Helpers
# ---------------------------------------------------------

def get_cash_bank_accounts(company):
    return tuple(frappe.get_all(
        "Account",
        filters={"company": company, "account_type": ["in", ["Cash", "Bank"]]},
        pluck="name",
    )) or ("",)


def get_asset_accounts(company):
    return tuple(frappe.get_all(
        "Account",
        filters={
            "company": company,
            "root_type": "Asset",
            "account_type": ["not in", ["Cash", "Bank"]],
        },
        pluck="name",
    )) or ("",)


def get_loan_accounts(company):
    return tuple(frappe.get_all(
        "Account",
        filters={"company": company, "account_type": "Loan"},
        pluck="name",
    )) or ("",)


# ---------------------------------------------------------
# Main Logic
# ---------------------------------------------------------
def get_data(filters, period_list):

    company = filters.company
    from_date = period_list[0]["from_date"]
    to_date = period_list[-1]["to_date"]

    cash_accounts = tuple(get_cash_bank_accounts(company)) or ("",)
    asset_accounts = tuple(get_asset_accounts(company)) or ("",)
    loan_accounts = tuple(get_loan_accounts(company)) or ("",)

    data = []

    # -----------------------------------------------------
    # OPENING BALANCE
    # -----------------------------------------------------

    # opening_balance = frappe.db.sql("""
    #     SELECT SUM(debit - credit)
    #     FROM `tabGL Entry`
    #     WHERE company=%s
    #     AND posting_date < %s
    #     AND account IN %s
    # """, (company, from_date, cash_accounts))[0][0] or 0

    # data.append({
    #     "particulars": "Opening Cash Balance",
    #     "amount": opening_balance,
    #     "indent": 0,
    #     "bold": 1,
    #     "parent": None
    # })

    # =====================================================
    # OPERATING ACTIVITIES
    # =====================================================

    # Customer Receipts
    customer_receipts = frappe.db.sql("""
        SELECT SUM(debit)
        FROM `tabGL Entry`
        WHERE company=%s
        AND posting_date BETWEEN %s AND %s
        AND account IN %s
        AND party_type='Customer'
        AND debit > 0
    """, (company, from_date, to_date, cash_accounts))[0][0] or 0

    # Supplier Payments
    supplier_payments = frappe.db.sql("""
        SELECT SUM(credit)
        FROM `tabGL Entry`
        WHERE company=%s
        AND posting_date BETWEEN %s AND %s
        AND account IN %s
        AND party_type='Supplier'
        AND credit > 0
    """, (company, from_date, to_date, cash_accounts))[0][0] or 0

    # Expense Payments
    expense_payments = frappe.db.sql("""
        SELECT SUM(gle.credit)
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.against = acc.name
        WHERE gle.company=%s
        AND gle.posting_date BETWEEN %s AND %s
        AND gle.account IN %s
        AND acc.root_type='Expense'
    """, (company, from_date, to_date, cash_accounts))[0][0] or 0

    # Tax Payments
    tax_payments = frappe.db.sql("""
        SELECT SUM(gle.credit)
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.against = acc.name
        WHERE gle.company=%s
        AND gle.posting_date BETWEEN %s AND %s
        AND gle.account IN %s
        AND acc.account_type='Tax'
    """, (company, from_date, to_date, cash_accounts))[0][0] or 0

    net_operating = (
        customer_receipts
        - supplier_payments
        - expense_payments
        - tax_payments
    )

    data.append({
        "particulars": "Operating Activities",
        "amount": net_operating,
        "indent": 0,
        "is_group": 1,
        "bold": 1,
        "parent": None
    })

    data.extend([
        {"particulars": "Customer Receipts", "amount": customer_receipts, "indent": 1, "parent": "Operating Activities"},
        {"particulars": "Supplier Payments", "amount": -supplier_payments, "indent": 1, "parent": "Operating Activities"},
        {"particulars": "Expense Payments", "amount": -expense_payments, "indent": 1, "parent": "Operating Activities"},
        {"particulars": "Tax Payments", "amount": -tax_payments, "indent": 1, "parent": "Operating Activities"},
    ])

    # =====================================================
    # INVESTING ACTIVITIES
    # =====================================================

    # Asset Purchase (cash going out)
    asset_purchase = frappe.db.sql("""
        SELECT SUM(credit)
        FROM `tabGL Entry`
        WHERE company=%s
        AND posting_date BETWEEN %s AND %s
        AND account IN %s
        AND against IN %s
        AND credit > 0
    """, (company, from_date, to_date, cash_accounts, asset_accounts))[0][0] or 0

    # Asset Sale (cash coming in)
    asset_sale = frappe.db.sql("""
        SELECT SUM(debit)
        FROM `tabGL Entry`
        WHERE company=%s
        AND posting_date BETWEEN %s AND %s
        AND account IN %s
        AND against IN %s
        AND debit > 0
    """, (company, from_date, to_date, cash_accounts, asset_accounts))[0][0] or 0

    net_investing = asset_sale - asset_purchase

    data.append({
        "particulars": "Investing Activities",
        "amount": net_investing,
        "indent": 0,
        "is_group": 1,
        "bold": 1,
        "parent": None
    })

    data.extend([
        {"particulars": "Asset Purchase", "amount": -asset_purchase, "indent": 1, "parent": "Investing Activities"},
        {"particulars": "Asset Sale", "amount": asset_sale, "indent": 1, "parent": "Investing Activities"},
    ])

    # =====================================================
    # FINANCING ACTIVITIES
    # =====================================================

    # Loan Received
    loan_received = frappe.db.sql("""
        SELECT SUM(debit)
        FROM `tabGL Entry`
        WHERE company=%s
        AND posting_date BETWEEN %s AND %s
        AND account IN %s
        AND against IN %s
        AND debit > 0
    """, (company, from_date, to_date, cash_accounts, loan_accounts))[0][0] or 0

    # Loan Repaid
    loan_repaid = frappe.db.sql("""
        SELECT SUM(credit)
        FROM `tabGL Entry`
        WHERE company=%s
        AND posting_date BETWEEN %s AND %s
        AND account IN %s
        AND against IN %s
        AND credit > 0
    """, (company, from_date, to_date, cash_accounts, loan_accounts))[0][0] or 0

    # Capital Introduced (Equity accounts)
    capital_introduced = frappe.db.sql("""
        SELECT SUM(debit)
        FROM `tabGL Entry` gle
        INNER JOIN `tabAccount` acc ON gle.against = acc.name
        WHERE gle.company=%s
        AND gle.posting_date BETWEEN %s AND %s
        AND gle.account IN %s
        AND acc.root_type='Equity'
        AND gle.debit > 0
    """, (company, from_date, to_date, cash_accounts))[0][0] or 0

    net_financing = loan_received - loan_repaid + capital_introduced

    data.append({
        "particulars": "Financing Activities",
        "amount": net_financing,
        "indent": 0,
        "is_group": 1,
        "bold": 1,
        "parent": None
    })

    data.extend([
        {"particulars": "Loan Received", "amount": loan_received, "indent": 1, "parent": "Financing Activities"},
        {"particulars": "Loan Repaid", "amount": -loan_repaid, "indent": 1, "parent": "Financing Activities"},
        {"particulars": "Capital Introduced", "amount": capital_introduced, "indent": 1, "parent": "Financing Activities"},
    ])

    # =====================================================
    # NET MOVEMENT
    # =====================================================

    net_movement = net_operating + net_investing + net_financing

    data.append({
        "particulars": "Net Increase / Decrease in Cash",
        "amount": net_movement,
        "indent": 0,
        "bold": 1,
        "parent": None
    })

    # closing_balance = opening_balance + net_movement

    # data.append({
    #     "particulars": "Closing Cash Balance",
    #     "amount": closing_balance,
    #     "indent": 0,
    #     "bold": 1,
    #     "parent": None
    # })
    # =====================================================
    # REPORT SUMMARY (Above Table)
    # =====================================================

    report_summary = [
        {
            "label": "Net Cash from Operations",
            "value": net_operating,
            "indicator": "Black",
            "datatype": "Currency",
        },
        {
            "label": "Net Cash from Investing",
            "value": net_investing,
            "indicator": "Black",
            "datatype": "Currency",
        },
        {
            "label": "Net Cash from Financing",
            "value": net_financing,
            "indicator": "Black",
            "datatype": "Currency",
        },
        {
            "label": "Net Change in Cash",
            "value": net_movement,
            "indicator": "Black",
            "datatype": "Currency",
        },
    ]

    return data, report_summary
