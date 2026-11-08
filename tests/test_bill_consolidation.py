import unittest
from usda_workflow import consolidate_cart_lines

class BillConsolidationTests(unittest.TestCase):
    def test_combo_and_extra_rice_appear_once_and_preserve_totals(self):
        raw=[{'Item':'1 + 2','Quantity':'100 g each','Regular (USD)':1.06,'Savings (USD)':.31,'Payable (USD)':.75,'Batches':'rice-batch, beans-batch'},
             {'Item':'1','Quantity':'20 g','Regular (USD)':.15,'Savings (USD)':0,'Payable (USD)':.15,'Batches':''},
             {'Item':'3','Quantity':'180 g','Regular (USD)':.49,'Savings (USD)':0,'Payable (USD)':.49,'Batches':''},
             {'Item':'4','Quantity':'120 g','Regular (USD)':.11,'Savings (USD)':0,'Payable (USD)':.11,'Batches':''}]
        lines=consolidate_cart_lines(raw,{'1':120,'2':100,'3':180,'4':120},{'1':.77,'2':.29,'3':.27,'4':.09},{1:'Brown rice',2:'Black beans',3:'White beans',4:'White rice'})
        self.assertEqual(len(lines),4)
        self.assertEqual(len({r['Item'] for r in lines}),4)
        self.assertEqual(lines[0]['Quantity'],'120 g')
        self.assertEqual(lines[0]['Regular (USD)'],.92)
        self.assertEqual(lines[0]['Batches'],'rice-batch')
        for key in ['Regular (USD)','Savings (USD)','Payable (USD)']:
            self.assertAlmostEqual(sum(r[key] for r in lines),sum(r[key] for r in raw))
        self.assertEqual(lines[2]['Savings (USD)'],0)
        for row in lines:self.assertAlmostEqual(row['Regular (USD)']-row['Savings (USD)'],row['Payable (USD)'])
