import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import db

app = Flask(__name__)
app.secret_key = 'donasi-secret-key-2024'

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_rupiah(amount):
    return f"Rp {amount:,.0f}".replace(',', '.')

app.jinja_env.filters['rupiah'] = format_rupiah

# ── Halaman Utama ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    campaigns = db.get_all_campaigns()
    stats = db.get_stats()
    return render_template('index.html', campaigns=campaigns, stats=stats)

# ── Kampanye ──────────────────────────────────────────────────────────────────

@app.route('/campaign/<int:campaign_id>')
def campaign_detail(campaign_id):
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        flash('Kampanye tidak ditemukan.', 'error')
        return redirect(url_for('index'))
    donations = db.get_donations_by_campaign(campaign_id)
    progress = min(int((campaign['collected_amount'] / campaign['target_amount']) * 100), 100) if campaign['target_amount'] > 0 else 0
    return render_template('campaign_detail.html', campaign=campaign, donations=donations, progress=progress)

@app.route('/campaign/new', methods=['GET', 'POST'])
def new_campaign():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        target_amount = request.form.get('target_amount', 0)
        category = request.form.get('category', 'Umum')
        image_filename = None

        if not title or not description or not target_amount:
            flash('Semua field wajib diisi.', 'error')
            return render_template('new_campaign.html')

        try:
            target_amount = float(target_amount)
            if target_amount <= 0:
                raise ValueError
        except ValueError:
            flash('Target donasi harus berupa angka positif.', 'error')
            return render_template('new_campaign.html')

        # Upload gambar
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                image_filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        db.create_campaign(title, description, target_amount, image_filename, category)
        flash('Kampanye berhasil dibuat!', 'success')
        return redirect(url_for('index'))

    return render_template('new_campaign.html')

@app.route('/campaign/<int:campaign_id>/delete', methods=['POST'])
def delete_campaign(campaign_id):
    db.delete_campaign(campaign_id)
    flash('Kampanye berhasil dihapus.', 'success')
    return redirect(url_for('index'))

# ── Donasi ────────────────────────────────────────────────────────────────────

@app.route('/donate/<int:campaign_id>', methods=['GET', 'POST'])
def donate(campaign_id):
    campaign = db.get_campaign_by_id(campaign_id)
    if not campaign:
        flash('Kampanye tidak ditemukan.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        donor_name = request.form.get('donor_name', '').strip()
        donor_email = request.form.get('donor_email', '').strip()
        amount = request.form.get('amount', 0)
        message = request.form.get('message', '').strip()
        payment_method = request.form.get('payment_method', 'Transfer Bank')

        if not donor_name or not donor_email or not amount:
            flash('Nama, email, dan jumlah donasi wajib diisi.', 'error')
            return render_template('donate.html', campaign=campaign)

        try:
            amount = float(amount)
            if amount < 1000:
                raise ValueError
        except ValueError:
            flash('Jumlah donasi minimal Rp 1.000.', 'error')
            return render_template('donate.html', campaign=campaign)

        donation_id = db.create_donation(campaign_id, donor_name, donor_email, amount, message, payment_method)
        return redirect(url_for('payment_confirmation', donation_id=donation_id))

    return render_template('donate.html', campaign=campaign)

@app.route('/payment/<int:donation_id>', methods=['GET', 'POST'])
def payment_confirmation(donation_id):
    conn = db.get_db()
    donation = conn.execute(
        '''SELECT d.*, c.title as campaign_title
           FROM donations d JOIN campaigns c ON d.campaign_id=c.id
           WHERE d.id=?''', (donation_id,)
    ).fetchone()
    conn.close()

    if not donation:
        flash('Data donasi tidak ditemukan.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        success = db.confirm_donation(donation_id)
        if success:
            flash('Pembayaran dikonfirmasi! Terima kasih atas donasi Anda.', 'success')
            return redirect(url_for('thank_you', donation_id=donation_id))
        else:
            flash('Donasi sudah dikonfirmasi sebelumnya.', 'info')

    return render_template('payment_confirmation.html', donation=donation)

@app.route('/thank-you/<int:donation_id>')
def thank_you(donation_id):
    conn = db.get_db()
    donation = conn.execute(
        '''SELECT d.*, c.title as campaign_title
           FROM donations d JOIN campaigns c ON d.campaign_id=c.id
           WHERE d.id=?''', (donation_id,)
    ).fetchone()
    conn.close()
    if not donation:
        return redirect(url_for('index'))
    return render_template('thank_you.html', donation=donation)

# ── Admin / Semua Donasi ──────────────────────────────────────────────────────

@app.route('/admin')
def admin():
    donations = db.get_all_donations()
    campaigns = db.get_all_campaigns()
    stats = db.get_stats()
    return render_template('admin.html', donations=donations, campaigns=campaigns, stats=stats)

# ── Static Upload ─────────────────────────────────────────────────────────────

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    db.init_db()
    app.run(debug=True)