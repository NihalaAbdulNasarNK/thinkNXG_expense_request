import frappe


def execute(filters=None):
	if not filters:
		filters = {}

	filter_based_on = filters.get("filter_based_on")
	fiscal_year = filters.get("fiscal_year")
	company = filters.get("company")

	if filter_based_on == "Fiscal Year" and fiscal_year:
		fy = frappe.db.get_value("Fiscal Year", fiscal_year, ["year_start_date", "year_end_date"], as_dict=True)
		from_date = str(fy.year_start_date)
		to_date = str(fy.year_end_date)
	else:
		from_date = filters.get("period_start_date")
		to_date = filters.get("period_end_date")

	accounts = frappe.get_all("Account", filters={"company": company, "account_type": ["in", ["Cash", "Bank"]]}, pluck="name")
	cash_accounts = tuple(accounts) if accounts else ("__dummy__",)

	cash_only = tuple(frappe.get_all("Account", filters={"company": company, "account_type": "Cash"}, pluck="name")) or ("__dummy__",)
	bank_only = tuple(frappe.get_all("Account", filters={"company": company, "account_type": "Bank"}, pluck="name")) or ("__dummy__",)

	# Opening Balances
	# opening_cash = frappe.db.sql("SELECT SUM(debit - credit) FROM `tabGL Entry` WHERE company=%s AND posting_date < %s AND account IN %s AND is_cancelled=0", (company, from_date, cash_only))[0][0] or 0
	# opening_bank = frappe.db.sql("SELECT SUM(debit - credit) FROM `tabGL Entry` WHERE company=%s AND posting_date < %s AND account IN %s AND is_cancelled=0", (company, from_date, bank_only))[0][0] or 0
	opening_cash = frappe.db.sql("""
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
		"accounts": cash_only
	})[0][0]
	opening_bank = frappe.db.sql("""
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
		"accounts": bank_only
	})[0][0]
	opening_balance = opening_cash + opening_bank

	# Totals
	cash_inflow = frappe.db.sql("SELECT SUM(debit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN %s AND debit > 0 AND is_cancelled=0 AND is_opening='No'", (company, from_date, to_date, cash_only))[0][0] or 0
	cash_outflow = frappe.db.sql("SELECT SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN %s AND credit > 0 AND is_cancelled=0 AND is_opening='No'", (company, from_date, to_date, cash_only))[0][0] or 0
	bank_inflow = frappe.db.sql("SELECT SUM(debit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN %s AND debit > 0 AND is_cancelled=0 AND is_opening='No'", (company, from_date, to_date, bank_only))[0][0] or 0
	bank_outflow = frappe.db.sql("SELECT SUM(credit) FROM `tabGL Entry` WHERE company=%s AND posting_date BETWEEN %s AND %s AND account IN %s AND credit > 0 AND is_cancelled=0 AND is_opening='No'", (company, from_date, to_date, bank_only))[0][0] or 0

	# Item wise breakdown by opposite account
	cash_inflow_items = frappe.db.sql("""
		SELECT opp_acc.name as acc_name, SUM(gle.debit) as total
		FROM `tabGL Entry` gle
		LEFT JOIN `tabAccount` acc ON gle.account = acc.name
		JOIN `tabGL Entry` opp ON opp.voucher_no = gle.voucher_no AND opp.name != gle.name AND opp.account NOT IN %s
		LEFT JOIN `tabAccount` opp_acc ON opp.account = opp_acc.name
		WHERE gle.company=%s AND gle.posting_date BETWEEN %s AND %s
		AND gle.account IN %s AND gle.debit > 0 AND gle.is_cancelled=0 AND gle.is_opening='No'
		GROUP BY opp_acc.name
		ORDER BY total DESC
	""", (cash_accounts, company, from_date, to_date, cash_only), as_dict=True)

	cash_outflow_items = frappe.db.sql("""
		SELECT opp_acc.name as acc_name, SUM(gle.credit) as total
		FROM `tabGL Entry` gle
		LEFT JOIN `tabAccount` acc ON gle.account = acc.name
		JOIN `tabGL Entry` opp ON opp.voucher_no = gle.voucher_no AND opp.name != gle.name AND opp.account NOT IN %s
		LEFT JOIN `tabAccount` opp_acc ON opp.account = opp_acc.name
		WHERE gle.company=%s AND gle.posting_date BETWEEN %s AND %s
		AND gle.account IN %s AND gle.credit > 0 AND gle.is_cancelled=0 AND gle.is_opening='No'
		GROUP BY opp_acc.name
		ORDER BY total DESC
	""", (cash_accounts, company, from_date, to_date, cash_only), as_dict=True)

	bank_inflow_items = frappe.db.sql("""
		SELECT opp_acc.name as acc_name, SUM(gle.debit) as total
		FROM `tabGL Entry` gle
		LEFT JOIN `tabAccount` acc ON gle.account = acc.name
		JOIN `tabGL Entry` opp ON opp.voucher_no = gle.voucher_no AND opp.name != gle.name AND opp.account NOT IN %s
		LEFT JOIN `tabAccount` opp_acc ON opp.account = opp_acc.name
		WHERE gle.company=%s AND gle.posting_date BETWEEN %s AND %s
		AND gle.account IN %s AND gle.debit > 0 AND gle.is_cancelled=0 AND gle.is_opening='No'
		GROUP BY opp_acc.name
		ORDER BY total DESC
	""", (cash_accounts, company, from_date, to_date, bank_only), as_dict=True)

	bank_outflow_items = frappe.db.sql("""
		SELECT opp_acc.name as acc_name, SUM(gle.credit) as total
		FROM `tabGL Entry` gle
		LEFT JOIN `tabAccount` acc ON gle.account = acc.name
		JOIN `tabGL Entry` opp ON opp.voucher_no = gle.voucher_no AND opp.name != gle.name AND opp.account NOT IN %s
		LEFT JOIN `tabAccount` opp_acc ON opp.account = opp_acc.name
		WHERE gle.company=%s AND gle.posting_date BETWEEN %s AND %s
		AND gle.account IN %s AND gle.credit > 0 AND gle.is_cancelled=0 AND gle.is_opening='No'
		GROUP BY opp_acc.name
		ORDER BY total DESC
	""", (cash_accounts, company, from_date, to_date, bank_only), as_dict=True)

	closing_cash = opening_cash + cash_inflow - cash_outflow
	closing_bank = opening_bank + bank_inflow - bank_outflow
	closing_balance = closing_cash + closing_bank
	net_movement = (cash_inflow + bank_inflow) - (cash_outflow + bank_outflow)

	columns = [
		{"label": "Particulars", "fieldname": "particulars", "fieldtype": "Data", "width": 500},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 200},
	]

	data = [
		{"particulars": "Opening Balance", "amount": opening_balance, "bold": 1},
		{"particulars": "Cash Opening Balance", "amount": opening_cash, "indent": 1},
		{"particulars": "Bank Opening Balance", "amount": opening_bank, "indent": 1},
		{"particulars": "", "amount": None},

		{"particulars": "Cash Inflow", "amount": cash_inflow, "bold": 1},
	] + [
		{"particulars": r.acc_name, "amount": r.total, "indent": 1}
		for r in cash_inflow_items if r.total
	] + [
		{"particulars": "", "amount": None},

		{"particulars": "Cash Outflow", "amount": -cash_outflow, "bold": 1},
	] + [
		{"particulars": r.acc_name, "amount": -r.total, "indent": 1}
		for r in cash_outflow_items if r.total
	] + [
		{"particulars": "", "amount": None},

		{"particulars": "Bank Inflow", "amount": bank_inflow, "bold": 1},
	] + [
		{"particulars": r.acc_name, "amount": r.total, "indent": 1}
		for r in bank_inflow_items if r.total
	] + [
		{"particulars": "", "amount": None},

		{"particulars": "Bank Outflow", "amount": -bank_outflow, "bold": 1},
	] + [
		{"particulars": r.acc_name, "amount": -r.total, "indent": 1}
		for r in bank_outflow_items if r.total
	] + [
		{"particulars": "", "amount": None},

		{"particulars": "Net Cash Movement", "amount": cash_inflow - cash_outflow, "bold": 1},
		{"particulars": "Net Bank Movement", "amount": bank_inflow - bank_outflow, "bold": 1},
		{"particulars": "Net Total Movement", "amount": net_movement, "bold": 1},
		{"particulars": "", "amount": None},

		{"particulars": "Closing Balance", "amount": closing_balance, "bold": 1},
		{"particulars": "Cash Closing Balance", "amount": closing_cash, "indent": 1},
		{"particulars": "Bank Closing Balance", "amount": closing_bank, "indent": 1},
	]

	summary = [
		{"label": "Opening Balance", "value": opening_balance, "datatype": "Currency"},
		{"label": "Cash Inflow", "value": cash_inflow, "datatype": "Currency"},
		{"label": "Cash Outflow", "value": cash_outflow, "datatype": "Currency"},
		{"label": "Bank Inflow", "value": bank_inflow, "datatype": "Currency"},
		{"label": "Bank Outflow", "value": bank_outflow, "datatype": "Currency"},
		{"label": "Closing Balance", "value": closing_balance, "datatype": "Currency"},
	]

	return columns, data, None, None, summary
