## Objective

 Write a new feature for the invoices subapp called prod-summary

## Arguments

- supplier_name: not mandatory, accepts wildcards
- invoice_number: not mandatory, accepts wildcards
- start_date
- end_date
- all arguments are optional; if none is supplied then all invoices are processed

## Other requirements

- use the rich library for the presentation layer
- separate the business logic from the presentation layer, these results will be required in the future for further processing
- comment all the code created by the agent using Google style comments
- separate the business logic from the presentation logic
- also create the tests for the implementation

## Output

- With those you need to create a table from the invoices / credit notes that satisfy the criteria with the following headers and criterias
  - Supplier, Invoices Number, Invoice Date, Total Value (Payable), Product, Product Code, Quantity, U.M., Price, Value, VAT Rate, VAT Value, Discount Rate, Discount Value, Total Per Line
  - Product Code only if the supplier supplies a code in the InvoiceLine
  - U.M. is the unitCode from the InvoicedQuantity
  - Price is the price per item
  - Value is the total value for the InvoiceLine
  - Discount Rate and/or Value depend on whether there is a discount only at document level or also at product level, if at document level then it needs to be proportionally divided between the InvoiceLines
  - Discount can be wrongly entered in the XML file (see below example), the amount is negative even though ChargeIndicator is false (the amount should be positive in the XML) and only be negative in calculations
  - In the end the sum of Total Per line **MUST** be equal to Total Value (Payable)

## Documentation

- [UBL 2.1 Invoice](https://www.truugo.com/ubl/2.1/invoice/)
- [UBL 2.1](https://docs.oasis-open.org/ubl/UBL-2.1.html)

## Example of complex invoice

tests/fixtues/invoice-4249721031_470534743.xml

## Other files

- See invoices/show and invoices/summary for some examples of files search, rich usage and calculations

## Example of InvoiceLine and calculations

see `tests/fixtures/invoice-discounts-terra-dent-5770358448_5485396796.xml`

```XML
  <cac:InvoiceLine>
    <cbc:ID>2</cbc:ID>
    <cbc:InvoicedQuantity unitCode="H87">10.0000</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="RON">83.20</cbc:LineExtensionAmount>
    <cac:AllowanceCharge>
      <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
      <cbc:AllowanceChargeReason>discount la document</cbc:AllowanceChargeReason>
      <cbc:Amount currencyID="RON">-8.32</cbc:Amount>
    </cac:AllowanceCharge>
    <cac:Item>
      <cbc:Name>PUDRA PROPHYPEARLS ORANGE KAVO PLIC 15G</cbc:Name>
      <cac:SellersItemIdentification>
        <cbc:ID>1.010.1830</cbc:ID>
      </cac:SellersItemIdentification>
      <cac:CommodityClassification>
        <cbc:ItemClassificationCode listID="TSP">33061000</cbc:ItemClassificationCode>
      </cac:CommodityClassification>
      <cac:ClassifiedTaxCategory>
        <cbc:ID>S</cbc:ID>
        <cbc:Percent>21.00</cbc:Percent>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="RON">8.32000000</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>
  <cac:InvoiceLine>
```

Item: PUDRA PROPHYPEARLS ORANGE KAVO PLIC 15G
Gross Value: 10.0000 (Quantity) × 8.32 (Price) = 83.20 RON
Discount: 8.32 RON
Value Without Tax (Taxable Amount): 83.20−8.32=74.88 RON
VAT Amount: 74.88×21.00%=15.72 RON
Total Value With Tax: 74.88+15.72=90.60 RON

## Implementation Steps

1. Reviewed existing invoice summary tooling and UBL models to understand document, line, and allowance data needed for product aggregation.
2. Implemented `libanaf/invoices/product_summary.py` with reusable business logic, rounding, and Rich presentation plus wired the new `prod-summary` CLI command.
3. Added regression tests around discount allocation, credit-note handling, document collection, and CLI rendering under `tests/test_product_summary.py`.
4. Documented usage in `README.md` so the new command is discoverable.
5. Ran formatting and test commands (`ruff`, `pytest`) to confirm everything stays green.
