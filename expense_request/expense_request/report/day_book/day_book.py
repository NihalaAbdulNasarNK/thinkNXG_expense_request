# Copyright (c) 2025, Bantoo and contributors
# For license information, please see license.txt


import frappe
from frappe.utils import flt

def execute(filters=None):
    accounts = get_accounts(filters)
    columns = get_columns(accounts)
    data = get_data(filters, accounts)
    return columns, data


def get_accounts(filters):
    """Return default or selected accounts for the selected company."""
    company = filters.get("company")
    
    if filters.get("accounts"):
        # MultiSelectList comes as JSON string → parse it
        return frappe.parse_json(filters.get("accounts"))

    accounts = []

    # Get all Cash accounts for the company
    cash_accounts = frappe.get_all(
        "Account",
        filters={"account_type": "Cash", "company": company},
        pluck="name"
    )
    accounts.extend(cash_accounts)
    # Add all Bank accounts for the company
    bank_accounts = frappe.get_all(
        "Account",
        filters={"account_type": "Bank", "company": company},
        pluck="name"
    )
    accounts.extend(bank_accounts)

    # Ensure unique list
    return list(set(accounts))



def get_columns(accounts):
    columns = [
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": "Account", "fieldname": "account", "fieldtype": "Data", "width": 200},
        {"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": "Credit", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": "Balance", "fieldname": "balance", "fieldtype": "Currency", "width": 120},
    ]
    return columns


def get_data(filters, accounts):
    conditions = ""
    values = {}

    if filters.get("from_date") and filters.get("to_date"):
        conditions += " and gl.posting_date between %(from_date)s and %(to_date)s"
        values.update({
            "from_date": filters["from_date"],
            "to_date": filters["to_date"],
        })

    if filters.get("company"):
        conditions += " and gl.company = %(company)s"
        values.update({"company": filters["company"]})

    data = []

    # Get posting dates
    dates = frappe.db.sql(f"""
        select distinct gl.posting_date
        from `tabGL Entry` gl
        where gl.docstatus = 1 {conditions}
        order by gl.posting_date
    """, values, as_dict=1)

    for d in dates:
        posting_date = d.posting_date
        # For each selected account
        for acc in accounts:
            debit, credit = frappe.db.sql(f"""
                select sum(gl.debit), sum(gl.credit)
                from `tabGL Entry` gl
                where gl.posting_date=%s and gl.account=%s and gl.docstatus=1
                {(" and gl.company=%s" if filters.get("company") else "")}
            """, (posting_date, acc, filters.get("company")) if filters.get("company") else (posting_date, acc))[0]

            debit = flt(debit)
            credit = flt(credit)
            balance = debit - credit

            # Skip if both debit and credit are zero
            if debit == 0 and credit == 0:
                continue

            data.append({
                "posting_date": posting_date,
                "account": acc,
                "debit": debit,
                "credit": credit,
                "balance": balance,
            })

        # Only when no account filter is applied
        if not filters.get("accounts"):
            sales = frappe.db.sql("""
                select sum(base_grand_total) from `tabSales Invoice`
                where posting_date=%s and docstatus=1 and is_return=0
            """, posting_date)[0][0] or 0

            purchase = frappe.db.sql("""
                select sum(base_grand_total) from `tabPurchase Invoice`
                where posting_date=%s and docstatus=1 and is_return=0
            """, posting_date)[0][0] or 0

            sales_return = frappe.db.sql("""
                select sum(base_grand_total) from `tabSales Invoice`
                where posting_date=%s and docstatus=1 and is_return=1
            """, posting_date)[0][0] or 0

            purchase_return = frappe.db.sql("""
                select sum(base_grand_total) from `tabPurchase Invoice`
                where posting_date=%s and docstatus=1 and is_return=1
            """, posting_date)[0][0] or 0

            # Append summary rows
            data.append({
                "posting_date": posting_date,
                "account": "Sales After Return",
                "debit": -sales_return,
                "credit": sales,
                "balance": flt(sales) + flt(sales_return),
            })
            data.append({
                "posting_date": posting_date,
                "account": "Purchase After Return",
                "debit": -purchase_return,
                "credit": purchase,
                "balance": flt(purchase) + flt(purchase_return),
            })

    return data
