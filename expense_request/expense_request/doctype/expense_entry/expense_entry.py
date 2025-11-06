# -*- coding: utf-8 -*-
# Copyright (c) 2020, Bantoo and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ExpenseEntry(Document):
	pass

	def validate(self):
			self.calculate_totals()

	def on_submit(self):
		self.link_journal_entry_to_expense_entry()

	def on_cancel(self):
		self.cancel_linked_journal_entry()

	def calculate_totals(self):
		total = 0
		count = 0
		expense_items = []

		for detail in self.expenses:
			total += float(detail.amount)
			count += 1

			if not detail.project and self.default_project:
				detail.project = self.default_project

			if not detail.cost_center and self.default_cost_center:
				detail.cost_center = self.default_cost_center

			expense_items.append(detail)

		self.expenses = expense_items
		self.total = total
		self.quantity = count

	def link_journal_entry_to_expense_entry(self):
		"""When Expense Entry is submitted, link its Journal Entry ID if exists."""
		je_name = frappe.db.get_value("Journal Entry", {"bill_no": self.name}, "name")

		if je_name and not self.journal_entry_id:
			self.db_set("journal_entry_id", je_name)
			frappe.msgprint(f"Linked Journal Entry <b>{je_name}</b> to Expense Entry <b>{self.name}</b>.")

	def cancel_linked_journal_entry(self):
		"""Cancel the Journal Entry linked to this Expense Entry when it is cancelled."""
		je_name = self.journal_entry_id or frappe.db.get_value("Journal Entry", {"bill_no": self.name}, "name")

		if not je_name:
			frappe.msgprint("No linked Journal Entry found for this Expense Entry.")
			return

		try:
			je = frappe.get_doc("Journal Entry", je_name)
			if je.docstatus == 1:
				je.cancel()
				frappe.msgprint(f"Journal Entry <b>{je_name}</b> cancelled as Expense Entry was cancelled.")
			else:
				frappe.msgprint(f"Journal Entry <b>{je_name}</b> is already cancelled or in draft.")
			self.db_set("journal_entry_id", None)
		except Exception as e:
			frappe.throw(f"Unable to cancel linked Journal Entry {je_name}: {str(e)}")
