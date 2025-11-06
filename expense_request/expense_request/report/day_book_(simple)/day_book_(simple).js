// Copyright (c) 2025, Bantoo and contributors
// For license information, please see license.txt

frappe.query_reports["Day Book (Simple)"] = {
	"filters": [
		// {
        //     "fieldname":"fiscal_year",
        //     "label": __("Fiscal Year"),
        //     "fieldtype": "Link",
        //     "options": "Fiscal Year",
        //     "reqd": 1
        // },
        {
            "fieldname":"company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname":"from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
			"default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname":"to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
			"default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "accounts",
            "label": __("Accounts"),
            "fieldtype": "MultiSelectList",
            "get_data": function(txt) {
                return frappe.db.get_link_options("Account", txt);
            },
        }

	]
};

