import unittest
from invoice import render_invoice

class InvoiceTests(unittest.TestCase):
    def test_totals_print_support_and_html_escaping(self):
        lines=[{'Item':'Rice <script>alert(1)</script>','Quantity':'100 g','Regular (INR)':100,'Payable (INR)':80,'Savings (INR)':20,'Batches':'A&B'},
               {'Item':'onion','Quantity':'50 g','Regular (INR)':10,'Payable (INR)':10,'Savings (INR)':0}]
        html=render_invoice(lines,'2026-11-05','SC-TEST')
        self.assertIn('₹110.00',html)
        self.assertIn('₹90.00',html)
        self.assertIn('₹20.00',html)
        self.assertIn('window.print()',html)
        self.assertIn('SC-TEST',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>alert',html)
        self.assertIn('not a tax invoice',html)
