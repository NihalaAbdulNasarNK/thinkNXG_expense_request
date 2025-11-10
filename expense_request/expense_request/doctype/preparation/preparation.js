// Copyright (c) 2025, Bantoo and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Preparation", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Preparation', {
    to: function(frm) {
        if (frm.doc.from && frm.doc.to) {
            console.log("function");
            frappe.call({
                method: 'expense_request.expense_request.doctype.preparation.preparation.fetch_employees_by_expiry_range',
                args: {
                    from_date: frm.doc.from,
                    to_date: frm.doc.to
                },
                callback: function(r) {
                    if (r.message) {
                        frm.clear_table('preparation_record');
                        r.message.forEach(emp => {
                            let row = frm.add_child('preparation_record');
                            row.employee = emp.employee;
                            row.employee_name = emp.employee_name;
                            row.civil_id = emp.custom_civil_id;
                            row.renewal_or_extend = emp.renewal_or_extend;

                            // Expiry Dates
                            row.acls_expiry_date = emp.work_permit_expiry_date;
                            row.medical_expiry_date = emp.medical_insurance_expiry_date;
                            row.residency_expiry_date = emp.residency_expiry_date;
                            row.civil_id_expiry_date = emp.civil_id_expiry_date;
                            row.mol_contract_expiry_date = emp.contract_expiry_date;

                            // Amounts
                            row.acls_amount = emp.work_permit_amount;
                            row.medical_amount = emp.medical_insurance_amount;
                            row.bls_amount = emp.residency_amount;
                            row.civil_id_amount = emp.civil_id_amount;
                            row.mol_contract_amount = emp.contract_amount;
                            row.total_amount = emp.total_amount;
                        });
                        frm.refresh_field('preparation_record');
                    }
                }
            });
        }
    }
});


frappe.ui.form.on('Preparation Record', {
    acls_amount: calculate_total,
    medical_amount: calculate_total,
    bls_amount: calculate_total,
    civil_id_amount: calculate_total
});

function calculate_total(frm, cdt, cdn) {
    let child = locals[cdt][cdn];
    let total = 0;

    total += flt(child.acls_amount);
    total += flt(child.medical_amount);
    total += flt(child.bls_amount);
    total += flt(child.civil_id_amount);

    frappe.model.set_value(cdt, cdn, 'total_amount', total);
}

frappe.ui.form.on("Preparation Record", {
    total_amount: function(frm) {
        calculate_totals(frm);
    },
    preparation_record_remove: function(frm) {
        calculate_totals(frm);
    }
});

frappe.ui.form.on("Preparation", {
    refresh: function(frm) {
        calculate_totals(frm);
    }
});

function calculate_totals(frm) {
    let total = 0;
    frm.doc.preparation_record.forEach(row => {
        total += row.total_amount || 0;
    });
    frm.set_value("total_payment", total);
}