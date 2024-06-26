from typing import List, Optional

from pydantic_xml import BaseXmlModel, attr, element, wrapped

from libanaf.ubl.types import NSMAP


class Country(BaseXmlModel, tag="Country", ns="cac", nsmap=NSMAP):
    identification_code: str = element(tag="IdentificationCode", ns="cbc", nsmap=NSMAP)


class PostalAddress(BaseXmlModel, tag="PostalAddress", search_mode="unordered", ns="cac", nsmap=NSMAP):
    street_name: str = element(tag="StreetName", ns="cbc", nsmap=NSMAP)
    additional_street_name: Optional[str] = element(tag="AdditionalStreetName", default=None, ns="cbc", nsmap=NSMAP)
    city_name: str = element(tag="CityName", ns="cbc", nsmap=NSMAP)
    postal_zone: Optional[str] = element(tag="PostalZone", default=None, ns="cbc", nsmap=NSMAP)
    country_subentity: str = element(tag="CountrySubentity", ns="cbc", nsmap=NSMAP)
    country: Country
    address_line: Optional[List[str]] = wrapped("AddressLine", default=None, ns="cac", nsmap=NSMAP, entity=element(tag="Line", default=None, ns="cbc", nsmap=NSMAP))


class PartyIdentification(BaseXmlModel, tag="PartyIdentification", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)


class PartyName(BaseXmlModel, tag="PartyName", ns="cac", nsmap=NSMAP):
    name: str = element(tag="Name", ns="cbc", nsmap=NSMAP)


class TaxScheme(BaseXmlModel, tag="TaxScheme", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)


class PartyTaxScheme(BaseXmlModel, tag="PartyTaxScheme", ns="cac", nsmap=NSMAP):
    company_id: Optional[str] = element(tag="CompanyID", default=None, ns="cbc", nsmap=NSMAP)
    tax_scheme: Optional[TaxScheme] = None


class PartyLegalEntity(BaseXmlModel, tag="PartyLegalEntity", ns="cac", nsmap=NSMAP):
    registration_name: Optional[str] = element(tag="RegistrationName", default=None, ns="cbc", nsmap=NSMAP)
    company_id: Optional[str] = element(tag="CompanyID", default=None, ns="cbc", nsmap=NSMAP)


class PartyContact(BaseXmlModel, tag="Contact", ns="cac", nsmap=NSMAP):
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
    contact: Optional[PartyContact] = None


class Price(BaseXmlModel, tag="Price", ns="cac", nsmap=NSMAP):
    price_amount: float = element(tag="PriceAmount", ns="cbc", nsmap=NSMAP)
    base_quantity: Optional[float] = element(tag="BaseQuantity", default=1.0, ns="cbc", nsmap=NSMAP)


class ClassifiedTaxCategory(BaseXmlModel, tag="ClassifiedTaxCategory", ns="cac", nsmap=NSMAP):
    id: str = element(tag="ID", ns="cbc", nsmap=NSMAP)
    percent: Optional[float] = element(tag="Percent", default=None, ns="cbc", nsmap=NSMAP)
    tax_scheme: Optional[TaxScheme] = None


class OrderLineReference(BaseXmlModel, tag="OrderLineReference", ns="cac", nsmap=NSMAP):
    line_id: Optional[str] = element(tag="LineID", default=None, ns="cbc", nsmap=NSMAP)


class CommodityClassification(BaseXmlModel, tag="CommodityClassification", ns="cac", nsmap=NSMAP):
    item_classification_code: Optional[str] = element(tag="ItemClassificationCode", default="None", ns="cbc", nsmap=NSMAP)
    list_id: Optional[str] = wrapped("ItemClassificationCode", ns="cbc", nsmap=NSMAP, default=None, entity=attr("listID"))


class Item(BaseXmlModel, tag="Item", search_mode="unordered", ns="cac", nsmap=NSMAP):
    name: str = element(tag="Name", ns="cbc", nsmap=NSMAP)
    seller_item_id: Optional[str] = wrapped("SellersItemIdentification", ns="cac", nsmap=NSMAP, default=None, entity=element(tag="ID", default=None, ns="cbc", nsmap=NSMAP))
    origin_country: Optional[str] = wrapped("OriginCountry", ns="cac", nsmap=NSMAP, default=None, entity=element("IdentificationCode", default=None, ns="cbc", nsmap=NSMAP))
    commodity_classification: Optional[CommodityClassification] = None
    classified_tax_category: ClassifiedTaxCategory


class InvoiceLine(BaseXmlModel, tag="InvoiceLine", search_mode="unordered", ns="cac", nsmap=NSMAP):
    id: str = element(tag="ID", ns="cbc", nsmap=NSMAP)
    note: Optional[List[str]] = element(tag="Note", default=None, ns="cbc", nsmap=NSMAP)
    invoiced_quantity: float = element(tag="InvoicedQuantity", ns="cbc", nsmap=NSMAP)
    line_extension_amount: float = element(tag="LineExtensionAmount", ns="cbc", nsmap=NSMAP)
    order_line_reference: Optional[OrderLineReference] = None
    item: Item = element(tag="Item", ns="cac", nsmap=NSMAP)
    price: Price = element(tag="Price", ns="cac", nsmap=NSMAP)


class TaxCategory(BaseXmlModel, tag="TaxCategory", search_mode="unordered", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    tax_exempt_reason_code: Optional[str] = element(tag="TaxExemptionReasonCode", default=None, ns="cbc", nsmap=NSMAP)
    tax_exempt_reason: Optional[str] = element(tag="TaxExemptionReason", default=None, ns="cbc", nsmap=NSMAP)
    tax_scheme: TaxScheme


class TaxSubtotal(BaseXmlModel, tag="TaxSubtotal", ns="cac", nsmap=NSMAP):
    taxable_amount: float = element(tag="TaxableAmount", ns="cbc", nsmap=NSMAP)
    tax_amount: float = element(tag="TaxAmount", ns="cbc", nsmap=NSMAP)


class TaxTotal(BaseXmlModel, tag="TaxTotal", ns="cac", nsmap=NSMAP):
    tax_amount: float = element(tag="TaxAmount", ns="cbc", nsmap=NSMAP)
    tax_subtotal: TaxSubtotal


class LegalMonetaryTotal(BaseXmlModel, tag="LegalMonetaryTotal", search_mode="unordered", ns="cac", nsmap=NSMAP):
    line_extension_amount: Optional[float] = element(tag="LineExtensionAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    tax_exclusive_amount: Optional[float] = element(tag="TaxExclusiveAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    tax_inclusive_amount: Optional[float] = element(tag="TaxInclusiveAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    allowance_total_amount: Optional[float] = element(tag="AllowanceTotalAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    charge_total_amount: Optional[float] = element(tag="ChargeTotalAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    prepaid_amount: Optional[float] = element(tag="PrepaidAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    payable_rounding_amount: Optional[float] = element(tag="PayableRoundingAmount", default=0.0, ns="cbc", nsmap=NSMAP)
    payable_amount: float = element(tag="PayableAmount", ns="cbc", nsmap=NSMAP)


class Attachment(BaseXmlModel, tag="Attachment", ns="cac", nsmap=NSMAP):
    embedded_binary_document: bytes = element("EmbeddedDocumentBinaryObject", ns="cbc", nsmap=NSMAP)


class AdditionalDocumentReference(BaseXmlModel, tag="AdditionalDocumentReference", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    attachment: Optional[Attachment] = None


class OrderReference(BaseXmlModel, tag="OrderReference", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(tag="ID", default=None, ns="cbc", nsmap=NSMAP)
    sales_order_id: Optional[str] = element(tag="SalesOrderID", default=None, ns="cbc", nsmap=NSMAP)


class FinancialInstitutionBranch(BaseXmlModel, tag="FinancialInstitutionBranch", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(name="ID", default=None, ns="cbc", nsmap=NSMAP)


class PayeeFinancialAccount(BaseXmlModel, tag="PayeeFinancialAccount", search_mode="unordered", ns="cac", nsmap=NSMAP):
    id: Optional[str] = element(name="ID", default=None, ns="cbc", nsmap=NSMAP)
    name: Optional[str] = element(name="Name", default=None, ns="cbc", nsmap=NSMAP)
    financial_institution_branch: Optional[FinancialInstitutionBranch] = None


class PaymentMeans(BaseXmlModel, tag="PaymentMeans", search_mode="unordered", ns="cac", nsmap=NSMAP):
    payment_means_code: Optional[str] = element(name="PaymentMeansCode", default=None, ns="cbc", nsmap=NSMAP)
    payment_id: Optional[str] = element(name="PaymentID", default=None, ns="cbc", nsmap=NSMAP)
    payee_financial_account: Optional[PayeeFinancialAccount] = None
