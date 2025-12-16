
frappe.ui.form.on('Payment Entry', {
    refresh(frm) {

        // Ensure references grid exists
        if (!frm.fields_dict.references) return;

        // Remove old handlers to avoid duplicate firing
        frm.fields_dict.references.grid.wrapper
            .off('click.allocate_row')

            // Attach click handler to grid rows
            .on('click.allocate_row', '.grid-row', function () {

                let idx = $(this).attr('data-idx');
                if (!idx) return;

                // Find the clicked row
                let row = frm.doc.references.find(r => r.idx == idx);
                if (!row) return;

                let paid_amount = flt(frm.doc.paid_amount || 0);

                // Calculate total allocated so far
                let total_allocated = frm.doc.references.reduce(
                    (sum, r) => sum + flt(r.allocated_amount),
                    0
                );

                let remaining = paid_amount - total_allocated;

                // Stop if nothing left to allocate
                if (remaining <= 0) {
                    frappe.msgprint(__('Paid Amount fully allocated'));
                    return;
                }

                // Allocate min(outstanding, remaining)
                let allocation = Math.min(
                    flt(row.outstanding_amount),
                    remaining
                );

                //use frappe.model.set_value
                frappe.model.set_value(
                    row.doctype,
                    row.name,
                    'allocated_amount',
                    allocation
                );
            });
    }
});
