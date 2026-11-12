import csv
import io
import os
import secrets
import sqlite3
from datetime import timedelta
from pathlib import Path
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32), DATABASE=os.environ.get('DATABASE', 'data/logistics.db'), ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD'), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1', PERMANENT_SESSION_LIFETIME=timedelta(hours=8), MAX_CONTENT_LENGTH=1024*1024)
    if config:
        app.config.update(config)
    if os.environ.get('TRUST_PROXY') == '1':
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    if not app.config['ADMIN_PASSWORD']:
        raise RuntimeError('ADMIN_PASSWORD muhit o‘zgaruvchisini belgilang')
    password_hash = generate_password_hash(app.config['ADMIN_PASSWORD'])

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=15)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db().executescript(Path(app.root_path, 'schema.sql').read_text(encoding='utf-8'))
        db().execute('PRAGMA journal_mode=WAL')
        db().commit()

    @app.before_request
    def protect():
        session.setdefault('csrf', secrets.token_hex(24))
        if request.method == 'POST' and not secrets.compare_digest(session['csrf'], request.form.get('csrf', '')):
            abort(400)
        if request.endpoint not in ('login', 'static', 'health') and not session.get('user'):
            return redirect(url_for('login'))

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'"
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.template_filter('money')
    def money(value):
        return f'{value:,.0f}'.replace(',', ' ')

    @app.context_processor
    def shared():
        return dict(csrf=session.get('csrf'), statuses=['Yangi','Yolda','Yetkazildi','Bekor qilindi'])

    def text(key, limit=100):
        value = request.form.get(key, '').strip()
        if not value or len(value) > limit:
            raise ValueError('Maydonlarni to‘liq va belgilangan uzunlikda kiriting')
        return value

    def integer(key, minimum=0, maximum=1000000000):
        try:
            value = int(request.form.get(key, ''))
        except ValueError:
            raise ValueError('Sonli maydonlarni tekshiring')
        if not minimum <= value <= maximum:
            raise ValueError('Son ruxsat etilgan oraliqda emas')
        return value

    def mutate(action, page):
        try:
            db().execute('BEGIN IMMEDIATE')
            action()
            db().commit()
            flash('Saqlandi', 'ok')
        except (ValueError, sqlite3.IntegrityError) as error:
            db().rollback()
            flash(str(error) if isinstance(error, ValueError) else 'Takroriy yoki mavjud bo‘lmagan ma’lumot. Qiymatlarni tekshiring.', 'error')
        return redirect(url_for(page))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            if check_password_hash(password_hash, request.form.get('password', '')):
                session.clear()
                session.update(user='admin', csrf=secrets.token_hex(24))
                session.permanent = True
                return redirect(url_for('dashboard'))
            flash('Parol noto‘g‘ri', 'error')
        return render_template('login.html')

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/health')
    def health():
        db().execute('SELECT 1')
        return {'status':'ok'}

    @app.get('/')
    def dashboard():
        stats = dict(products=db().execute('SELECT COUNT(*) FROM products').fetchone()[0], stock=db().execute('SELECT COALESCE(SUM(stock*price),0) FROM products').fetchone()[0], active=db().execute("SELECT COUNT(*) FROM orders WHERE status IN ('Yangi','Yolda')").fetchone()[0], delivered=db().execute("SELECT COUNT(*) FROM orders WHERE status='Yetkazildi'").fetchone()[0])
        low = db().execute('SELECT * FROM products WHERE stock<=minimum ORDER BY stock').fetchall()
        recent = db().execute('SELECT * FROM orders ORDER BY id DESC LIMIT 6').fetchall()
        bars = db().execute('SELECT status, COUNT(*) AS n FROM orders GROUP BY status').fetchall()
        return render_template('dashboard.html', stats=stats, low=low, recent=recent, bars=bars)

    @app.route('/suppliers', methods=['GET','POST'])
    def suppliers():
        if request.method == 'POST':
            def save():
                db().execute('INSERT INTO suppliers(name,phone,city) VALUES(?,?,?)', (text('name'), text('phone',30), text('city')))
            return mutate(save, 'suppliers')
        return render_template('suppliers.html', rows=db().execute('SELECT * FROM suppliers ORDER BY id DESC').fetchall())

    @app.route('/products', methods=['GET','POST'])
    def products():
        if request.method == 'POST':
            def save():
                sku, name, supplier, price, minimum, stock = text('sku',30), text('name'), integer('supplier_id',1), integer('price'), integer('minimum'), integer('stock')
                cur = db().execute('INSERT INTO products(sku,name,supplier_id,price,minimum,stock) VALUES(?,?,?,?,?,?)',(sku,name,supplier,price,minimum,stock))
                if stock:
                    db().execute("INSERT INTO stock_movements(product_id,quantity,reason) VALUES(?,?,'Boshlang‘ich qoldiq')",(cur.lastrowid,stock))
            return mutate(save,'products')
        q=request.args.get('q','').strip()[:100]
        rows=db().execute('SELECT p.*,s.name AS supplier FROM products p JOIN suppliers s ON s.id=p.supplier_id WHERE p.name LIKE ? OR p.sku LIKE ? ORDER BY p.id DESC',('%'+q+'%','%'+q+'%')).fetchall()
        return render_template('products.html', rows=rows, suppliers=db().execute('SELECT * FROM suppliers').fetchall(), q=q)

    @app.post('/stock')
    def stock():
        def save():
            pid, qty, reason = integer('product_id',1),integer('quantity',1,1000000),text('reason')
            if not db().execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,pid)).rowcount:
                raise ValueError('Mahsulot topilmadi')
            db().execute('INSERT INTO stock_movements(product_id,quantity,reason) VALUES(?,?,?)',(pid,qty,reason))
        return mutate(save,'products')

    @app.route('/orders', methods=['GET','POST'])
    def orders():
        if request.method=='POST':
            def save():
                customer,destination=text('customer'),text('destination',200)
                ids=request.form.getlist('product_id')
                quantities=request.form.getlist('quantity')
                if len(ids)!=len(quantities) or not 1<=len(ids)<=20:
                    raise ValueError('Buyurtma tarkibini tekshiring')
                items={}
                for pid, qty in zip(ids,quantities):
                    try:
                        pid,qty=int(pid),int(qty)
                    except ValueError:
                        raise ValueError('Mahsulot va miqdorni tekshiring')
                    if qty<1 or qty>1000000:
                        raise ValueError('Miqdor musbat bo‘lishi kerak')
                    items[pid]=items.get(pid,0)+qty
                oid=db().execute('INSERT INTO orders(customer,destination) VALUES(?,?)',(customer,destination)).lastrowid
                for pid,qty in items.items():
                    product=db().execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
                    if not product or product['stock']<qty:
                        raise ValueError('Omborda yetarli mahsulot yo‘q')
                    db().execute('UPDATE products SET stock=stock-? WHERE id=?',(qty,pid))
                    db().execute('INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES(?,?,?,?)',(oid,pid,qty,product['price']))
                    db().execute("INSERT INTO stock_movements(product_id,order_id,quantity,reason) VALUES(?,?,?,'Buyurtmaga ajratildi')",(pid,oid,-qty))
            return mutate(save,'orders')
        status=request.args.get('status','')
        rows=db().execute('SELECT o.*,SUM(i.quantity*i.unit_price) AS total FROM orders o JOIN order_items i ON o.id=i.order_id WHERE (?=\'\' OR o.status=?) GROUP BY o.id ORDER BY o.id DESC',(status,status)).fetchall()
        return render_template('orders.html',rows=rows,products=db().execute('SELECT * FROM products ORDER BY name').fetchall(),selected=status)

    @app.get('/orders/<int:oid>')
    def order_detail(oid):
        order=db().execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
        if not order:
            abort(404)
        items=db().execute('SELECT i.*,p.name,p.sku FROM order_items i JOIN products p ON p.id=i.product_id WHERE order_id=?',(oid,)).fetchall()
        shipment=db().execute('SELECT * FROM shipments WHERE order_id=?',(oid,)).fetchone()
        return render_template('detail.html',order=order,items=items,shipment=shipment,total=sum(i['quantity']*i['unit_price'] for i in items))

    @app.post('/orders/<int:oid>/status')
    def change_status(oid):
        def save():
            order=db().execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
            target=request.form.get('status')
            allowed={'Yangi':['Yolda','Bekor qilindi'],'Yolda':['Yetkazildi'],'Yetkazildi':[],'Bekor qilindi':[]}
            if not order or target not in allowed[order['status']]:
                raise ValueError('Bu holatga o‘tish mumkin emas')
            if target=='Yolda':
                db().execute('INSERT INTO shipments(order_id,driver,vehicle) VALUES(?,?,?)',(oid,text('driver'),text('vehicle',30)))
            elif target=='Yetkazildi':
                db().execute("UPDATE shipments SET delivered_at=strftime('%Y-%m-%d %H:%M','now') WHERE order_id=?",(oid,))
            elif target=='Bekor qilindi':
                for item in db().execute('SELECT * FROM order_items WHERE order_id=?',(oid,)).fetchall():
                    db().execute('UPDATE products SET stock=stock+? WHERE id=?',(item['quantity'],item['product_id']))
                    db().execute("INSERT INTO stock_movements(product_id,order_id,quantity,reason) VALUES(?,?,?,'Buyurtma bekor qilindi')",(item['product_id'],oid,item['quantity']))
            db().execute('UPDATE orders SET status=? WHERE id=?',(target,oid))
        return mutate(save,'orders')

    @app.get('/movements')
    def movements():
        rows=db().execute('SELECT m.*,p.name,p.sku FROM stock_movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC LIMIT 300').fetchall()
        return render_template('movements.html',rows=rows)

    @app.get('/export')
    def export():
        stream=io.StringIO()
        writer=csv.writer(stream)
        writer.writerow(['SKU','Mahsulot','Yetkazib beruvchi','Narx UZS','Qoldiq','Minimal qoldiq'])
        for row in db().execute('SELECT p.sku,p.name,s.name,p.price,p.stock,p.minimum FROM products p JOIN suppliers s ON s.id=p.supplier_id ORDER BY p.id'):
            writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in row])
        return Response('\ufeff'+stream.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=ombor.csv'})

    @app.cli.command('seed')
    def seed():
        if db().execute('SELECT COUNT(*) FROM suppliers').fetchone()[0]:
            print('Ma’lumotlar mavjud. Namuna qo‘shilmadi.')
            return
        with db():
            db().executemany('INSERT INTO suppliers(name,phone,city) VALUES(?,?,?)',[('Vodiy Savdo','+998 90 000 00 01','Andijon'),('Poytaxt Ta’minot','+998 90 000 00 02','Toshkent'),('Farg‘ona Qadoq','+998 90 000 00 03','Farg‘ona')])
            for sku,name,sid,price,qty,minimum in [('QG-01','Qadoqlash qutisi',3,12000,85,15),('KB-02','USB kabel',1,25000,40,10),('RT-03','Wi-Fi router',2,280000,8,10),('FL-04','USB xotira 64 GB',1,75000,30,8),('SK-05','Skaner',2,850000,4,5),('LP-06','Yopishqoq lenta',3,18000,70,20)]:
                pid=db().execute('INSERT INTO products(sku,name,supplier_id,price,stock,minimum) VALUES(?,?,?,?,?,?)',(sku,name,sid,price,qty,minimum)).lastrowid
                db().execute("INSERT INTO stock_movements(product_id,quantity,reason) VALUES(?,?,'Namuna boshlang‘ich qoldiq')",(pid,qty))
        print('Namuna ma’lumotlar yuklandi.')

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1',port=8080)
