import frappe


CONTACT_US_EMAIL = "contactus@refugee-education.org.au"


def execute():
	frappe.db.set_single_value("LMS Settings", "contact_us_email", CONTACT_US_EMAIL)
	frappe.db.set_single_value("LMS Settings", "contact_us_url", "")
