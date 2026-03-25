
import frappe
from erpnext.accounts.report.financial_statements import get_period_list


def execute(filters=None):
    if not filters:
        filters = {}

    company = filters.get("company")
    filter_based_on = filters.get("filter_based_on")

    # -------------------------
    # DATE HANDLING
    # -------------------------
    if filter_based_on == "Fiscal Year":
        from_fy = filters.get("from_fiscal_year")
        to_fy = filters.get("to_fiscal_year")

        if not from_fy or not to_fy:
            frappe.throw("Please select From and To Fiscal Year")

        fy_from = frappe.db.get_value("Fiscal Year", from_fy, "year_start_date")
        fy_to = frappe.db.get_value("Fiscal Year", to_fy, "year_end_date")

        if not fy_from or not fy_to:
            frappe.throw("Invalid Fiscal Year")

        filters["period_start_date"] = str(fy_from)
        filters["period_end_date"] = str(fy_to)

    else:
        if not filters.get("period_start_date") or not filters.get("period_end_date"):
            frappe.throw("Please select From Date and To Date")

    # -------------------------
    # PERIOD LIST
    # -------------------------
    period_list = get_period_list(
        filters.get("from_fiscal_year"),
        filters.get("to_fiscal_year"),
        filters.get("period_start_date"),
        filters.get("period_end_date"),
        filter_based_on,
        filters.get("periodicity"),
        company=company,
    )

    # -------------------------
    # CASH/BANK ACCOUNTS
    # -------------------------
    accounts = frappe.get_all(
        "Account",
        filters={
            "company": company,
            "account_type": ["in", ["Cash", "Bank"]]
        },
        pluck="name"
    )

    if not accounts:
        return [], []

    accounts_tuple = tuple(accounts)

    # -------------------------
    # BASE PARAMS
    # -------------------------
    base_params = {
        "company": company,
        "accounts": accounts_tuple
    }

    extra_conditions = ""

    if filters.get("finance_book"):
        extra_conditions += " AND gle.finance_book = %(finance_book)s"
        base_params["finance_book"] = filters.get("finance_book")

    if filters.get("cost_center"):
        extra_conditions += " AND gle.cost_center = %(cost_center)s"
        base_params["cost_center"] = filters.get("cost_center")

    if filters.get("project"):
        extra_conditions += " AND gle.project = %(project)s"
        base_params["project"] = filters.get("project")

    if not filters.get("include_default_book_entries"):
        extra_conditions += " AND (gle.finance_book IS NULL OR gle.finance_book = '')"

    # -------------------------
    # VARIABLES
    # -------------------------
    opening_balance = 0
    customer_receipts = 0
    supplier_payments = 0
    expense_payments = 0
    tax_payments = 0
    asset_purchase = 0
    asset_sale = 0
    loan_received = 0
    loan_repaid = 0
    capital_introduced = 0
    other_receipts = 0
    other_payments = 0

    closing_per_period = {}
    running_balance = 0

    # -------------------------
    # LOOP THROUGH PERIODS
    # -------------------------
    for p in period_list:
        params = base_params.copy()
        params.update({
            "from_date": p["from_date"],
            "to_date": p["to_date"]
        })

        # OPENING
        if p == period_list[-1]:
            opening_balance = frappe.db.sql(f"""
                SELECT COALESCE(SUM(debit - credit), 0)
                FROM `tabGL Entry` gle
                WHERE gle.company = %(company)s
                AND gle.account IN %(accounts)s
                AND gle.is_cancelled = 0
                AND (
                    gle.posting_date < %(from_date)s
                    OR gle.is_opening = 'Yes'
                )
                {extra_conditions}
            """, params)[0][0]

            running_balance = opening_balance

        # ENTRIES
        entries = frappe.db.sql(f"""
            SELECT name, debit, credit, voucher_no
            FROM `tabGL Entry` gle
            WHERE gle.company = %(company)s
            AND gle.account IN %(accounts)s
            AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
            AND gle.is_cancelled = 0
            AND gle.is_opening = 'No'
            {extra_conditions}
        """, params, as_dict=True)

        period_net = 0

        # PROCESS
        for row in entries:
            debit = row.debit or 0
            credit = row.credit or 0

            # Period movement tracking
            if debit > 0:
                period_net += debit
            elif credit > 0:
                period_net -= credit

            other_legs = frappe.db.sql("""
                SELECT acc.account_type, acc.root_type, acc.name
                FROM `tabGL Entry` gle
                LEFT JOIN `tabAccount` acc ON gle.account = acc.name
                WHERE gle.voucher_no = %s
                AND gle.name != %s
                AND gle.account NOT IN %s
            """, (row.voucher_no, row.name, accounts_tuple), as_dict=True)

            if not other_legs:
                continue

            acc = other_legs[0]
            acc_type = acc.get("account_type") or ""
            root_type = acc.get("root_type") or ""
            acc_name = acc.get("name") or ""

            if debit > 0 and root_type == "Income":
                customer_receipts += debit
            elif credit > 0 and root_type == "Expense":
                expense_payments += credit
            elif credit > 0 and root_type == "Liability":
                supplier_payments += credit
            elif acc_type == "Tax":
                if credit > 0:
                    tax_payments += credit
                else:
                    other_receipts += debit
            elif acc_type == "Fixed Asset":
                if credit > 0:
                    asset_purchase += credit
                else:
                    asset_sale += debit
            elif root_type == "Equity":
                capital_introduced += debit
            elif root_type == "Liability" and "loan" in acc_name.lower():
                if debit > 0:
                    loan_received += debit
                else:
                    loan_repaid += credit
            elif debit > 0:
                other_receipts += debit
            elif credit > 0:
                other_payments += credit

        # Update running closing
        running_balance += period_net
        closing_per_period[p["key"]] = running_balance

    # -------------------------
    # FINAL CALCULATIONS
    # -------------------------
    net_operating = customer_receipts - supplier_payments - expense_payments - tax_payments
    net_investing = asset_sale - asset_purchase
    net_financing = loan_received - loan_repaid + capital_introduced

    net_movement = net_operating + net_investing + net_financing + other_receipts - other_payments

    # FINAL CLOSING = LAST PERIOD VALUE
    last_key = period_list[-1]["key"]
    closing_balance = closing_per_period.get(last_key, opening_balance)

    # -------------------------
    # COLUMNS
    # -------------------------
    columns = [
        {"label": "Particulars", "fieldname": "particulars", "fieldtype": "Data", "width": 500},
        {"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 200},
    ]

    # -------------------------
    # DATA
    # -------------------------
    data = []

    if filters.get("show_opening_and_closing_balance"):
        data.append({"particulars": "Opening Balance", "amount": opening_balance, "bold": 1})
        data.append({"particulars": "", "amount": None})

    data.extend([
        {"particulars": "Operating Activities", "amount": net_operating, "bold": 1},
        {"particulars": "Customer Receipts", "amount": customer_receipts, "indent": 1},
        {"particulars": "Supplier Payments", "amount": -supplier_payments, "indent": 1},
        {"particulars": "Expense Payments", "amount": -expense_payments, "indent": 1},
        {"particulars": "Tax Payments", "amount": -tax_payments, "indent": 1},

        {"particulars": "", "amount": None},
        {"particulars": "Investing Activities", "amount": net_investing, "bold": 1},
        {"particulars": "Asset Purchase", "amount": -asset_purchase, "indent": 1},
        {"particulars": "Asset Sale", "amount": asset_sale, "indent": 1},

        {"particulars": "", "amount": None},
        {"particulars": "Financing Activities", "amount": net_financing, "bold": 1},
        {"particulars": "Loan Received", "amount": loan_received, "indent": 1},
        {"particulars": "Loan Repaid", "amount": -loan_repaid, "indent": 1},
        {"particulars": "Capital Introduced", "amount": capital_introduced, "indent": 1},

        {"particulars": "", "amount": None},
        {"particulars": "Net Increase / Decrease in Cash", "amount": net_movement, "bold": 1},
    ])

    if filters.get("show_opening_and_closing_balance"):
        data.append({"particulars": "", "amount": None})
        data.append({"particulars": "Closing Balance", "amount": closing_balance, "bold": 1})

    # -------------------------
    # SUMMARY
    # -------------------------
    summary = [
        {"label": "Opening", "value": opening_balance, "datatype": "Currency"},
        {"label": "Operating", "value": net_operating, "datatype": "Currency"},
        {"label": "Investing", "value": net_investing, "datatype": "Currency"},
        {"label": "Financing", "value": net_financing, "datatype": "Currency"},
        {"label": "Closing", "value": closing_balance, "datatype": "Currency"},
    ]

    return columns, data, None, None, summary