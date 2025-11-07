# Copyright (c) 2025, Bantoo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ManualEmployeeCheckin(Document):
	pass

	def on_submit(self):
		frappe.msgprint("Employee Checkin created")
		if self.workflow_state == "Approved by Employee Checkin Approver":
			# Punch IN
			if self.time:
				frappe.get_doc({
					"doctype": "Employee Checkin",
					"employee": self.employee,
					"time": self.time,
					"log_type": "IN",
					"device_id": self.location_device_id,
					"skip_auto_attendance": 0
				}).insert(ignore_permissions=True)

			# Punch OUT (only if provided)
			if self.time_out:
				frappe.get_doc({
					"doctype": "Employee Checkin",
					"employee": self.employee,
					"time": self.time_out,
					"log_type": "OUT",
					"device_id": self.device_id_out,
					"skip_auto_attendance": 0
				}).insert(ignore_permissions=True)