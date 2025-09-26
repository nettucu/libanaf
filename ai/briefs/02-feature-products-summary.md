**Objective**: Write a new feature for the invoices subapp called prod-summary

- **Arguments**:
  - supplier_name: not mandatory, accepts wildcards
  - invoice_number: not mandatory, accepts wildcards
  - start_date
  - end_date
  - all arguments are optional; if none is supplied then all invoices are processed

- **Output**:
  - With those you need to create a table from the invoices / credit notes that satisfy the criteria with the following headers and criterias
    - Supplier, Invoices Number, Invoice Date, Total Value (Payable), Product, Product Code, Quantity, U.M., Price, Value, VAT Rate, VAT Value, Discount Rate, Discount Value, Total Per Line
    - Product Code only if the supplier supplies a code in the InvoiceLine
    - U.M. is the unitCode from the InvoicedQuantity
    - Price is the price per item
    - Value is the total value for the InvoiceLine
    - Discount Rate and Value depend on whether there is a discount only at document level or also at product level, if at document level then it needs to be properly divided between the InvoiceLines
    - In the end the sum of Total Per line **MUST** be equal to Total Value (Payable)

**Documentation**:

- [UBL 2.1 Invoice](https://www.truugo.com/ubl/2.1/invoice/)
- [UBL 2.1](https://docs.oasis-open.org/ubl/UBL-2.1.html)

**Example of complex invoice**:

tests/fixtues/invoice-4249721031_470534743.xml
