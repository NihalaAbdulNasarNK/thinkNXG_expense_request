# Copyright (c) 2025, Bantoo and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = [
        {"label": "Fiscal Year", "fieldname": "fiscal_year", "fieldtype": "Data", "width": 80},
        {"label": "Company", "fieldname": "company", "fieldtype": "Data", "width": 220},
        {"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": "Account", "fieldname": "account", "fieldtype": "Data", "width": 380},
        {"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 140},
        {"label": "Credit", "fieldname": "credit", "fieldtype": "Currency", "width": 140},
        # {"label": "Finance Book", "fieldname": "finance_book", "fieldtype": "Link", "options": "Finance Book", "width": 140},
    ]

    data = get_data(filters)
    return columns, data


def get_data(filters):
    conditions = ["is_cancelled=0"]

    if filters.get("fiscal_year"):
        conditions.append(f"fiscal_year='{filters.fiscal_year}'")
    if filters.get("company"):
        conditions.append(f"company='{filters.company}'")
    if filters.get("from_date"):
        conditions.append(f"posting_date >= '{filters.from_date}'")
    if filters.get("to_date"):
        conditions.append(f"posting_date <= '{filters.to_date}'")
    if filters.get("accounts"):
        accounts_list = [f"'{a.strip()}'" for a in filters.accounts]
        conditions.append(f"account IN ({','.join(accounts_list)})")
	

	
    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT 
            fiscal_year,
            company,
            posting_date,
            account,
            SUM(debit) as debit,
            SUM(credit) as credit,
            finance_book
        FROM `tabGL Entry`
        WHERE {where_clause}
        GROUP BY fiscal_year, company, posting_date, account, finance_book
        ORDER BY fiscal_year, company, posting_date, account
    """

    return frappe.db.sql(query, as_dict=True)
