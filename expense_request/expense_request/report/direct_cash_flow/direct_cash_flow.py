
import frappe
from erpnext.accounts.report.financial_statements import get_period_list

def execute(filters=None):
    if not filters:
        filters = {}

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
    data, summary = get_data(filters, period_list, filters.company)

    return columns, data, None, None, summary

# ---------------------------------------------------------
# Columns
# ---------------------------------------------------------
def get_columns():
    return [
        {"label": "Particulars", "fieldname": "particulars", "fieldtype": "Data", "width": 500},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 200},
    ]

# ---------------------------------------------------------
# Helper: Get Cash/Bank Accounts
# ---------------------------------------------------------
def get_cash_bank_accounts(company):
    accounts = frappe.get_all(
        "Account",
        filters={"company": company, "account_type": ["in", ["Cash", "Bank"]]},
        pluck="name",
    )
    return tuple(accounts) if accounts else ("",)

# ---------------------------------------------------------
# Main Logic
# ---------------------------------------------------------
def get_data(filters, period_list, company):
    from_date = period_list[0]["from_date"]
    to_date = period_list[-1]["to_date"]
    cash_accounts = get_cash_bank_accounts(company)

    # --- Opening Cash Balance ---
    opening_balance = frappe.db.sql("""
        SELECT SUM(debit - credit)
        FROM `tabGL Entry`
        WHERE company=%s
        AND posting_date < %s
        AND account IN %s
    """, (company, from_date, cash_accounts))[0][0] or 0

    # --- Fetch all GL entries for period ---
    entries = frappe.db.sql("""
        SELECT gle.name as gl_entry,
               gle.debit,
               gle.credit,
               gle.account,
               gle.voucher_type,
               gle.voucher_no,
               gle.is_opening,
               acc.account_type,
               acc.root_type
        FROM `tabGL Entry` gle
        LEFT JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.company=%s
        AND gle.posting_date BETWEEN %s AND %s
        AND gle.account IN %s
    """, (company, from_date, to_date, cash_accounts), as_dict=True)

    # --- Initialize totals ---
    customer_receipts = 0
    supplier_payments = 0
    expense_payments = 0
    tax_payments = 0
    asset_purchase = 0
    asset_sale = 0
    loan_received = 0
    loan_repaid = 0
    capital_introduced = 0

    # --- Process each cash GL row ---
    for row in entries:
        if row.is_opening == "Yes":
            continue  # ignore opening entries inside period

        debit = row.debit or 0
        credit = row.credit or 0
        voucher_no = row.voucher_no

        # Fetch the other accounts for this voucher
        other_entries = frappe.db.sql("""
            SELECT acc.account_type, acc.root_type
            FROM `tabGL Entry` gle
            LEFT JOIN `tabAccount` acc ON gle.account = acc.name
            WHERE gle.voucher_no=%s
            AND gle.name != %s
        """, (voucher_no, row.gl_entry), as_dict=True)

        for other in other_entries:
            other_type = other.get("account_type")
            other_root = other.get("root_type")

            # ---------------- Operating ----------------
            if debit > 0 and other_type == "Receivable":
                customer_receipts += debit

            elif credit > 0 and other_type == "Payable":
                supplier_payments += credit

            elif credit > 0 and other_root == "Expense":
                expense_payments += credit

            elif credit > 0 and other_type == "Tax":
                tax_payments += credit

            # ---------------- Investing ----------------
            elif other_root == "Asset" and other_type == "Fixed Assets":
                if row.account in cash_accounts:
                    if debit > 0:
                        asset_sale += debit
                    elif credit > 0:
                        asset_purchase += credit

            # ---------------- Financing ----------------
            elif credit > 0 and other_type == "Loan":
                loan_repaid += credit
            elif debit > 0 and other_type == "Loan":
                loan_received += debit
            elif debit > 0 and other_root == "Equity":
                capital_introduced += debit

    # --- Calculate totals ---
    net_operating = customer_receipts - supplier_payments - expense_payments - tax_payments
    net_investing = asset_sale - asset_purchase
    net_financing = loan_received - loan_repaid + capital_introduced
    net_movement = net_operating + net_investing + net_financing
    closing_balance = opening_balance + net_movement

    # --- Build report ---
    data = [
        {"particulars": "Opening Balance", "amount": opening_balance, "bold": 1},

        {"particulars": "Operating Activities", "amount": net_operating, "bold": 1},
        {"particulars": "Customer Receipts", "amount": customer_receipts, "indent": 1},
        {"particulars": "Supplier Payments", "amount": -supplier_payments, "indent": 1},
        {"particulars": "Expense Payments", "amount": -expense_payments, "indent": 1},
        {"particulars": "Tax Payments", "amount": -tax_payments, "indent": 1},

        {"particulars": "Investing Activities", "amount": net_investing, "bold": 1},
        {"particulars": "Asset Purchase", "amount": -asset_purchase, "indent": 1},
        {"particulars": "Asset Sale", "amount": asset_sale, "indent": 1},

        {"particulars": "Financing Activities", "amount": net_financing, "bold": 1},
        {"particulars": "Loan Received", "amount": loan_received, "indent": 1},
        {"particulars": "Loan Repaid", "amount": -loan_repaid, "indent": 1},
        {"particulars": "Capital Introduced", "amount": capital_introduced, "indent": 1},

        {"particulars": "Net Increase / Decrease in Cash", "amount": net_movement, "bold": 1},
        {"particulars": "Closing Balance", "amount": closing_balance, "bold": 1},
    ]

    report_summary = [
        {"label": "Opening Balance", "value": opening_balance, "datatype": "Currency"},
        {"label": "Net Operating", "value": net_operating, "datatype": "Currency"},
        {"label": "Net Investing", "value": net_investing, "datatype": "Currency"},
        {"label": "Net Financing", "value": net_financing, "datatype": "Currency"},
        {"label": "Closing Balance", "value": closing_balance, "datatype": "Currency"},
    ]

    return data, report_summary