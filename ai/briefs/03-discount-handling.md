# Feature Brief: Handle "Fake" Discount Lines in Invoices

## Context
Some suppliers issue invoices where discounts are listed as separate `InvoiceLine` items with negative quantities, rather than using the standard UBL `AllowanceCharge`. This is semantically incorrect but validates against the schema.

### Issues
1.  **Inventory**: Inflated stock value (real items at full price), phantom "DISCOUNT" products with negative stock.
2.  **Semantics**: "Discount" is a property of price, not a physical good.

## Goal
Detect these "fake" discount lines and distribute their value proportionally to the real product lines in the `product-summary` output.

## Implementation Details

### Logic
The `_prepare_line_entries` function in `libanaf/invoices/product_summary.py` will be updated to use a 3-pass approach:

1.  **First Pass**: Parse all lines into `_LineComputation` objects. Calculate `net_after_line` for each.
2.  **Second Pass**: Separate entries into `product_entries` and `discount_entries`.
    -   **Detection Heuristic**: `quantity < 0` AND (`"discount"` in name OR `"reducere"` in name).
3.  **Third Pass**: Distribute the total value of `discount_entries` to `product_entries`.
    -   Calculate `total_special_discount` (sum of `net_after_line` of discount entries).
    -   Distribute this amount proportionally to the `raw_amount` (absolute) of the product entries.
    -   Apply the adjustment to `final_net` of the product entries.

### Output
The "fake" discount lines will be removed from the final list of entries. The real product lines will have their `total_per_line` reduced by the distributed discount amount.

## Verification
-   **Test Files**:
    -   `dlds/6256610403_5733390573.xml`
    -   `dlds/4070424984_4613282582.xml`
    -   `dlds/4147817631_4653348903.xml`
    -   `dlds/5895021193_5549139021.xml`
-   **Success Criteria**:
    -   No negative quantity lines with "Discount" in the name in the output.
    -   Total Payable Amount matches the invoice total.
    -   Real products show a reduced Total Per Line.
