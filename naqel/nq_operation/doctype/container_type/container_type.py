# Copyright (c) 2025, QuailtyPoint and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from naqel.utils.uom import validate_uom_field


class ContainerType(Document):
    def validate(self):
        validate_uom_field(self, "volume_unit", "Volume")
        validate_uom_field(self, "weight_unit", "Mass")


@frappe.whitelist()
def get_compatible_containers_query(doctype, txt, searchfield, start, page_len, filters):
    """Server-side search used by Service Quotation to filter Container Types whose
    removal_mechanisms table (Container Collection Mechanism child) includes the
    selected Collection Mechanism."""
    from frappe.query_builder import DocType

    sf = searchfield if searchfield in {"name", "container_type"} else "name"
    txt_like = f"%{txt}%"
    collection_mechanism = (filters or {}).get(
        "collection_mechanism") if isinstance(filters, dict) else None

    CT = DocType("Container Type")

    if not collection_mechanism:
        return (
            frappe.qb.from_(CT)
            .select(CT.name, CT.container_type)
            .where(getattr(CT, sf).like(txt_like))
            .limit(int(page_len))
            .offset(int(start))
            .run()
        )

    CCM = DocType("Container Collection Mechanism")
    subquery = (
        frappe.qb.from_(CCM)
        .select(CCM.parent)
        .where(CCM.parenttype == "Container Type")
        .where(CCM.collection_mechanism == collection_mechanism)
    )

    return (
        frappe.qb.from_(CT)
        .select(CT.name, CT.container_type)
        .where(CT.name.isin(subquery))
        .where(getattr(CT, sf).like(txt_like))
        .limit(int(page_len))
        .offset(int(start))
        .run()
    )
