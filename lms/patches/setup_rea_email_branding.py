import os

import frappe


WELCOME_TEMPLATE = "REA LMS - Welcome"
PASSWORD_RESET_TEMPLATE = "REA LMS - Password Reset"


def execute():
	_setup_system_templates()
	_setup_email_account()
	_setup_system_identity()


def _setup_system_templates():
	base_path = frappe.get_app_path("lms", "templates", "emails")
	templates = {
		WELCOME_TEMPLATE: {
			"subject": "Welcome to REA LMS",
			"filename": "rea_welcome.html",
		},
		PASSWORD_RESET_TEMPLATE: {
			"subject": "Reset your REA LMS password",
			"filename": "rea_password_reset.html",
		},
	}

	for name, values in templates.items():
		content = frappe.read_file(os.path.join(base_path, values["filename"]))
		if frappe.db.exists("Email Template", name):
			doc = frappe.get_doc("Email Template", name)
		else:
			doc = frappe.new_doc("Email Template")
			doc.name = name

		doc.subject = values["subject"]
		doc.use_html = 1
		doc.response_html = content
		doc.save(ignore_permissions=True)

	frappe.db.set_single_value("System Settings", "welcome_email_template", WELCOME_TEMPLATE)
	frappe.db.set_single_value(
		"System Settings", "reset_password_template", PASSWORD_RESET_TEMPLATE
	)


def _setup_email_account():
	account_name = frappe.db.get_value(
		"Email Account",
		{"default_outgoing": 1, "enable_outgoing": 1},
		"name",
	)
	if not account_name:
		return

	account = frappe.get_doc("Email Account", account_name)
	account.brand_logo = "/assets/lms/frontend/rea-logo.png"
	account.footer = _email_footer()
	account.save(ignore_permissions=True)


def _setup_system_identity():
	frappe.db.set_single_value("System Settings", "app_name", "REA LMS")
	frappe.db.set_single_value("System Settings", "otp_issuer_name", "REA LMS")
	frappe.db.set_default("site_name", "REA LMS")


def _email_footer():
	site_url = frappe.utils.get_url()
	return f"""
		<div>
			<strong>Refugee Education Australia</strong><br>
			This is an automated message from REA LMS. Please do not reply.<br>
			<a href="{site_url}">Open REA LMS</a>
		</div>
	"""
