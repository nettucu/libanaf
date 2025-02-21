import datetime
from typing import List, Optional

from pydantic_xml import BaseXmlModel, attr, element, wrapped

from libanaf.ubl.ubl_types import NSMAP, NSMAP_CREDIT_NOTE


class Country(BaseXmlModel, tag="Country", ns="cac", nsmap=NSMAP):
    identification_code: str = element(tag="IdentificationCode", ns="cbc", nsmap=NSMAP)


class PostalAddress(BaseXmlModel, tag="PostalAddress", search_mode="unordered", ns="cac", nsmap=NSMAP):
    street_name: str = element(tag="StreetName", ns="cbc", nsmap=NSMAP)
    additional_street_name: Optional[str] = element(tag="AdditionalStreetName", default=None, ns="cbc", nsmap=NSMAP)
    city_name: str = element(tag="CityName", ns="cbc", nsmap=NSMAP)
    postal_zone: Optional[str] = element(tag="PostalZone", default=None, ns="cbc", nsmap=NSMAP)
    country_subentity: str = element(tag="CountrySubentity", ns="cbc", nsmap=NSMAP)
    country: Country
    address_line: Optional[List[str]] = wrapped(
        "AddressLine",
        default=None,
        ns="cac",
        nsmap=NSMAP,
        entity=element(tag="Line", default=None, ns="cbc", nsmap=NSMAP),
    )

    def get_display_str(self) -> dict[str, str]:
        address = ""
        if self.additional_street_name is not None:
            address = " ".join(self.address_line)  # pyright: ignore
        else:
            street = self.street_name or ""
            street_extra = self.additional_street_name or ""
            address = f"{street} {street_extra}"

        city = self.city_name or ""
        county = self.country_subentity or ""

        return {
            "fomatted": f"Adresa: {address}  {city}\nJudet: {county}",
            "address": address,
            "city": city,
            "county": county,
        }


class PartyIdentification(BaseXmlModel, tag="PartyIdentification", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)


class PartyName(BaseXmlModel, tag="PartyName", ns="cac", nsmap=NSMAP):
    name: str = element(tag="Name", ns="cbc", nsmap=NSMAP)


class TaxScheme(BaseXmlModel, tag="TaxScheme", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    name: Optional[str] = element(tag="Name", default=None, ns="cbc", nsmap=NSMAP)
    tax_type_code: Optional[str] = element(tag="TaxTypeCode", default=None, ns="cbc", nsmap=NSMAP)
    currency_code: Optional[str] = element(tag="CurrencyCode", default=None, ns="cbc", nsmap=NSMAP)


class PartyTaxScheme(BaseXmlModel, tag="PartyTaxScheme", ns="cac", nsmap=NSMAP):
    company_id: Optional[str] = element(tag="CompanyID", default=None, ns="cbc", nsmap=NSMAP)
    tax_scheme: Optional[TaxScheme] = None


class PartyLegalEntity(BaseXmlModel, tag="PartyLegalEntity", ns="cac", nsmap=NSMAP):
    registration_name: Optional[str] = element(tag="RegistrationName", default=None, ns="cbc", nsmap=NSMAP)
    company_id: Optional[str] = element(tag="CompanyID", default=None, ns="cbc", nsmap=NSMAP)
    company_legal_form: Optional[str] = element(tag="CompanyLegalForm", default=None, ns="cbc", nsmap=NSMAP)


class Contact(BaseXmlModel, tag="Contact", ns="cac", nsmap=NSMAP):
    name: Optional[str] = element(tag="Name", default=None, ns="cbc", nsmap=NSMAP)
    telephone: Optional[str] = element(tag="Telephone", default=None, ns="cbc", nsmap=NSMAP)
    electronic_mail: Optional[str] = element(tag="ElectronicMail", default=None, ns="cbc", nsmap=NSMAP)


class Party(BaseXmlModel, tag="Party", search_mode="unordered", ns="cac", nsmap=NSMAP):
    endpoint_id: Optional[str] = element(tag="EndpointID", default=None, ns="cbc", nsmap=NSMAP)
    party_identification: Optional[PartyIdentification] = None
    party_name: Optional[PartyName] = None
    postal_address: PostalAddress
    party_tax_scheme: Optional[PartyTaxScheme] = None
    party_legal_entity: PartyLegalEntity
    contact: Optional[Contact] = None

    def get_display_str(self) -> dict[str, str]:
        """
        Returns a string similar to:
        # GURSK MEDICA SRL
        # CIF: RO25629635
        # Reg. com.: J23/1344/2012
        # Adresa: INTR. VLASCEANU DUMITRU, Voluntari
        # Judet: Ilfov
        # IBAN: RO51BACX0000000363717001
        # Banca: UNICREDIT BANK SA
        """
        name = (
            self.party_name.name
            if self.party_name and self.party_name.name
            else (self.party_legal_entity.registration_name or "N/A")
        )

        cif = self.party_tax_scheme.company_id if self.party_tax_scheme and self.party_tax_scheme.company_id else "N/A"
        reg_com = (
            self.party_legal_entity.company_id
            if self.party_legal_entity and self.party_legal_entity.company_id
            else "N/A"
        )
        formatted_address, address, city, county = (
            self.postal_address.get_display_str().values() if self.postal_address else {"N/A", "N/A", "N/A", "N/A"}
        )

        return {
            "formatted": f"{name}\nCIF: {cif}\nReg. com.: {reg_com}\n{formatted_address}\n",
            "name": name,
            "cif": cif,
            "reg_com": reg_com,
            "address": address,
            "city": city,
            "county": county,
        }


class SupplierPartyType(BaseXmlModel):
    party: Party


class AccountingSupplierParty(SupplierPartyType, tag="AccountingSupplierParty", ns="cac"):  # , nsmap=NSMAP):
    pass


class AccountingCustomerParty(SupplierPartyType, tag="AccountingCustomerParty", ns="cac"):  # , nsmap=NSMAP):
    pass


class Price(BaseXmlModel, tag="Price", ns="cac", nsmap=NSMAP):
    price_amount: float = element(tag="PriceAmount", ns="cbc", nsmap=NSMAP)
    base_quantity: Optional[float] = element(tag="BaseQuantity", default=1.0, ns="cbc", nsmap=NSMAP)


class OrderLineReference(BaseXmlModel, tag="OrderLineReference", ns="cac", nsmap=NSMAP):
    line_id: Optional[str] = element(tag="LineID", default=None, ns="cbc", nsmap=NSMAP)


class CommodityClassification(BaseXmlModel, tag="CommodityClassification", ns="cac", nsmap=NSMAP):
    item_classification_code: Optional[str] = element(
        tag="ItemClassificationCode", default="None", ns="cbc", nsmap=NSMAP
    )
    list_id: Optional[str] = wrapped(
        "ItemClassificationCode", ns="cbc", nsmap=NSMAP, default=None, entity=attr("listID")
    )


class TaxCategory(BaseXmlModel, tag="TaxCategory", search_mode="unordered", ns="cac"):  # nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    name: Optional[str] = element(tag="name", default=None, ns="cbc", nsmap=NSMAP)
    percent: Optional[float] = element(tag="Percent", default=None, ns="cbc", nsmap=NSMAP)
    base_unit_measure: Optional[str] = element(tag="BaseUnitMeasure", default=None, ns="cbc", nsmap=NSMAP)
    per_unit_amount: Optional[float] = element(tag="PerUnitAmount", default=None, ns="cbc", nsmap=NSMAP)
    tax_exemption_reason_code: Optional[str] = element(
        tag="TaxExemptionReasonCode", default=None, ns="cbc", nsmap=NSMAP
    )
    tax_exemption_reason: Optional[str] = element(tag="TaxExemptionReason", default=None, ns="cbc", nsmap=NSMAP)
    tier_range: Optional[str] = element(tag="TierRange", default=None, ns="cbc", nsmap=NSMAP)
    tier_rate_percentage: Optional[float] = element(tag="TierRatePercentage", default=None, ns="cbc", nsmap=NSMAP)
    tax_scheme: TaxScheme


class ClassifiedTaxCategory(TaxCategory, tag="ClassifiedTaxCategory", ns="cac", nsmap=NSMAP):
    pass
    # id: str = element(tag="ID", ns="cbc", nsmap=NSMAP)
    # percent: Optional[float] = element(tag="Percent", default=None, ns="cbc", nsmap=NSMAP)
    # tax_scheme: Optional[TaxScheme] = None


class AllowanceCharge(BaseXmlModel, tag="AllowanceCharge", search_mode="unordered", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    # charge_indicator
    # FALSE = discount
    # TRUE = charge
    charge_indicator: bool = element(tag="ChargeIndicator", default=False, ns="cbc")
    allowance_charge_reason_code: Optional[str] = element(
        tag="AllowanceChargeReasonCode", default=None, ns="cbc", nsmap=NSMAP
    )
    allowance_charge_reason: Optional[str] = element(tag="AllowanceChargeReason", default=None, ns="cbc", nsmap=NSMAP)
    multiplier_factor_numeric: Optional[int] = element(
        tag="MultiplierFactorNumeric", default=None, ns="cbc", nsmap=NSMAP
    )
    prepaid_indicator: Optional[bool] = element(tag="PrepaidIndicator", default=None, ns="cbc", nsmap=NSMAP)
    sequence_numeric: Optional[int] = element(tag="SequenceNumeric", default=None, ns="cbc", nsmap=NSMAP)
    amount: float = element(tag="Amount", ns="cbc", nsmap=NSMAP)
    base_amount: float = element(tag="BaseAmount", ns="cbc", nsmap=NSMAP)
    per_unit_amount: Optional[float] = element(tag="PerUnitAmount", ns="cbc", nsmap=NSMAP)
    tax_category: Optional[TaxCategory]
    tax_total: Optional[str] = element(tag="TaxTotal", default=None, ns="cac", nsmap=NSMAP)


class Item(BaseXmlModel, tag="Item", search_mode="unordered", ns="cac", nsmap=NSMAP):
    description: str = element(tag="Description", default=None, ns="cbc", nsmap=NSMAP)
    name: str = element(tag="Name", ns="cbc", nsmap=NSMAP)
    seller_item_id: Optional[str] = wrapped(
        "SellersItemIdentification",
        ns="cac",
        nsmap=NSMAP,
        default=None,
        entity=element(tag="ID", default=None, ns="cbc", nsmap=NSMAP),
    )
    origin_country: Optional[str] = wrapped(
        "OriginCountry",
        ns="cac",
        nsmap=NSMAP,
        default=None,
        entity=element("IdentificationCode", default=None, ns="cbc", nsmap=NSMAP),
    )
    commodity_classification: Optional[CommodityClassification] = None
    classified_tax_category: ClassifiedTaxCategory


class InvoicePeriod(BaseXmlModel, tag="InvoicePeriod", search_mode="unordered", ns="cac"):
    start_date: Optional[datetime.date] = element(tag="StartDate", ns="cbc")
    start_time: Optional[datetime.time] = element(tag="StartTime", default=None, ns="cbc")  # , nsmap=NSMAP)
    end_date: Optional[datetime.date] = element(tag="EndDate", ns="cbc")
    end_time: Optional[datetime.time] = element(tag="EndTime", default=None, ns="cbc")  # , nsmap=NSMAP)
    duration_measure: Optional[str] = element(tag="DurationMeasure", default=None, ns="cbc")
    description_code: Optional[str] = element(tag="DescriptionCode", default=None, ns="cbc")
    description: Optional[str] = element(tag="Description", default=None, ns="cbc")


class InvoiceLine(BaseXmlModel, tag="InvoiceLine", search_mode="unordered", ns="cac"):  # , nsmap=NSMAP):
    id: str = element(tag="ID", ns="cbc", nsmap=NSMAP)
    note: Optional[List[str]] = element(tag="Note", default=None, ns="cbc", nsmap=NSMAP)
    invoiced_quantity: float = element(tag="InvoicedQuantity", ns="cbc", nsmap=NSMAP)
    line_extension_amount: float = element(tag="LineExtensionAmount", ns="cbc", nsmap=NSMAP)
    order_line_reference: Optional[OrderLineReference] = None
    item: Item  # = element(tag="Item", ns="cac", nsmap=NSMAP)
    price: Optional[Price] = None  # = element(tag="Price", ns="cac", nsmap=NSMAP)


class CreditNoteLine(BaseXmlModel, tag="CreditNoteLine", search_mode="unordered", ns="cac"):  # , nsmap=NSMAP):
    id: str = element(tag="ID", ns="cbc", nsmap=NSMAP_CREDIT_NOTE)
    credited_quantity: float = element(tag="CreditedQuantity", ns="cbc", nsmap=NSMAP_CREDIT_NOTE)
    line_extension_amount: float = element(tag="LineExtensionAmount", ns="cbc", nsmap=NSMAP_CREDIT_NOTE)
    item: Item  # = element(tag="Item", ns="cac", nsmap=NSMAP_CREDIT_NOTE)
    price: Price = element(tag="Price", ns="cac", nsmap=NSMAP_CREDIT_NOTE)


class TaxSubtotal(BaseXmlModel, tag="TaxSubtotal", ns="cac"):  # nsmap=NSMAP):
    taxable_amount: float = element(tag="TaxableAmount", ns="cbc", nsmap=NSMAP)
    tax_amount: float = element(tag="TaxAmount", ns="cbc", nsmap=NSMAP)


class TaxTotal(BaseXmlModel, tag="TaxTotal", ns="cac", nsmap=NSMAP):
    tax_amount: float = element(tag="TaxAmount", ns="cbc", nsmap=NSMAP)
    currency_id: str = wrapped("TaxAmount", ns="cbc", nsmap=NSMAP, default=None, entity=attr("currencyID"))
    tax_subtotal: TaxSubtotal


class LegalMonetaryTotal(BaseXmlModel, tag="LegalMonetaryTotal", search_mode="unordered", ns="cac"):  # , nsmap=NSMAP):
    line_extension_amount: Optional[float] = element(tag="LineExtensionAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    tax_exclusive_amount: Optional[float] = element(tag="TaxExclusiveAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    tax_inclusive_amount: Optional[float] = element(tag="TaxInclusiveAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    allowance_total_amount: Optional[float] = element(tag="AllowanceTotalAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    charge_total_amount: Optional[float] = element(tag="ChargeTotalAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    prepaid_amount: Optional[float] = element(tag="PrepaidAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    payable_rounding_amount: Optional[float] = element(tag="PayableRoundingAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    payable_amount: float = element(tag="PayableAmount", ns="cbc", nsmap=NSMAP)


class Attachment(BaseXmlModel, tag="Attachment", ns="cac"):  # , nsmap=NSMAP):
    embedded_binary_document: bytes = element("EmbeddedDocumentBinaryObject", ns="cbc", nsmap=NSMAP)


class AdditionalDocumentReference(BaseXmlModel, tag="AdditionalDocumentReference", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    attachment: Optional[Attachment] = None


class OrderReference(BaseXmlModel, tag="OrderReference", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    sales_order_id: Optional[str] = element(tag="SalesOrderID", default=None, ns="cbc", nsmap=NSMAP)


class FinancialInstitutionBranch(BaseXmlModel, tag="FinancialInstitutionBranch", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)

    def get_display_str(self) -> dict[str, str]:
        bank = self.id if self.id is not None else "N/A"
        return {
            "formatted": f"Banca: {bank}",
            "bank": bank,
        }


class PayeeFinancialAccount(BaseXmlModel, tag="PayeeFinancialAccount", search_mode="unordered", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    name: Optional[str] = element(tag="Name", default=None, ns="cbc", nsmap=NSMAP)
    financial_institution_branch: Optional[FinancialInstitutionBranch]

    def get_display_str(self) -> dict[str, str]:
        iban = self.id if self.id else "N/A"
        bank = (
            self.financial_institution_branch.get_display_str()["bank"] if self.financial_institution_branch else "N/A"
        )

        return {
            "formatted": f"IBAN: {iban}\nBanca: {bank}",
            "iban": iban,
            "bank": bank,
        }


class PaymentMeans(BaseXmlModel, tag="PaymentMeans", search_mode="unordered", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    payment_means_code: Optional[str] = element(tag="PaymentMeansCode", default=None, ns="cbc", nsmap=NSMAP)
    payment_id: Optional[str] = element(tag="PaymentID", default=None, ns="cbc", nsmap=NSMAP)
    payee_financial_account: Optional[PayeeFinancialAccount]

    def get_display_str(self) -> dict[str, str]:
        if self.payee_financial_account:
            return self.payee_financial_account.get_display_str()

        return {"formatted": "N/A", "iban": "N/A", "bank": "N/A"}
