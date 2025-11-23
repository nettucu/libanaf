## Objective

 Write a new feature for the invoices subapp called prod-summary


There are multiple views here:
1. the UBL standard way, which I fully understand
2. The accounting way - How an invoice is entered in the books - here the LegalMonetaryTotal covers it all
3. The stocks/inventory manager/reselling point of view, where one would need to correctly enter the value per product in stock \
   so they know the base level they start from when reselling - this is where I think I am coming from and for me in the supplied table `Total Per Line` is actually this value.

I hope I did make myself understood, if not ask question please. Try to take into consideration all three points from above and basically have 3 personas:
- for point 1 act as a UBL specialist and analyst / coder that needs to implement code for managing UBL
- for point 2 act as an accountant that needs to add this invoice to his books (take Romania for the standards)
- for point 3 act as a stocks / inventory / logistics manager that needs to add these products to his stock and needs to assign the correct prices\
  for later reselling or using of these products in the production of their goods and how these would impact the production cost

What I am interested in is the perspective of inventory manager where the Total Per Line value should be:
1. If there are discounts at line Level

Example: invoice @dlds/4098027691_4627877821.xml -   <cbc:ID>IMC64506</cbc:ID>

- For this invoice the AllowanceTotalAmount is registered at document level (LegalMonetaryTotal) and at product InvoiceLineLevel

```xml
  <cac:LegalMonetaryTotal>
    <cbc:LineExtensionAmount currencyID="RON">-669.74</cbc:LineExtensionAmount>
    <cbc:TaxExclusiveAmount currencyID="RON">-468.82</cbc:TaxExclusiveAmount>
    <cbc:TaxInclusiveAmount currencyID="RON">-468.82</cbc:TaxInclusiveAmount>
    <cbc:AllowanceTotalAmount currencyID="RON">-200.92</cbc:AllowanceTotalAmount>
    <cbc:PayableAmount currencyID="RON">-468.82</cbc:PayableAmount>
  </cac:LegalMonetaryTotal>
```

Col `Total (Invoice)` = TaxInclusiveAmount = -468.82
Col `Total (Payable)` = PayableAmount = -468.82

```xml First InvoiceLine
  <cac:InvoiceLine>
    <cbc:ID>1</cbc:ID>
    <cbc:InvoicedQuantity unitCode="H87">-1.0000</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="RON">-334.87</cbc:LineExtensionAmount>
    <cac:AllowanceCharge>
      <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
      <cbc:AllowanceChargeReason>discount la document</cbc:AllowanceChargeReason>
      <cbc:Amount currencyID="RON">83.72</cbc:Amount>
    </cac:AllowanceCharge>
    <cac:Item>
      <cbc:Name>PAB3540 - POSITIONER</cbc:Name>
      <cac:SellersItemIdentification>
        <cbc:ID>PAB3540</cbc:ID>
      </cac:SellersItemIdentification>
      <cac:ClassifiedTaxCategory>
        <cbc:ID>Z</cbc:ID>
        <cbc:Percent>0.00</cbc:Percent>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="RON">334.87350000</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>
```
Col `Quantity` = -1
Col `Price` = 334.87 <cac:Price><cbc:PriceAmount> - should always be positive
Col `Value` = -334.87 = LineExtensionAmount from UBL or Quantity * Price
Col `VAT Rate` = 0   No VAT Info
Col `VAT Value` = 0  No VAT Info
Col `Discount Rate` =  MUST be calculated because it's not in UBL = (Discount Value / Value) * 100 = 83.72 / 334.87 * 100 = 25%
Col `Discount Value` = InvoiceLine Level in this case = 83.72
Col `Total Per Line` = NOT the LineExtensionAmount BUT `Value` - `Discount` = -334.87 + 83.72 = -251.15

```xml Second InvoiceLine
<cac:InvoiceLine>
    <cbc:ID>2</cbc:ID>
    <cbc:InvoicedQuantity unitCode="H87">-1.0000</cbc:InvoicedQuantity>
    <cbc:LineExtensionAmount currencyID="RON">-334.87</cbc:LineExtensionAmount>
    <cac:AllowanceCharge>
      <cbc:ChargeIndicator>false</cbc:ChargeIndicator>
      <cbc:AllowanceChargeReason>discount la document</cbc:AllowanceChargeReason>
      <cbc:Amount currencyID="RON">117.21</cbc:Amount>
    </cac:AllowanceCharge>
    <cac:Item>
      <cbc:Name>PAB3550 - POSITIONER</cbc:Name>
      <cac:SellersItemIdentification>
        <cbc:ID>PAB3550</cbc:ID>
      </cac:SellersItemIdentification>
      <cac:ClassifiedTaxCategory>
        <cbc:ID>Z</cbc:ID>
        <cbc:Percent>0.00</cbc:Percent>
        <cac:TaxScheme>
          <cbc:ID>VAT</cbc:ID>
        </cac:TaxScheme>
      </cac:ClassifiedTaxCategory>
    </cac:Item>
    <cac:Price>
      <cbc:PriceAmount currencyID="RON">334.87350000</cbc:PriceAmount>
    </cac:Price>
  </cac:InvoiceLine>

```
same as for Line 1 but the discount value is 117.21
Col `Discount Rate` calculate as above = 35%
Col `Total Per Line` = -334.87 + 117.21 = -217.66

When summing up the `Total Per Line` from both lines you get the `Total (Invoice)` -> -251.15 + -217.66 = -468.81 which is a rounding an acceptable rounding error

If there are discounts at document level, those are to be used only if sum(`Total Per Line`) <> `Total (Invoice)`


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
  - Supplier, Invoices Number, Invoice Date, Total (Invoice), Total Value (Payable), Product, Product Code, Quantity, U.M., Price, Value, VAT Rate, VAT Value, Discount Rate, Discount Value, Total Per Line
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
