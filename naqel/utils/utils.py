import frappe
from frappe import _


@frappe.whitelist()
def get_default_address(link_doctype, link_name, sort_key="is_primary_address"):
    """Get the default address linked to any doctype (Company, Customer, Facility, etc.).

    Resolves the Address via the Dynamic Link table and returns the one flagged as
    default (highest sort_key), skipping disabled addresses.
    """
    if not link_name:
        return None

    if sort_key not in ["is_shipping_address", "is_primary_address"]:
        return None

    Addr = frappe.qb.DocType("Address")
    DL = frappe.qb.DocType("Dynamic Link")

    out = (
        frappe.qb.from_(Addr)
        .inner_join(DL).on(DL.parent == Addr.name)
        .select(Addr.name, Addr[sort_key])
        .where(DL.link_doctype == link_doctype)
        .where(DL.link_name == link_name)
        .where(Addr.disabled.isnull() | (Addr.disabled == 0))
    ).run()

    if out:
        return max(out, key=lambda x: x[1])[0]
    return None


@frappe.whitelist()
def get_party_details(party_type, party):
    """Lean clone of erpnext's get_party_details for Service Quotation.

    Resolves the party's display name, default address (rendered via the Address
    Template) and default contact (rendered) for the given party_type
    (Customer / Lead / Prospect / CRM Deal). Returns a dict keyed by Service
    Quotation field names so the client can ``frm.set_value(r.message)`` directly.
    """
    from frappe.contacts.doctype.address.address import get_address_display
    from frappe.contacts.doctype.contact.contact import get_contact_details
    from naqel.utils.contract.party import get_default_contact

    out = {
        "customer_name": "",
        "customer_address": "",
        "customer_address_display": "",
        "contact_person": "",
        "contact_display": "",
        "contact_mobile": "",
        "contact_email": "",
    }

    if not (party_type and party):
        return out

    # Display name (mirrors erpnext Quotation.set_customer_name): a Customer uses
    # customer_name; a Lead uses its company (organization) name, falling back to the
    # person's lead_name. Other party types fall back to the doctype's title field.
    if party_type == "Customer":
        out["customer_name"] = frappe.db.get_value(
            "Customer", party, "customer_name") or party
    elif party_type == "Lead":
        lead_name, company_name = frappe.db.get_value(
            "Lead", party, ["lead_name", "company_name"])
        out["customer_name"] = company_name or lead_name or party
    else:
        title_field = frappe.get_meta(party_type).title_field or "name"
        out["customer_name"] = frappe.db.get_value(
            party_type, party, title_field) or party

    # Default address (rendered via the Address Template)
    address = get_default_address(party_type, party)
    if address:
        out["customer_address"] = address
        out["customer_address_display"] = get_address_display(address) or ""

    # Default contact (rendered)
    contact = get_default_contact(party_type, party)
    if contact:
        details = get_contact_details(contact)
        out["contact_person"] = details.get("contact_person") or ""
        out["contact_display"] = details.get("contact_display") or ""
        out["contact_mobile"] = details.get("contact_mobile") or ""
        out["contact_email"] = details.get("contact_email") or ""

    return out


# ---------------------------------------------------------------------------
# Session-default-aware party helpers
# ---------------------------------------------------------------------------

def get_current_producer(raise_if_missing: bool = True) -> str | None:
    """Return the Producer linked to the current session user.

    Strategy (fast → slow):
    1. Read from the server-side session default set at login time.
    2. Fall back to a DB JOIN query (and cache the result in the session default
       so the next call is instant).

    Args:
        raise_if_missing: When True (default) raise PermissionError if the user
                          is not linked to any Producer.

    Returns:
        The Producer document name, or None when raise_if_missing is False.
    """
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Not authenticated"), frappe.PermissionError)

    # 1. Fast path – session default set at login
    producer_name = frappe.defaults.get_user_default("producer")
    if producer_name:
        return producer_name

    # 2. Slow path – DB query with caching
    from frappe.query_builder import DocType

    Producer = DocType("Producer")
    PartyPortalUser = DocType("Party Portal User")

    rows = (
        frappe.qb.from_(Producer)
        .inner_join(PartyPortalUser)
        .on(
            (PartyPortalUser.parent == Producer.name)
            & (PartyPortalUser.parenttype == "Producer")
        )
        .select(Producer.name)
        .where(PartyPortalUser.user == user)
        .limit(1)
    ).run(as_dict=True)

    if rows:
        producer_name = rows[0].name
        # Cache it so subsequent calls skip the query
        frappe.defaults.set_user_default("producer", producer_name)
        return producer_name

    if raise_if_missing:
        frappe.throw(_("No Producer linked to this account"),
                     frappe.PermissionError)
    return None


def get_current_transporter(raise_if_missing: bool = True) -> str | None:
    """Return the Transporter linked to the current session user.

    Strategy (fast → slow):
    1. Read from the server-side session default set at login time.
    2. Fall back to a DB JOIN query (and cache the result in the session default
       so the next call is instant).

    Args:
        raise_if_missing: When True (default) raise PermissionError if the user
                          is not linked to any Transporter.

    Returns:
        The Transporter document name, or None when raise_if_missing is False.
    """
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(_("Not authenticated"), frappe.PermissionError)

    # 1. Fast path – session default set at login
    transporter_name = frappe.defaults.get_user_default("transporter")
    if transporter_name:
        return transporter_name

    # 2. Slow path – DB query with caching
    from frappe.query_builder import DocType

    Transporter = DocType("Transporter")
    PartyPortalUser = DocType("Party Portal User")

    rows = (
        frappe.qb.from_(Transporter)
        .inner_join(PartyPortalUser)
        .on(
            (PartyPortalUser.parent == Transporter.name)
            & (PartyPortalUser.parenttype == "Transporter")
        )
        .select(Transporter.name)
        .where(PartyPortalUser.user == user)
        .limit(1)
    ).run(as_dict=True)

    if rows:
        transporter_name = rows[0].name
        # Cache it so subsequent calls skip the query
        frappe.defaults.set_user_default("transporter", transporter_name)
        return transporter_name

    if raise_if_missing:
        frappe.throw(_("No Transporter linked to this account"),
                     frappe.PermissionError)
    return None


@frappe.whitelist()
def get_default_terms_template():
    """Get the default Service Contract Terms Template"""
    default_template = frappe.db.get_value(
        "Service Contract Terms Template",
        {"is_default": 1},
        "name"
    )
    return default_template


@frappe.whitelist()
def get_terms_template(template_name):
    """
    Fetch terms and conditions from the Service Contract Terms Template.
    """
    if not template_name:
        return

    try:
        template_doc = frappe.get_doc(
            "Service Contract Terms Template", template_name)

        template_terms = []
        for terms in template_doc.get("template_terms", []):
            template_terms.append({
                "primary_title": terms.primary_title,
                "primary_terms_and_conditions": terms.primary_terms_and_conditions,
                "foreign_title": terms.foreign_title,
                "foreign_terms_and_conditions": terms.foreign_terms_and_conditions,
            })

        return template_terms

    except frappe.DoesNotExistError:
        frappe.throw(
            _("Service Contract Terms Template {0} does not exist").format(template_name))
    except Exception as e:
        frappe.log_error(
            "Terms and Conditions Fetch",
            f"Error fetching terms and conditions: {str(e)}")


@frappe.whitelist()
def format_currency_in_words(amount, currency):
    from frappe.utils import money_in_words
    from decimal import Decimal

    """Helper function to format currency placement in words"""
    # Convert the amount to Decimal for precise arithmetic and split into integer and fractional parts
    amount = Decimal(amount).quantize(Decimal('0.01'))
    integer_part, fractional_part = str(amount).split('.')

    # Convert integer and fractional parts to words separately, removing "SAR" and "only."
    integer_part_in_words = money_in_words(integer_part, currency).replace(
        _(currency), "").replace(_("only."), "").strip()
    fractional_part_in_words = money_in_words(fractional_part, currency).replace(
        _(currency), "").replace(_("only."), "").strip()

    # Combine the parts with appropriate labels
    if int(fractional_part) > 0:
        formatted_words = f"{integer_part_in_words} {_(currency.upper())} {_('and')} {fractional_part_in_words} {_('Halala')} {_('only.')}"
    else:
        formatted_words = f"{integer_part_in_words} {_(currency.upper())} {_('only.')}"

    return formatted_words


@frappe.whitelist()
def get_reference_document_price_details(doctype, document_name):
    """Fetch contract items based on the document name."""
    from frappe.utils import flt

    doc = frappe.get_doc(doctype, document_name)
    price_details = {
        "currency": doc.currency,
        "total_taxes_and_charges": doc.total_taxes_and_charges,
    }
    # Set precision to 2 decimal places for the taxes and charges
    price_details.update({
        "taxes": flt(doc.total_taxes_and_charges, precision=2)
    })

    # Calculate the grand total
    grand_total = flt(doc.grand_total -
                      doc.total_taxes_and_charges, precision=2)
    price_details.update({
        "grand_total": grand_total
    })

    # Convert the grand total to words
    grand_total_in_words = format_currency_in_words(
        grand_total, doc.currency)
    price_details.update({
        "grand_total_in_words": grand_total_in_words
    })

    return price_details
