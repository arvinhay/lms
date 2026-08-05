import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import get_url


def get_login_with_email_link_ratelimit() -> int:
	return frappe.get_system_settings("rate_limit_email_link_login") or 5


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=get_login_with_email_link_ratelimit, seconds=60 * 60)
def send_login_link(email: str):
	"""Send Frappe's one-time login link, resolving users by ID or email field.

	Frappe's default implementation only accepts the User document name. Some LMS
	accounts may use a non-email username while storing the login address in the
	User.email field, so this keeps the public behaviour private while still
	delivering links to valid enabled users.
	"""
	if not frappe.get_system_settings("login_with_email_link"):
		return

	try:
		user = _resolve_login_link_user(email)
		if not user:
			return

		expiry = frappe.get_system_settings("login_with_email_link_expiry") or 10
		link = _generate_temporary_login_link(user, expiry)
		recipient = frappe.db.get_value("User", user, "email") or user

		app_name = (
			frappe.get_website_settings("app_name") or frappe.get_system_settings("app_name") or _("Frappe")
		)
		first_name = frappe.db.get_value("User", user, "first_name") or _("there")
		subject = _("Your secure sign-in link for {0}").format(app_name)

		frappe.sendmail(
			subject=subject,
			recipients=recipient,
			template="rea_login_with_email_link",
			args={
				"first_name": first_name,
				"link": link,
				"minutes": expiry,
				"app_name": app_name,
			},
			now=True,
		)
	except frappe.OutgoingEmailError:
		frappe.clear_messages()
		frappe.log_error(title="Login link email could not be sent", message=frappe.get_traceback())
	except Exception:
		frappe.clear_messages()
		frappe.log_error(title="Login link generation failed unexpectedly", message=frappe.get_traceback())


def _resolve_login_link_user(login_id: str) -> str | None:
	login_id = (login_id or "").strip()
	if not login_id:
		return None

	if frappe.db.exists("User", {"name": login_id, "enabled": 1}):
		return login_id

	return frappe.db.get_value("User", {"email": login_id, "enabled": 1}, "name")


def _generate_temporary_login_link(user: str, expiry: int) -> str:
	key = frappe.generate_hash()
	frappe.cache.set_value(f"one_time_login_key:{key}", user, expires_in_sec=expiry * 60)
	return get_url(f"/api/method/frappe.www.login.login_via_key?key={key}", allow_header_override=False)
