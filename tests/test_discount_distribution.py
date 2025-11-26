from decimal import Decimal
from libanaf.invoices.product_summary import build_product_summary_rows
from libanaf.ubl.ubl_document import parse_ubl_document_from_string
from tests.test_product_summary import FIXTURES


def test_distribute_fake_discount_lines() -> None:
    # XML reproducing the structure of dlds/4070424984_4613282582.xml
    # Line 1: 10 units @ 23.5290 = 235.29
    # Line 2: -1 unit @ 82.77 = -82.77 (DISCOUNT 10%)
    # Total Net: 235.29 - 82.77 = 152.52

    xml_content = (FIXTURES / "invoice-with-fake-discount.xml").read_text()
    document = parse_ubl_document_from_string(xml_content)
    rows = build_product_summary_rows([document])

    # Expectation:
    # The "DISCOUNT 10%" line (Line 5 in the file) should be gone.
    # The real product lines should have their totals reduced.

    # In this specific file:
    # Line 1: 10 x 23.5290 = 235.29
    # Line 2: 5 x 12.6060 = 63.03
    # Line 3: 10 x 12.6050 = 126.05
    # Line 4: 40 x 10.0840 = 403.36
    # Line 5: -1 x 82.77 = -82.77 (DISCOUNT 10%)

    # Total Net (TaxExclusive): 744.96
    # Sum of positive lines: 235.29 + 63.03 + 126.05 + 403.36 = 827.73
    # Discount: -82.77
    # 827.73 - 82.77 = 744.96 (Matches)

    # The discount of 82.77 needs to be distributed across the 4 real lines.
    # Weights: [235.29, 63.03, 126.05, 403.36]
    # Total Weight: 827.73
    # Discount Ratio: 82.77 / 827.73 ~= 10%

    # We expect 4 rows, not 5.
    assert len(rows) == 4

    # Check that no row has "DISCOUNT" in the product name
    for row in rows:
        assert "DISCOUNT" not in row.product.upper()

    # Check totals match
    total_payable = sum(row.total_per_line for row in rows)

    print(f"\nTotal Payable: {total_payable}")
    for r in rows:
        print(f"{r.product}: Net={r.value}, Total={r.total_per_line}")

    # The file has PayableAmount = 886.50
    assert total_payable == Decimal("886.50")
