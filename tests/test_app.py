import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from app import create_app


class LogisticsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path.cwd())
        self.path=str(Path(self.temp.name)/'test.db')
        self.app=create_app({'TESTING':True,'DATABASE':self.path,'SECRET_KEY':'test-key','ADMIN_PASSWORD':'test-password'})
        self.client=self.app.test_client()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO suppliers(name,city) VALUES('Supplier','Andijon')")
            db.execute("INSERT INTO products(sku,name,supplier_id,price,stock,minimum) VALUES('P1','Product',1,2000,10,2)")
            db.execute("INSERT INTO stock_movements(product_id,quantity,reason) VALUES(1,10,'Opening')")
        self.client.get('/login')
        self.post('/login',password='test-password')

    def tearDown(self):
        self.temp.cleanup()

    def post(self,url,**values):
        with self.client.session_transaction() as state:
            values['csrf']=state['csrf']
        return self.client.post(url,data=values,follow_redirects=True)

    def scalar(self,sql):
        with closing(sqlite3.connect(self.path)) as db, db:
            return db.execute(sql).fetchone()[0]

    def order(self,qty='3'):
        return self.post('/orders',customer='Customer',destination='Andijon',product_id='1',quantity=qty)

    def test_cancel_restores_stock_once(self):
        self.order()
        self.assertEqual(self.scalar('SELECT stock FROM products'),7)
        self.post('/orders/1/status',status='Bekor qilindi')
        self.post('/orders/1/status',status='Bekor qilindi')
        self.assertEqual(self.scalar('SELECT stock FROM products'),10)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM stock_movements'),3)

    def test_insufficient_stock_rolls_back(self):
        self.order('11')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM orders'),0)
        self.assertEqual(self.scalar('SELECT stock FROM products'),10)

    def test_duplicate_lines_are_aggregated(self):
        self.post('/orders',customer='Customer',destination='Andijon',product_id=['1','1'],quantity=['4','7'])
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM orders'),0)
        self.assertEqual(self.scalar('SELECT stock FROM products'),10)

    def test_multiple_products_rollback_together(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO products(sku,name,supplier_id,price,stock) VALUES('P2','Other',1,1000,1)")
        self.post('/orders',customer='Customer',destination='Andijon',product_id=['1','2'],quantity=['3','2'])
        self.assertEqual(self.scalar('SELECT stock FROM products WHERE id=1'),10)
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM orders'),0)

    def test_shipping_state_machine(self):
        self.order()
        self.post('/orders/1/status',status='Yetkazildi')
        self.assertEqual(self.scalar('SELECT status FROM orders'),'Yangi')
        self.post('/orders/1/status',status='Yolda',driver='Ali',vehicle='60A123AA')
        self.post('/orders/1/status',status='Bekor qilindi')
        self.assertEqual(self.scalar('SELECT status FROM orders'),'Yolda')
        self.post('/orders/1/status',status='Yetkazildi')
        self.assertIsNotNone(self.scalar('SELECT delivered_at FROM shipments'))
        self.assertEqual(self.scalar('SELECT stock FROM products'),7)

    def test_csrf_and_authentication(self):
        self.assertEqual(self.client.post('/suppliers',data={'name':'Bad'}).status_code,400)
        self.post('/logout')
        self.assertEqual(self.client.get('/export').status_code,302)
        self.post('/login',password='wrong')
        self.assertEqual(self.client.get('/products').status_code,302)

    def test_all_pages_render_and_escape_html(self):
        self.order()
        for url in ['/','/products','/products?q=Product','/suppliers','/orders','/orders?status=Yangi','/orders/1','/movements','/export','/health']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.post('/suppliers',name='<script>alert(1)</script>',phone='123',city='City')
        html=self.client.get('/suppliers').get_data(as_text=True)
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('&lt;script&gt;',html)

    def test_stock_and_validation(self):
        self.post('/stock',product_id='1',quantity='5',reason='Delivery')
        self.post('/stock',product_id='1',quantity='-1',reason='Invalid')
        self.assertEqual(self.scalar('SELECT stock FROM products'),15)
        self.post('/products',sku='P1',name='Duplicate',supplier_id='1',price='100',minimum='2',stock='2')
        self.assertEqual(self.scalar('SELECT COUNT(*) FROM products'),1)

    def test_price_snapshot_and_restart(self):
        self.order()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE products SET price=9000')
        self.assertEqual(self.scalar('SELECT unit_price FROM order_items'),2000)
        other=create_app({'TESTING':True,'DATABASE':self.path,'ADMIN_PASSWORD':'another'})
        self.assertEqual(other.test_client().get('/health').status_code,200)
        self.assertEqual(self.scalar('SELECT stock FROM products'),7)


if __name__=='__main__':
    unittest.main()
