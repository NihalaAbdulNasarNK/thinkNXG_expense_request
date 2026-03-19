
import frappe

def execute(filters=None):
	if not filters:
		filters = {}

	filter_based_on = filters.get("filter_based_on")
	fiscal_year = filters.get("fiscal_year")
	company = filters.get("company")

	if filter_based_on == "Fiscal Year" and fiscal_year:
		fy = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
		if not fy:
			frappe.throw("Fiscal Year {0} not found".format(fiscal_year))
		from_date = str(fy.year_start_date)
		to_date = str(fy.year_end_date)
	else:
		from_date = filters.get("period_start_date")
		to_date = filters.get("period_end_date")

	accounts = frappe.get_all("Account", filters={"company": company, "account_type": ["in", ["Cash", "Bank"]]}, pluck="name")
	cash_accounts = tuple(accounts) if accounts else ("__dummy__",)

	# opening_balance = frappe.db.sql("SELECT SUM(debit - credit) FROM `tabGL Entry` WHERE company=%s AND posting_date < %s AND account IN %s AND is_cancelled=0", (company, from_date, cash_accounts))[0][0] or 0
	opening_balance = frappe.db.sql("""
		SELECT COALESCE(SUM(debit - credit), 0)
		FROM `tabGL Entry`
		WHERE company = %(company)s
		AND account IN %(accounts)s
		AND is_cancelled = 0
		AND (
			posting_date < %(from_date)s
			OR is_opening = 'Yes'
		)
	""", {
		"company": company,
		"from_date": from_date,
		"accounts": tuple(accounts)
	})[0][0]

	entries = frappe.db.sql("SELECT gle.name, gle.debit, gle.credit, gle.voucher_no, gle.voucher_type FROM `tabGL Entry` gle WHERE gle.company=%s AND gle.posting_date BETWEEN %s AND %s AND gle.account IN %s AND gle.is_cancelled=0 AND gle.is_opening='No'", (company, from_date, to_date, cash_accounts), as_dict=True)

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

	for row in entries:
		debit = row.debit or 0
		credit = row.credit or 0
		voucher_type = row.voucher_type or ""

		all_legs = frappe.db.sql("SELECT gle.party_type, acc.account_type, acc.root_type, acc.name as acc_name FROM `tabGL Entry` gle LEFT JOIN `tabAccount` acc ON gle.account = acc.name WHERE gle.voucher_no=%s AND gle.name != %s AND gle.account NOT IN %s", (row.voucher_no, row.name, cash_accounts), as_dict=True)

		if not all_legs:
			continue

		party_leg = next((l for l in all_legs if l.get("party_type")), None)
		primary = party_leg if party_leg else all_legs[0]

		other_party = primary.get("party_type") or ""
		other_type = primary.get("account_type") or ""
		other_root = primary.get("root_type") or ""
		other_name = primary.get("acc_name") or ""

		if debit > 0 and other_party == "Customer":
			customer_receipts += debit
		elif credit > 0 and other_party == "Supplier":
			supplier_payments += credit
		elif credit > 0 and voucher_type == "Purchase Invoice":
			supplier_payments += credit
		elif credit > 0 and other_root == "Liability" and "payroll" in other_name.lower():
			expense_payments += credit
		elif credit > 0 and other_root == "Expense":
			expense_payments += credit
		elif other_type == "Tax" or (other_root == "Liability" and "vat" in other_name.lower()):
			if credit > 0:
				tax_payments += credit
			elif debit > 0:
				other_receipts += debit
		elif other_type == "Fixed Asset":
			if debit > 0:
				asset_sale += debit
			elif credit > 0:
				asset_purchase += credit
		elif other_root == "Liability" and ("loan" in other_name.lower() or other_type == "Liability"):
			if debit > 0:
				loan_received += debit
			elif credit > 0:
				loan_repaid += credit
		elif other_root == "Equity":
			if debit > 0:
				capital_introduced += debit
		elif debit > 0:
			other_receipts += debit
		elif credit > 0:
			other_payments += credit

	net_operating = customer_receipts - supplier_payments - expense_payments - tax_payments
	net_investing = asset_sale - asset_purchase
	net_financing = loan_received - loan_repaid + capital_introduced
	net_movement = net_operating + net_investing + net_financing + other_receipts - other_payments
	closing_balance = opening_balance + net_movement

	columns = [
		{"label": "Particulars", "fieldname": "particulars", "fieldtype": "Data", "width": 500},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 200},
	]

	data = [
		{"particulars": "Opening Balance", "amount": opening_balance, "bold": 1},
		{"particulars": "", "amount": None},
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
		{"particulars": "", "amount": None},
		{"particulars": "Closing Balance", "amount": closing_balance, "bold": 1},
	]

	summary = [
		{"label": "Opening Balance", "value": opening_balance, "datatype": "Currency"},
		{"label": "Net Operating", "value": net_operating, "datatype": "Currency"},
		{"label": "Net Investing", "value": net_investing, "datatype": "Currency"},
		{"label": "Net Financing", "value": net_financing, "datatype": "Currency"},
		{"label": "Closing Balance", "value": closing_balance, "datatype": "Currency"},
	]

	return columns, data, None, None, summary