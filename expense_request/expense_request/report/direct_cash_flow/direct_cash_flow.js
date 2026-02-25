// Copyright (c) 2026, Bantoo and contributors
// For license information, please see license.txt

frappe.query_reports["Direct Cash Flow"] = {
    tree: true,
    name_field: "particulars",
    parent_field: "parent",
    initial_depth: 1,

    filters: [

        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
            options: "Company",
            reqd: 1
        },

        {
            fieldname: "finance_book",
            label: "Finance Book",
            fieldtype: "Link",
            options: "Finance Book"
        },

        {
            fieldname: "filter_based_on",
            label: "Filter Based On",
            fieldtype: "Select",
            options: "Fiscal Year\nDate Range",
            default: "Fiscal Year"
        },

        {
            fieldname: "from_fiscal_year",
            label: "From Fiscal Year",
            fieldtype: "Link",
            options: "Fiscal Year",
            depends_on: "eval:doc.filter_based_on=='Fiscal Year'"
        },

        {
            fieldname: "to_fiscal_year",
            label: "To Fiscal Year",
            fieldtype: "Link",
            options: "Fiscal Year",
            depends_on: "eval:doc.filter_based_on=='Fiscal Year'"
        },

        {
            fieldname: "period_start_date",
            label: "Start Date",
            fieldtype: "Date",
            depends_on: "eval:doc.filter_based_on=='Date Range'"
        },

        {
            fieldname: "period_end_date",
            label: "End Date",
            fieldtype: "Date",
            depends_on: "eval:doc.filter_based_on=='Date Range'"
        },

        {
            fieldname: "periodicity",
            label: "Periodicity",
            fieldtype: "Select",
            options: "Monthly\nQuarterly\nHalf-Yearly\nYearly",
            default: "Monthly"
        },

        {
            fieldname: "cost_center",
            label: "Cost Center",
            fieldtype: "Link",
            options: "Cost Center"
        },

        {
            fieldname: "project",
            label: "Project",
            fieldtype: "Link",
            options: "Project"
        },

        {
            fieldname: "include_default_book_entries",
            label: "Include Default FB Entries",
            fieldtype: "Check"
        },

        {
            fieldname: "show_opening_and_closing_balance",
            label: "Show Opening and Closing Balance",
            fieldtype: "Check"
        }
    ],

    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (data && data.bold) {
            value = `<b>${value}</b>`;
        }

        return value;
    }
};