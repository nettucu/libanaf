**Objective**: Write a new feature for the invoices subapp called summary

- **Arguments**:
  - supplier_name: not mandatory, accepts wildcards
  - invoice_number: not mandatory, accepts wildcards
  - start_date
  - end_date
  - at least one of supplier_name or invoice_number must be supplied

- **Output**:
  - With those you need to create a table from the invoices / credit notes that satisfy the criteria with the following headers
    - Invoices Number, Supplier, Invoice Date, Due Date, Total Value (Payable)

**Example**:

- See invoices/show for an example
