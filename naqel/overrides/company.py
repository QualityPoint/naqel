from erpnext.setup.doctype.company.company import Company
from naqel.utils.validations import validate_credential_types


class NaqelCompany(Company):
    def validate(self):
        super().validate()
        validate_credential_types(self)
