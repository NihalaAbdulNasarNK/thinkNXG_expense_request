
import frappe
from erpnext.accounts.report.financial_statements import get_period_list, get_columns


def execute(filters=None):
	if not filters:
		filters = {}

	company = filters.get("company")

	# ---------------- CONDITIONS ----------------
	conditions = get_conditions(filters)

	# ---------------- PERIOD ----------------
	period_list = get_period_list(
		filters.get("from_fiscal_year"),
		filters.get("to_fiscal_year"),
		filters.get("period_start_date"),
		filters.get("period_end_date"),
		filters.get("filter_based_on"),
		filters.get("periodicity"),
		company=company,
	)

	columns = get_columns(filters.get("periodicity"), period_list, False, company)

	# ---------------- ACCOUNTS ----------------
	cash_accounts = tuple(frappe.get_all("Account",
		filters={"company": company, "account_type": "Cash"},
		pluck="name")) or ("__dummy__",)

	bank_accounts = tuple(frappe.get_all("Account",
		filters={"company": company, "account_type": "Bank"},
		pluck="name")) or ("__dummy__",)

	all_cash_bank = cash_accounts + bank_accounts

	data = []

	# ---------------- OPENING ----------------
	open_cash = get_opening(company, cash_accounts, period_list, filters, conditions)
	open_bank = get_opening(company, bank_accounts, period_list, filters, conditions)
	open_total = add(open_cash, open_bank)

	# ---------------- FLOWS ----------------
	cash_in = get_total(company, cash_accounts, "debit", period_list, filters, conditions)
	cash_out = get_total(company, cash_accounts, "credit", period_list, filters, conditions)

	bank_in = get_total(company, bank_accounts, "debit", period_list, filters, conditions)
	bank_out = get_total(company, bank_accounts, "credit", period_list, filters, conditions)

	net_cash = subtract(cash_in, cash_out)
	net_bank = subtract(bank_in, bank_out)
	net_total = add(net_cash, net_bank)
	# ensure total is sum of all periods
	net_total["total"] = sum(
		net_total.get(p["key"], 0) for p in period_list
	)

	close_cash = add(open_cash, net_cash)
	close_bank = add(open_bank, net_bank)
	close_total = add(close_cash, close_bank)
	last_key = period_list[-1]["key"]
	close_total["total"] = close_total.get(last_key, 0)

	# ---------------- TREE REPORT ----------------
	if filters.get("show_opening_and_closing_balance"):
		data.append(group_row("Opening Balance", open_total))
		data.append(row("Cash Opening Balance", open_cash, 1))
		data.append(row("Bank Opening Balance", open_bank, 1))

	data.append(group_row("Cash Inflow", cash_in))
	data.extend(get_children(company, cash_accounts, all_cash_bank, "debit", period_list, 1, filters, conditions))

	data.append(group_row("Cash Outflow", negate(cash_out)))
	data.extend(get_children(company, cash_accounts, all_cash_bank, "credit", period_list, 1, filters, conditions, negate_vals=True))

	data.append(group_row("Bank Inflow", bank_in))
	data.extend(get_children(company, bank_accounts, all_cash_bank, "debit", period_list, 1, filters, conditions))

	data.append(group_row("Bank Outflow", negate(bank_out)))
	data.extend(get_children(company, bank_accounts, all_cash_bank, "credit", period_list, 1, filters, conditions, negate_vals=True))

	data.append(row("Net Cash Movement", net_cash, 0, 1))
	data.append(row("Net Bank Movement", net_bank, 0, 1))
	data.append(row("Net Total Movement", net_total, 0, 1))

	if filters.get("show_opening_and_closing_balance"):
		data.append(group_row("Closing Balance", close_total))
		data.append(row("Cash Closing Balance", close_cash, 1))
		data.append(row("Bank Closing Balance", close_bank, 1))

	chart = get_chart(period_list, cash_in, cash_out, bank_in, bank_out)

	report_summary = get_report_summary(
		company, open_total, cash_in, cash_out,
		bank_in, bank_out, net_total, close_total
	)

	return columns, data, None, chart, report_summary


# ================= CONDITIONS =================

def get_conditions(filters):
	conditions = ""

	if filters.get("cost_center"):
		conditions += " AND gle.cost_center = %(cost_center)s"

	if filters.get("project"):
		conditions += " AND gle.project = %(project)s"

	if filters.get("finance_book"):
		conditions += " AND gle.finance_book = %(finance_book)s"

	if not filters.get("include_default_book_entries"):
		conditions += " AND (gle.finance_book IS NULL OR gle.finance_book = '')"

	return conditions


# ================= TOTAL =================

def get_total(company, accounts, field, period_list, filters, conditions):
	out = {}

	for p in period_list:
		val = frappe.db.sql(f"""
			SELECT COALESCE(SUM(gle.{field}),0)
			FROM `tabGL Entry` gle
			WHERE gle.company=%(company)s
			AND gle.account IN %(accounts)s
			AND gle.posting_date BETWEEN %(from)s AND %(to)s
			AND gle.{field} > 0
			AND gle.is_cancelled=0
			AND gle.is_opening='No'
			{conditions}
		""", {
			"company": company,
			"accounts": accounts,
			"from": p["from_date"],
			"to": p["to_date"],
			**filters
		})[0][0]

		out[p["key"]] = val

	out["total"] = sum(out.values())
	return out


# ================= OPENING =================

def get_opening(company, accounts, period_list, filters, conditions):
	out = {}

	for p in period_list:
		val = frappe.db.sql(f"""
			SELECT COALESCE(SUM(gle.debit - gle.credit),0)
			FROM `tabGL Entry` gle
			WHERE gle.company=%(company)s
			AND gle.account IN %(acc)s
			AND gle.is_cancelled=0
			AND (gle.posting_date < %(date)s OR gle.is_opening='Yes')
			{conditions}
		""", {
			"company": company,
			"acc": accounts,
			"date": p["from_date"],
			**filters
		})[0][0]

		out[p["key"]] = val

	# out["total"] = sum(out.values())
	open_last_key = period_list[-1]["key"]
	out["total"] = out.get(open_last_key, 0)
	return out


# ================= CHILDREN =================

def get_children(company, main_accounts, exclude_accounts, field, period_list, indent, filters, conditions, negate_vals=False):
	rows = []
	data = {}

	for p in period_list:
		res = frappe.db.sql(f"""
			SELECT opp.account, SUM(gle.{field}) as amount
			FROM `tabGL Entry` gle
			JOIN `tabGL Entry` opp
				ON gle.voucher_no = opp.voucher_no
				AND gle.name != opp.name
				AND opp.account NOT IN %(exclude)s
			WHERE gle.company=%(company)s
			AND gle.account IN %(main)s
			AND gle.posting_date BETWEEN %(from)s AND %(to)s
			AND gle.{field} > 0
			AND gle.is_cancelled=0
			AND gle.is_opening='No'
			{conditions}
			GROUP BY gle.voucher_no, opp.account
		""", {
			"company": company,
			"main": main_accounts,
			"exclude": exclude_accounts,
			"from": p["from_date"],
			"to": p["to_date"],
			**filters
		}, as_dict=True)

		for r in res:
			data.setdefault(r.account, {}).setdefault(p["key"], 0)
			data[r.account][p["key"]] += r.amount

	for acc in data:
		data[acc]["total"] = sum(data[acc].values())

	for acc, val in sorted(data.items(), key=lambda x: -x[1]["total"]):
		if negate_vals:
			val = {k: -v for k, v in val.items()}
		rows.append(row(acc, val, indent))

	return rows

#========================= CHART =========================
def get_chart(period_list, cash_in, cash_out, bank_in, bank_out):
	labels = [p["label"] for p in period_list]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": "Cash Inflow",
					"values": [cash_in.get(p["key"], 0) for p in period_list],
				},
				{
					"name": "Cash Outflow",
					"values": [-cash_out.get(p["key"], 0) for p in period_list],  # NEGATIVE
				},
				{
					"name": "Bank Inflow",
					"values": [bank_in.get(p["key"], 0) for p in period_list],
				},
				{
					"name": "Bank Outflow",
					"values": [-bank_out.get(p["key"], 0) for p in period_list],  # NEGATIVE
				},
			],
		},
		"type": "bar",
	}
# ========================= REPORT SUMMARY ======================================
def get_report_summary(company, open_total, cash_in, cash_out, bank_in, bank_out, net_total, close_total):
	currency = frappe.get_cached_value("Company", company, "default_currency")

	open_val = open_total.get("total", 0)
	net_val = net_total.get("total", 0)
	close_val = close_total.get("total", 0)

	return [
		{
			"value": open_val,
			"label": "Opening Balance",
			"datatype": "Currency",
			"indicator": "Green" if open_val >= 0 else "Red",
			"currency": currency,
		},
		{
			"value": cash_in.get("total", 0),
			"label": "Cash Inflow",
			"datatype": "Currency",
			"indicator": "Green",
			"currency": currency,
		},
		{
			"value": -cash_out.get("total", 0),
			"label": "Cash Outflow",
			"datatype": "Currency",
			"indicator": "Red",
			"currency": currency,
		},
		{
			"value": bank_in.get("total", 0),
			"label": "Bank Inflow",
			"datatype": "Currency",
			"indicator": "Green",
			"currency": currency,
		},
		{
			"value": -bank_out.get("total", 0),
			"label": "Bank Outflow",
			"datatype": "Currency",
			"indicator": "Red",
			"currency": currency,
		},
		{
			"value": net_val,
			"label": "Net Movement",
			"datatype": "Currency",
			"indicator": "Green" if net_val >= 0 else "Red",
			"currency": currency,
		},
		{
			"value": close_val,
			"label": "Closing Balance",
			"datatype": "Currency",
			"indicator": "Green" if close_val >= 0 else "Red",
			"currency": currency,
		},
	]

# ================= HELPERS =================

def row(label, values, indent=0, bold=0):
	r = {"account_name": label, "account": label, "indent": indent, "bold": bold}
	r.update(values or {})
	return r


def group_row(label, values):
	r = {
		"account_name": label,
		"account": label,
		"indent": 0,
		"bold": 1,
		"is_group": 1,
		"expandable": 1
	}
	r.update(values or {})
	return r


def add(a, b): return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}
def subtract(a, b): return {k: a.get(k, 0) - b.get(k, 0) for k in set(a) | set(b)}
def negate(a): return {k: -v for k, v in a.items()}