# Copyright (c) 2025, Bantoo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Preparation(Document):
	pass



class Preparation(Document):
	pass
@frappe.whitelist()
def fetch_employees_by_posting_date( from_date, to):
    from frappe.utils import add_days, getdate

    posting_date = getdate(from_date)
    end_date = add_days(to, 30)

    # Fetch GRD settings amounts
    grd_settings = frappe.get_single("GRD Settings")
    cost_map = {
        row.renewal_or_extend: {
            "work_permit_amount": row.work_permit_amount or 0,
            "medical_insurance_amount": row.medical_insurance_amount or 0,
            "residency_amount": row.residency_stamp_amount or 0,
            "civil_id_amount": row.civil_id_amount or 0,
            "no_of_years": row.no_of_years
        }
        for row in grd_settings.get("table_dkcn")
    }

    employees = frappe.get_all(
        "Employee",
        filters={
            "custom_bls_expiry_date": ["between", [posting_date, end_date]]
        },
        fields=["name", "employee_name", "custom_civil_id_no", "custom_bls_expiry_date"],
        order_by="modified desc"
    )

    for emp in employees:
        costs = cost_map.get("Renewal", {})
        emp.update({
            "renewal_or_extend": "Renewal",
            **costs,
           "total_amount": sum([
                costs.get("work_permit_amount", 0),
                costs.get("medical_insurance_amount", 0),
                costs.get("residency_amount", 0),
                costs.get("civil_id_amount", 0)
            ])
        })

    return employees

@frappe.whitelist()
def fetch_employees_by_expiry_range(from_date, to_date):
    from frappe.utils import getdate

    from_date = getdate(from_date)
    to_date = getdate(to_date)

    # Fetch GRD settings as a category-cost mapping
    grd_settings = frappe.get_single("GRD Settings")
    cost_map = {
        row.category: {
            "amount": row.amount or 0,
            "no_of_years": row.no_of_years or "",
            "renewal_or_extend": row.renewal_or_extend or ""
        }
        for row in grd_settings.get("table_dkcn") or []
    }

    # Fields to check for expiry
    expiry_fields = {
        "Work Permit": "custom_acls_expiry_date",
        "Medical Insurance": "custom_medical_expiry_date",
        "Residency Stamp": "custom_bls_expiry_date",
        "Civil ID": "custom_civil_id_expiry_date",
        "Contract": "custom_mol_contract_expiry_date"
    }

    employees = frappe.get_all(
        "Employee",
        fields=["name", "employee_name", "custom_civil_id_no"] + list(expiry_fields.values()),
        # order_by="modified desc"
    )

    results = []

    # for emp in employees:
    #     employee_row = {
    #         "employee": emp.name,
    #         "employee_name": emp.employee_name,
    #         "custom_civil_id": emp.custom_civil_id_no,
    #         "renewal_or_extend": "Renewal",
    #         "work_permit_amount": 0,
    #         "medical_insurance_amount": 0,
    #         "residency_amount": 0,
    #         "civil_id_amount": 0,
    #         "contract_amount": 0,
    #         "total_amount": 0,
    #         "work_permit_expiry_date": emp.get(expiry_fields["Work Permit"]),
    #         "medical_insurance_expiry_date": emp.get(expiry_fields["Medical Insurance"]),
    #         "residency_expiry_date": emp.get(expiry_fields["Residency Stamp"]),
    #         "civil_id_expiry_date": emp.get(expiry_fields["Civil ID"]),
    #         "contract_expiry_date": emp.get(expiry_fields["Contract"])
            

    #     }

    #     total = 0

    #     for category, field in expiry_fields.items():
    #         expiry_date = emp.get(field)
    #         if expiry_date and from_date <= getdate(expiry_date) <= to_date:
    #             cost_data = cost_map.get(category)
    #             if cost_data:
    #                 amount = cost_data.get("amount", 0)
    #                 total += amount
    #                 if category == "Work Permit":
    #                     employee_row["work_permit_amount"] = amount
    #                 elif category == "Medical Insurance":
    #                     employee_row["medical_insurance_amount"] = amount
    #                 elif category == "Residency Stamp":
    #                     employee_row["residency_amount"] = amount
    #                 elif category == "Civil ID":
    #                     employee_row["civil_id_amount"] = amount
    #                 elif category == "Contract":
    #                     employee_row["contract_amount"] = amount

    #     if total > 0:
    #         employee_row["total_amount"] = total
    #         results.append(employee_row)

    # return results

    for emp in employees:
        employee_row = {
            "employee": emp.name,
            "employee_name": emp.employee_name,
            "custom_civil_id": emp.custom_civil_id_no,
            "renewal_or_extend": "Renewal",
            "work_permit_expiry_date": None,
            "medical_insurance_expiry_date": None,
            "residency_expiry_date": None,
            "civil_id_expiry_date": None,
            "contract_expiry_date": None,
            "work_permit_amount": 0,
            "medical_insurance_amount": 0,
            "residency_amount": 0,
            "civil_id_amount": 0,
            "contract_amount": 0,
            "total_amount": 0
        }

        total = 0
        found = False

        # Check each document
        for category, field in expiry_fields.items():
            expiry_date = emp.get(field)
            if expiry_date:
                expiry_date = getdate(expiry_date)

                # Only consider expiry dates in the given range
                if from_date <= expiry_date <= to_date:
                    found = True
                    cost_data = cost_map.get(category)
                    amount = cost_data.get("amount", 0) if cost_data else 0
                    total += amount

                    if category == "Work Permit":
                        employee_row["work_permit_expiry_date"] = expiry_date
                        employee_row["work_permit_amount"] = amount
                    elif category == "Medical Insurance":
                        employee_row["medical_insurance_expiry_date"] = expiry_date
                        employee_row["medical_insurance_amount"] = amount
                    elif category == "Residency Stamp":
                        employee_row["residency_expiry_date"] = expiry_date
                        employee_row["residency_amount"] = amount
                    elif category == "Civil ID":
                        employee_row["civil_id_expiry_date"] = expiry_date
                        employee_row["civil_id_amount"] = amount
                    elif category == "Contract":
                        employee_row["contract_expiry_date"] = expiry_date
                        employee_row["contract_amount"] = amount

        # Only add if at least one document is expiring in range
        if found:
            employee_row["total_amount"] = total
            results.append(employee_row)

    return results