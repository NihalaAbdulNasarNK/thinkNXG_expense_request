
frappe.ui.form.on('Vehicle Log', {
    refresh: function(frm) {
        frm.add_custom_button(__('Expense Entry'), function() {
            if (!frm.doc.name) {
                frappe.msgprint(__('Please save the Vehicle Log before creating an Expense Entry.'));
                return;
            }

            let service_detail = frm.doc.service_detail || [];

            frappe.model.with_doctype('Expense Entry', function() {
                // Create new Expense Entry document
                let doc = frappe.model.get_new_doc('Expense Entry');

                // Set main fields
                doc.vehicle_log_id = frm.doc.name;
                doc.employee_name = frm.doc.employee;
                doc.license_plate = frm.doc.license_plate;

                // Add rows to child table
                service_detail.forEach(row => {
                    let child = frappe.model.add_child(doc, 'expenses');
                    child.description = row.service_item || '';
                    child.amount = row.expense_amount || 0;
                });

                // Route to new document
                frappe.set_route('Form', doc.doctype, doc.name);

                // Wait a little and then refresh the form view (to render child table)
                setTimeout(() => {
                    frappe.get_doc(doc.doctype, doc.name);
                    frappe.ui.form.get_new_doc(doc.doctype, doc.name);
                    cur_frm.refresh_field('expenses');
                }, 500);
            });
        }, __('Create'));
    }
});
