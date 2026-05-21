import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'donasi.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            target_amount REAL NOT NULL,
            collected_amount REAL DEFAULT 0,
            image_filename TEXT,
            category TEXT DEFAULT 'Umum',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            donor_name TEXT NOT NULL,
            donor_email TEXT NOT NULL,
            amount REAL NOT NULL,
            message TEXT,
            payment_method TEXT DEFAULT 'Transfer Bank',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
        );
    ''')

    # Seed data kampanye awal jika belum ada
    existing = cursor.execute('SELECT COUNT(*) FROM campaigns').fetchone()[0]
    if existing == 0:
        seed_campaigns = [
            (
                'Bantu Korban Banjir Kalimantan',
                'Ribuan warga terdampak banjir bandang di Kalimantan Selatan membutuhkan bantuan segera berupa makanan, pakaian, dan tempat tinggal sementara.',
                50000000, 23500000, None, 'Bencana Alam'
            ),
            (
                'Beasiswa Anak Yatim Piatu',
                'Membantu 100 anak yatim piatu agar dapat melanjutkan pendidikan hingga SMA. Setiap donasi Anda adalah harapan bagi masa depan mereka.',
                30000000, 18750000, None, 'Pendidikan'
            ),
            (
                'Renovasi Masjid Desa Terpencil',
                'Masjid satu-satunya di Desa Sukamaju Pedalaman sudah sangat rusak. Kami butuh bantuan untuk merenovasi agar ibadah tetap berjalan.',
                20000000, 9200000, None, 'Keagamaan'
            ),
        ]
        cursor.executemany(
            'INSERT INTO campaigns (title, description, target_amount, collected_amount, image_filename, category) VALUES (?,?,?,?,?,?)',
            seed_campaigns
        )

    conn.commit()
    conn.close()

# ── Campaign Queries ──────────────────────────────────────────────────────────

def get_all_campaigns():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM campaigns WHERE is_active=1 ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return rows

def get_campaign_by_id(campaign_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM campaigns WHERE id=?', (campaign_id,)).fetchone()
    conn.close()
    return row

def create_campaign(title, description, target_amount, image_filename, category):
    conn = get_db()
    conn.execute(
        'INSERT INTO campaigns (title, description, target_amount, image_filename, category) VALUES (?,?,?,?,?)',
        (title, description, target_amount, image_filename, category)
    )
    conn.commit()
    conn.close()

def update_campaign_amount(campaign_id, amount):
    conn = get_db()
    conn.execute(
        'UPDATE campaigns SET collected_amount = collected_amount + ? WHERE id=?',
        (amount, campaign_id)
    )
    conn.commit()
    conn.close()

def delete_campaign(campaign_id):
    conn = get_db()
    conn.execute('UPDATE campaigns SET is_active=0 WHERE id=?', (campaign_id,))
    conn.commit()
    conn.close()

# ── Donation Queries ──────────────────────────────────────────────────────────

def create_donation(campaign_id, donor_name, donor_email, amount, message, payment_method):
    conn = get_db()
    cursor = conn.execute(
        '''INSERT INTO donations (campaign_id, donor_name, donor_email, amount, message, payment_method)
           VALUES (?,?,?,?,?,?)''',
        (campaign_id, donor_name, donor_email, amount, message, payment_method)
    )
    donation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return donation_id

def confirm_donation(donation_id):
    conn = get_db()
    donation = conn.execute('SELECT * FROM donations WHERE id=?', (donation_id,)).fetchone()
    if donation and donation['status'] == 'pending':
        conn.execute('UPDATE donations SET status=? WHERE id=?', ('confirmed', donation_id))
        conn.commit()
        conn.close()
        update_campaign_amount(donation['campaign_id'], donation['amount'])
        return True
    conn.close()
    return False

def get_donations_by_campaign(campaign_id):
    conn = get_db()
    rows = conn.execute(
        '''SELECT * FROM donations WHERE campaign_id=? AND status="confirmed"
           ORDER BY created_at DESC''',
        (campaign_id,)
    ).fetchall()
    conn.close()
    return rows

def get_all_donations():
    conn = get_db()
    rows = conn.execute(
        '''SELECT d.*, c.title as campaign_title
           FROM donations d
           JOIN campaigns c ON d.campaign_id = c.id
           ORDER BY d.created_at DESC'''
    ).fetchall()
    conn.close()
    return rows

def get_stats():
    conn = get_db()
    total_campaigns = conn.execute('SELECT COUNT(*) FROM campaigns WHERE is_active=1').fetchone()[0]
    total_donations = conn.execute('SELECT COUNT(*) FROM donations WHERE status="confirmed"').fetchone()[0]
    total_amount = conn.execute('SELECT COALESCE(SUM(amount),0) FROM donations WHERE status="confirmed"').fetchone()[0]
    total_donors = conn.execute('SELECT COUNT(DISTINCT donor_email) FROM donations WHERE status="confirmed"').fetchone()[0]
    conn.close()
    return {
        'total_campaigns': total_campaigns,
        'total_donations': total_donations,
        'total_amount': total_amount,
        'total_donors': total_donors,
    }