from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, Response, abort
import os, json, random, uuid
import pandas as pd
import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash# ----------  keep the old helpers + add the new mapper ----------
from career_report_generator import (
    calculate_attribute_scores,
    generate_career_blueprint_report,
    map_assessment_to_report          # <-- NEW
)
# -----------------------------------------------------------------
from job_scraper import get_latest_jobs
# app.py
import os, json, random, uuid
import pandas as pd
import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash



BASE_DIR = os.path.dirname(__file__)
ATTEMPTS_DIR = os.path.join(BASE_DIR, 'attempts')
SITE_DIR = os.path.join(BASE_DIR, 'site')
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
EXCEL_FILE = os.path.join(BASE_DIR, 'Sample Assessment questions.xlsx')

import os, zipfile, io, glob
from flask import send_file

# ----------  folder-level paths ----------
CAREER_DIR    = os.path.join(BASE_DIR, 'data', 'careers')
CONTACT_DIR   = os.path.join(BASE_DIR, 'data', 'contacts')
os.makedirs(CAREER_DIR, exist_ok=True)
os.makedirs(CONTACT_DIR, exist_ok=True)

CAREER_EXCEL  = os.path.join(CAREER_DIR, 'careers.xlsx')
CONTACT_EXCEL = os.path.join(CONTACT_DIR, 'contacts.xlsx')

app = Flask(__name__, static_folder=None, template_folder='templates')
# Production-ready defaults
app.secret_key = 'unicorn-secret-please-change'
app.config['DEBUG'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_PERMANENT'] = False

# ----------  CONTACT-FORM  ----------
import os, pandas as pd                      # already at top of file
from datetime import datetime                # already at top of file

CONTACT_DIR   = os.path.join(BASE_DIR, 'data')
CONTACT_FILE  = os.path.join(CONTACT_DIR, 'contacts.xlsx')
os.makedirs(CONTACT_DIR, exist_ok=True)

import io, os, pandas as pd
from flask import send_file


@app.route('/blog')
def blog():
    return send_from_directory('site', 'blog.html')

@app.route('/faq')
def faq():
    return send_from_directory('site', 'faq.html')

@app.route('/privacy')
def privacy():
    return send_from_directory('site', 'privacy.html')

@app.route('/terms')
def terms():
    return send_from_directory('site', 'terms.html')


@app.route('/download/careers')
def download_careers_zip():
    """Return entire /data/careers/ folder as zip"""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(CAREER_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name  = os.path.relpath(file_path, CAREER_DIR)   # keep folder structure
                zf.write(file_path, arc_name)
    memory_file.seek(0)
    return send_file(memory_file,
                     mimetype='application/zip',
                     as_attachment=True,
                     download_name='careers_bundle.zip')

@app.route('/download/contacts')
def download_contacts_zip():
    """Return entire /data/contacts/ folder as zip"""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(CONTACT_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name  = os.path.relpath(file_path, CONTACT_DIR)
                zf.write(file_path, arc_name)
    memory_file.seek(0)
    return send_file(memory_file,
                     mimetype='application/zip',
                     as_attachment=True,
                     download_name='contacts_bundle.zip')


@app.route('/download/careers/delete', methods=['POST'])   # or GET if you prefer
def delete_careers():
    """
    ADMIN: purge every career application & uploaded file.
    Keeps the Excel header so the next append still works.
    """
    import os, glob

    # 1. wipe the Excel sheet (keep header only)
    header = ['Full Name','Email','Phone','Position','Trainings',
              'Current CTC','Portfolio','Location','Work Authorization',
              'Salary Expectation','Start Date','Resume Filename',
              'Cover-Letter Filename','Submitted At']
    pd.DataFrame(columns=header).to_excel(CAREER_FILE, index=False)

    # 2. delete every uploaded file in the same folder
    for f in glob.glob(os.path.join(CAREER_DIR, "RESUME_*")) + \
             glob.glob(os.path.join(CAREER_DIR, "CL_*")):
        try:
            os.remove(f)
        except Exception:
            pass

    return jsonify({'status': 'ok', 'message': 'All career data wiped.'}), 200


@app.route('/download/contacts/delete', methods=['POST'])   # or GET
def delete_contacts():
    """
    ADMIN: purge every contact-form row.
    Keeps header so next append still works.
    """
    import os, glob

    # 1. wipe the Excel sheet (header only)
    header = ['Full Name','Email','Phone','Inquiry Type',
              'Background','Message','Submitted At']
    pd.DataFrame(columns=header).to_excel(CONTACT_FILE, index=False)

    # 2. (optional) delete any uploaded files if you ever add them here
    for f in glob.glob(os.path.join(CONTACT_DIR, "*")):
        if not f.endswith('.xlsx'):          # keep the sheet itself
            try:
                os.remove(f)
            except Exception:
                pass

    return jsonify({'status': 'ok', 'message': 'All contact data wiped.'}), 200

# ============================================================================
# RAZORPAY PAYMENT INTEGRATION
# Copy this entire section and paste it in your app.py after the imports
# ============================================================================

import razorpay

# ----------  RAZORPAY CONFIGURATION ----------
# IMPORTANT: Replace these with your actual Razorpay credentials
# Get them from: https://dashboard.razorpay.com/app/keys
RAZORPAY_KEY_ID = "rzp_live_RRLzuRNwQiqFcR"
RAZORPAY_KEY_SECRET = "1Fct2RgdkxW97AWMTTRYsunC"

# Assessment price in paise (100 paise = 1 INR)
# Currently set to 1 INR (100 paise)
ASSESSMENT_PRICE = int(os.environ.get('ASSESSMENT_PRICE', '100'))  # ₹1

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ----------  PAYMENT TRACKING ----------
PAYMENTS_DIR = os.path.join(BASE_DIR, 'payments')
os.makedirs(PAYMENTS_DIR, exist_ok=True)
PAYMENTS_FILE = os.path.join(PAYMENTS_DIR, 'payments.json')


def load_payments():
    """Load payment records"""
    if os.path.exists(PAYMENTS_FILE):
        with open(PAYMENTS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def save_payments(payments):
    """Save payment records"""
    with open(PAYMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(payments, f, indent=2)


def has_user_paid(user_email):
    """Check if user has ever made a successful payment"""
    payments = load_payments()
    user_payments = payments.get(user_email, [])
    return any(p.get('status') == 'captured' for p in user_payments)


def record_payment(user_email, payment_data):
    """Record a payment for a user"""
    payments = load_payments()
    if user_email not in payments:
        payments[user_email] = []
    payments[user_email].append(payment_data)
    save_payments(payments)


# ----------  PAYMENT ROUTES ----------

@app.route('/payment')
def payment():
    """Payment page - shown before first assessment"""
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/payment'))
    
    user_email = session.get('user', {}).get('email')
    
    # Check if user already paid
    if has_user_paid(user_email):
        return redirect('/assessment')
    
    # Render payment page
    return render_template('payment.html', 
                         razorpay_key=RAZORPAY_KEY_ID,
                         amount=ASSESSMENT_PRICE,
                         user_email=user_email,
                         user_name=session.get('user', {}).get('name'))


@app.route('/create_order', methods=['POST'])
def create_order():
    """Create Razorpay order"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    user_email = session.get('user', {}).get('email')
    
    # Check if already paid
    if has_user_paid(user_email):
        return jsonify({'error': 'Already paid'}), 400
    
    try:
        # Create Razorpay order
        order_data = {
            'amount': ASSESSMENT_PRICE,  # amount in paise
            'currency': 'INR',
            'receipt': f'assessment_{user_email}_{uuid.uuid4().hex[:8]}',
            'notes': {
                'user_email': user_email,
                'purpose': 'First Assessment Payment'
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        return jsonify({
            'success': True,
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency']
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

# ---------- TRAINER PROFILE ROUTES ----------
TRAINER_DIR = os.path.join(BASE_DIR, 'data', 'trainers')
os.makedirs(TRAINER_DIR, exist_ok=True)
TRAINER_FILE = os.path.join(TRAINER_DIR, 'trainers.json')

def load_trainers():
    """Load trainer data from JSON file"""
    if os.path.exists(TRAINER_FILE):
        with open(TRAINER_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_trainers(trainers):
    """Save trainer data to JSON file"""
    with open(TRAINER_FILE, 'w', encoding='utf-8') as f:
        json.dump(trainers, f, indent=2)

@app.route('/trainer')
def trainer():
    """Trainer profile page"""
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/trainer'))
    
    user_info = session.get('user', {})
    user_email = user_info.get('email')
    trainers = load_trainers()
    trainer_data = trainers.get(user_email, {})
    
    # Calculate profile completion for trainer
    required_fields = ['first_name', 'last_name', 'phone', 'address', 'dob', 
                      'pan_number', 'aadhaar_number', 'bank_name', 'account_number']
    completed = sum(1 for f in required_fields if trainer_data.get(f))
    profile_completion = int((completed / len(required_fields)) * 100)
    
    return render_template('trainer.html',
                         user_info=user_info,
                         trainer_data=trainer_data,
                         profile_completion=profile_completion)

@app.route('/trainer/update/personal', methods=['POST'])
def update_trainer_personal():
    """Update trainer personal information"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
    # Update personal fields
    updates = {
        'first_name': request.form.get('first_name', '').strip(),
        'last_name': request.form.get('last_name', '').strip(),
        'email': request.form.get('email', '').strip(),
        'phone': request.form.get('phone', '').strip(),
        'address': request.form.get('address', '').strip(),
        'city': request.form.get('city', '').strip(),
        'state': request.form.get('state', '').strip(),
        'pincode': request.form.get('pincode', '').strip(),
        'dob': request.form.get('dob', '').strip(),
        'gender': request.form.get('gender', '').strip(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    trainers[user_email].update({k: v for k, v in updates.items() if v})
    save_trainers(trainers)
    
    return jsonify({'success': True, 'message': 'Personal information updated successfully'})

@app.route('/trainer/update/identification', methods=['POST'])
def update_trainer_identification():
    """Update trainer identification documents"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
    # Update identification fields
    updates = {
        'pan_number': request.form.get('pan_number', '').strip().upper(),
        'pan_name': request.form.get('pan_name', '').strip(),
        'aadhaar_number': request.form.get('aadhaar_number', '').strip(),
        'aadhaar_name': request.form.get('aadhaar_name', '').strip(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    trainers[user_email].update({k: v for k, v in updates.items() if v})
    save_trainers(trainers)
    
    return jsonify({'success': True, 'message': 'Identification details updated successfully'})

@app.route('/trainer/update/banking', methods=['POST'])
def update_trainer_banking():
    """Update trainer banking details"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
    # Validate account numbers match
    account_number = request.form.get('account_number', '').strip()
    confirm_account = request.form.get('confirm_account_number', '').strip()
    
    if account_number != confirm_account:
        return jsonify({'success': False, 'error': 'Account numbers do not match'}), 400
    
    # Update banking fields
    updates = {
        'bank_name': request.form.get('bank_name', '').strip(),
        'account_number': account_number,
        'ifsc_code': request.form.get('ifsc_code', '').strip().upper(),
        'account_type': request.form.get('account_type', '').strip(),
        'account_holder_name': request.form.get('account_holder_name', '').strip(),
        'branch_name': request.form.get('branch_name', '').strip(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    trainers[user_email].update({k: v for k, v in updates.items() if v})
    save_trainers(trainers)
    
    return jsonify({'success': True, 'message': 'Banking details updated successfully'})

@app.route('/trainer/update/qualifications', methods=['POST'])
def update_trainer_qualifications():
    """Save trainer qualifications"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
    # Collect all qualification entries from form
    qualifications = []
    form_data = request.form.to_dict()
    
    # Group by qualification counter
    qual_counters = set()
    for key in form_data.keys():
        if key.startswith('qual_'):
            counter = key.split('_')[-1]
            if counter.isdigit():
                qual_counters.add(counter)
    
    for counter in qual_counters:
        qual = {
            'degree': form_data.get(f'qual_degree_{counter}', ''),
            'specialization': form_data.get(f'qual_specialization_{counter}', ''),
            'institution': form_data.get(f'qual_institution_{counter}', ''),
            'year': form_data.get(f'qual_year_{counter}', ''),
            'grade': form_data.get(f'qual_grade_{counter}', '')
        }
        if any(qual.values()):  # Only add if at least one field has data
            qualifications.append(qual)
    
    trainers[user_email]['qualifications'] = qualifications
    trainers[user_email]['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_trainers(trainers)
    
    return jsonify({'success': True, 'message': 'Qualifications saved successfully'})

@app.route('/trainer/update/employment', methods=['POST'])
def update_trainer_employment():
    """Save trainer employment history"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
    # Collect employment entries
    employment = []
    form_data = request.form.to_dict()
    
    emp_counters = set()
    for key in form_data.keys():
        if key.startswith('emp_'):
            counter = key.split('_')[-1]
            if counter.isdigit():
                emp_counters.add(counter)
    
    for counter in emp_counters:
        emp = {
            'company': form_data.get(f'emp_company_{counter}', ''),
            'title': form_data.get(f'emp_title_{counter}', ''),
            'start_date': form_data.get(f'emp_start_{counter}', ''),
            'end_date': form_data.get(f'emp_end_{counter}', ''),
            'current': form_data.get(f'emp_current_{counter}') == 'on',
            'responsibilities': form_data.get(f'emp_responsibilities_{counter}', '')
        }
        if any([emp['company'], emp['title']]):
            employment.append(emp)
    
    trainers[user_email]['employment'] = employment
    trainers[user_email]['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_trainers(trainers)
    
    return jsonify({'success': True, 'message': 'Employment history saved successfully'})

@app.route('/trainer/update/trainings', methods=['POST'])
def update_trainer_trainings():
    """Save trainings that trainer can provide"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
    # Collect training courses
    trainings = []
    form_data = request.form.to_dict()
    
    train_counters = set()
    for key in form_data.keys():
        if key.startswith('train_'):
            counter = key.split('_')[-1]
            if counter.isdigit():
                train_counters.add(counter)
    
    for counter in train_counters:
        training = {
            'name': form_data.get(f'train_name_{counter}', ''),
            'category': form_data.get(f'train_category_{counter}', ''),
            'duration': form_data.get(f'train_duration_{counter}', ''),
            'experience': form_data.get(f'train_experience_{counter}', ''),
            'description': form_data.get(f'train_description_{counter}', ''),
            'prerequisites': form_data.get(f'train_prerequisites_{counter}', '')
        }
        if training['name']:
            trainings.append(training)
    
    trainers[user_email]['trainings'] = trainings
    trainers[user_email]['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_trainers(trainers)
    
    return jsonify({'success': True, 'message': 'Training courses saved successfully'})


@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    """Verify Razorpay payment signature"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    user_email = session.get('user', {}).get('email')
    
    try:
        # Get payment details from request
        payment_id = request.json.get('razorpay_payment_id')
        order_id = request.json.get('razorpay_order_id')
        signature = request.json.get('razorpay_signature')
        
        # Verify signature
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Payment verified - record it
        payment_record = {
            'payment_id': payment_id,
            'order_id': order_id,
            'amount': ASSESSMENT_PRICE,
            'currency': 'INR',
            'status': 'captured',
            'timestamp': datetime.utcnow().isoformat(),
            'user_email': user_email
        }
        
        record_payment(user_email, payment_record)
        
        return jsonify({
            'success': True,
            'message': 'Payment verified successfully',
            'redirect': '/assessment'
        })
    
    except razorpay.errors.SignatureVerificationError:
        return jsonify({'error': 'Payment verification failed'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------  MODIFY EXISTING /assessment ROUTE ----------
# Replace your existing @app.route('/assessment') function with this:

@app.route('/assessment')
def assessment():
    """Start or resume assessment - check payment first"""
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))
    
    user_email = session.get('user', {}).get('email')
    
    # Check if user needs to pay (first time user)
    if not has_user_paid(user_email):
        return redirect('/payment')
    
    # User has paid, proceed with assessment
    os.makedirs(ATTEMPTS_DIR, exist_ok=True)
    attempt_id = session.get('attempt_id')
    attempt_path = os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json") if attempt_id else None

    if not attempt_id or not os.path.exists(attempt_path):
        qs = load_questions()
        random.shuffle(qs)
        for q in qs:
            random.shuffle(q['Options'])
        attempt_id = uuid.uuid4().hex
        attempt = {
            'id': attempt_id,
            'user': user_email,
            'start': datetime.utcnow().isoformat(),
            'questions': qs,
            'submitted': False,
            'results': None,
            'answers': {}
        }
        with open(os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json"), 'w', encoding='utf-8') as f:
            json.dump(attempt, f)
        session['attempt_id'] = attempt_id
    else:
        with open(attempt_path, 'r', encoding='utf-8') as f:
            attempt = json.load(f)
        start = datetime.fromisoformat(attempt['start'])
        if datetime.utcnow() - start > timedelta(minutes=30):
            try:
                os.remove(attempt_path)
            except Exception:
                pass
            session.pop('attempt_id', None)
            session.clear()
            return redirect(url_for('login', next='/assessment', timeout=1))
    
    return redirect(url_for('assessment_question', idx=0))


# ----------  OPTIONAL: UPDATE PROFILE TO SHOW PAYMENT STATUS ----------
# Add this helper function if it doesn't exist:

def calculate_profile_completion(user_data: dict) -> int:
    required = ['name', 'first_name', 'last_name', 'phone', 'date_of_birth', 'address']
    completed = sum(1 for f in required if user_data.get(f))
    return int((completed / len(required)) * 100)


# Update your existing @app.route('/profile') function:
# Find the line: profile_data = {...}
# And add 'has_paid': has_user_paid(user_email) to it
# Like this:

@app.route('/profile')
def profile():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/profile'))

    user_info = session.get('user', {})
    user_email = user_info.get('email')
    users = load_users()
    user_data = users.get(user_email, {})

    # Get payment status
    has_paid = has_user_paid(user_email)

    # Assessment history
    user_attempts = []
    if os.path.exists(ATTEMPTS_DIR):
        for fname in os.listdir(ATTEMPTS_DIR):
            if not fname.endswith('.json'):
                continue
            try:
                with open(os.path.join(ATTEMPTS_DIR, fname), encoding='utf-8') as f:
                    att = json.load(f)
                    if att.get('user') == user_email and att.get('submitted'):
                        user_attempts.append(att)
            except Exception:
                continue
    user_attempts.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
    total_attempts = len(user_attempts)
    latest_results = user_attempts[0]['results'] if user_attempts else None

    profile_data = {
        'user_info': user_info,
        'user_data': user_data,
        'total_attempts': total_attempts,
        'latest_results': latest_results,
        'attempts_history': user_attempts[:5],
        'join_date': user_data.get('created_at', ''),
        'profile_completion': calculate_profile_completion(user_data),
        'has_paid': has_paid  # Add this line
    }
    return render_template('profile.html', **profile_data)


# ============================================================================
# END OF RAZORPAY INTEGRATION
# ============================================================================

# INSTRUCTIONS:
# 1. Make sure to add 'import razorpay' at the top of your app.py with other imports
# 2. Install razorpay: pip install razorpay==1.4.2
# 3. Set your Razorpay keys:
#    - Windows: set RAZORPAY_KEY_ID=rzp_test_xxxxx
#    - Linux/Mac: export RAZORPAY_KEY_ID='rzp_test_xxxxx'
# 4. Or directly replace 'rzp_test_xxxxxxxxxxxxx' above with your actual key
# 5. Price is currently set to ₹1 (100 paise)
# 6. Test with card: 4111 1111 1111 1111, CVV: 123, Expiry: any future date

@app.route('/contact', methods=['POST'])
def save_contact():
    """Store contact-form data into /data/contacts/"""
    fullName     = request.form.get('fullName', '').strip()
    email        = request.form.get('email', '').strip()
    phone        = request.form.get('phone', '').strip()
    inquiryType  = request.form.get('inquiryType', '')
    background   = request.form.get('background', '')
    message      = request.form.get('message', '')

    row = {
        'Full Name': fullName,
        'Email': email,
        'Phone': phone,
        'Inquiry Type': inquiryType,
        'Background': background,
        'Message': message,
        'Submitted At': datetime.utcnow()
    }

    if not os.path.exists(CONTACT_EXCEL):
        pd.DataFrame([row]).to_excel(CONTACT_EXCEL, index=False)
    else:
        df = pd.read_excel(CONTACT_EXCEL)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_excel(CONTACT_EXCEL, index=False)

    return '', 200


def strip_tags_func(s):
    """Remove internal tag markers like (FAR), (CRM), (BM), (MO) from display text."""
    if not s:
        return s
    try:
        return re.sub(r'\s*\((?:FAR|CRM|BM|MO)\)\s*', '', str(s))
    except Exception:
        return str(s)

app.jinja_env.filters['strip_tags'] = strip_tags_func

# ----------  CAREER-APPLICATION  ----------
CAREER_DIR   = os.path.join(BASE_DIR, 'data')
CAREER_FILE  = os.path.join(CAREER_DIR, 'careers.xlsx')
os.makedirs(CAREER_DIR, exist_ok=True)

@app.route('/career', methods=['POST'])
def save_career():
    """Store career-application + files into /data/careers/"""
    full_name          = request.form.get('full_name', '').strip()
    email              = request.form.get('email', '').strip()
    phone              = request.form.get('phone', '').strip()
    position           = request.form.get('position', '').strip()
    trainings          = request.form.get('trainings', '').strip()
    current_ctc        = request.form.get('current_ctc', '').strip()
    portfolio          = request.form.get('portfolio', '').strip()
    location           = request.form.get('location', '').strip()
    authorization      = request.form.get('authorization', '').strip()
    salary_expectation = request.form.get('salary_expectation', '').strip()
    start_date         = request.form.get('start_date', '')
    resume_file        = request.files.get('resume_file')
    cover_letter_file  = request.files.get('cover_letter_file')

    row = {
        'Full Name': full_name,
        'Email': email,
        'Phone': phone,
        'Position': position,
        'Trainings': trainings,
        'Current CTC': current_ctc,
        'Portfolio': portfolio,
        'Location': location,
        'Work Authorization': authorization,
        'Salary Expectation': salary_expectation,
        'Start Date': start_date,
        'Resume Filename': resume_file.filename if resume_file else '',
        'Cover-Letter Filename': cover_letter_file.filename if cover_letter_file else '',
        'Submitted At': datetime.utcnow()
    }

    # append Excel
    if not os.path.exists(CAREER_EXCEL):
        pd.DataFrame([row]).to_excel(CAREER_EXCEL, index=False)
    else:
        df = pd.read_excel(CAREER_EXCEL)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_excel(CAREER_EXCEL, index=False)

    # save uploads into CAREER_DIR
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    if resume_file and resume_file.filename:
        resume_file.save(os.path.join(CAREER_DIR, f"RESUME_{ts}_{resume_file.filename}"))
    if cover_letter_file and cover_letter_file.filename:
        cover_letter_file.save(os.path.join(CAREER_DIR, f"CL_{ts}_{cover_letter_file.filename}"))

    return '', 200


# Utility: load/save users
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2)

# Load questions from Excel. Map Option A->FAR, B->BM, C->CRM, D->MO
# Load questions from Excel. Map Option A->FAR, B->BM, C->CRM, D->MO
def load_questions():
    """
    Load questions from Excel and ensure balanced selection:
    - 10 questions from each of the 10 categories
    - Total 100 questions
    """
    if not os.path.exists(EXCEL_FILE):
        return []
    
    df = pd.read_excel(EXCEL_FILE)
    
    # Define all expected categories
    EXPECTED_CATEGORIES = [
        'Accounting Knowledge',
        'Attention to Detail',
        'Business & Economic Acumen',
        'Communication Skills',
        'Compliance & Ethics',
        'Finacial Concepts Skill',
        'Personality Preference',
        'Problem Solving Skills',
        'Quantitative & Math Skill',
        'Tech & Tool Familiarity'
    ]
    
    # Group questions by category
    questions_by_category = {cat: [] for cat in EXPECTED_CATEGORIES}
    
    for idx, row in df.iterrows():
        # Skip rows with missing required data
        if pd.isna(row.get('No')) or pd.isna(row.get('Scenario')):
            continue
        
        try:
            no = int(row['No'])
        except Exception:
            no = int(idx) + 1
        
        # Parse options with their codes
        opts = []
        mapping = [('Option A', 'FAR'), ('Option B', 'BM'), 
                   ('Option C', 'CRM'), ('Option D', 'MO')]
        for col, code in mapping:
            text = row.get(col)
            if pd.notna(text):
                opts.append({'text': str(text), 'code': code})
        
        # Get category (handle variations in column name)
        category = row.get('Categories/Attributes') or row.get('Categories') or ''
        category = str(category).strip()
        
        # Build question object
        question = {
            'No': no,
            'Scenario': str(row['Scenario']),
            'Options': opts,
            'Category': category
        }
        
        # Add to appropriate category bucket
        if category in questions_by_category:
            questions_by_category[category].append(question)
    
    # Select exactly 10 questions from each category
    selected_questions = []
    warnings = []
    
    for category in EXPECTED_CATEGORIES:
        available = questions_by_category[category]
        
        if len(available) >= 10:
            # Randomly select 10 questions
            selected = random.sample(available, 10)
            selected_questions.extend(selected)
        elif len(available) > 0:
            # Not enough questions - use all available and warn
            selected_questions.extend(available)
            warnings.append(f"Category '{category}': Only {len(available)} questions available (need 10)")
        else:
            warnings.append(f"Category '{category}': No questions found!")
    
    # Log warnings if any
    if warnings:
        print("\nQuestion Selection Warnings:")
        for w in warnings:
            print(f"   - {w}")
        print(f"   Total questions loaded: {len(selected_questions)} (expected 100)\n")
    
    return selected_questions


@app.route('/checkpoint')
def checkpoint():
    """
    TESTING ONLY: Bypass payment requirement
    This should be removed or disabled in production
    """
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/checkpoint'))
    
    user_email = session.get('user', {}).get('email')
    
    # Create a fake payment record to bypass payment check
    fake_payment = {
        'payment_id': 'test_bypass',
        'order_id': 'test_order',
        'amount': ASSESSMENT_PRICE,
        'currency': 'INR',
        'status': 'captured',
        'timestamp': datetime.utcnow().isoformat(),
        'user_email': user_email,
        'note': 'Testing bypass - not a real payment'
    }
    
    record_payment(user_email, fake_payment)
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Checkpoint - Payment Bypassed</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 100px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .card {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .success {{
                color: #28a745;
                font-size: 48px;
                margin-bottom: 20px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
            }}
            p {{
                color: #666;
                margin-bottom: 20px;
            }}
            .btn {{
                display: inline-block;
                padding: 12px 30px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                margin-top: 20px;
            }}
            .btn:hover {{
                background: #0056b3;
            }}
            .warning {{
                background: #fff3cd;
                border: 1px solid #ffc107;
                padding: 15px;
                border-radius: 5px;
                margin-top: 20px;
                color: #856404;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="success">✓</div>
            <h1>Payment Bypassed</h1>
            <p>Testing mode activated for user: <strong>{user_email}</strong></p>
            <p>You can now access the assessment without payment.</p>
            <a href="/assessment" class="btn">Start Assessment</a>
            <div class="warning">
                <strong>⚠️ Testing Mode</strong><br>
                This is a testing bypass. Remove this route in production!
            </div>
        </div>
    </body>
    </html>
    '''


@app.route('/')
def index():
    return send_from_directory(SITE_DIR, 'index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    users = load_users()
    # If someone navigates back to login page, clear the session to force a fresh login
    if request.method == 'GET':
        session.clear()
    if request.method == 'POST':
        email = (request.form.get('email') or '').lower().strip()
        password = request.form.get('password') or ''
        next_url = request.form.get('next') or request.args.get('next') or '/assessment'
        user = users.get(email)
        # check password
        if user and user.get('password') and check_password_hash(user.get('password'), password):
            session['logged_in'] = True
            session['user'] = {'email': email, 'name': user.get('name')}
            return redirect(next_url)
        # also allow login as plain "admin" (legacy)
        if email == 'admin' and password == 'admin':
            session['logged_in'] = True
            session['user'] = {'email': 'admin', 'name': 'Administrator'}
            return redirect(next_url)
        # failed -> send back to login with error flag preserved
        return redirect('/login?error=1' + (f"&next={next_url}" if next_url else ""))
    return send_from_directory(SITE_DIR, 'login.html')

@app.route('/signup', methods=['POST'])
def signup():
    users = load_users()
    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').lower().strip()
    password = request.form.get('password') or ''
    confirm = request.form.get('confirm_password') or ''
    next_url = request.form.get('next') or request.args.get('next') or '/assessment'
    if not email or not password or password != confirm:
        return redirect('/login?error_signup=1' + (f"&next={next_url}" if next_url else ""))
    if email in users:
        return redirect('/login?error_exists=1' + (f"&next={next_url}" if next_url else ""))
    users[email] = {'name': name or email.split('@')[0], 'password': generate_password_hash(password)}
    save_users(users)
    session['logged_in'] = True
    session['user'] = {'email': email, 'name': users[email]['name']}
    return redirect(next_url)


# ----------  helpers  ----------
from datetime import datetime, timezone  # UTC-aware

def load_users():
    import json, os
    USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_users(users):
    import json, os
    USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2)

def calculate_profile_completion(user_data: dict) -> int:
    required = ['name', 'first_name', 'last_name', 'phone', 'date_of_birth', 'address']
    completed = sum(1 for f in required if user_data.get(f))
    return int((completed / len(required)) * 100)

# ----------  routes  ----------
# @app.route('/profile')
# def profile():
#     if not session.get('logged_in'):
#         return redirect(url_for('login', next='/profile'))

#     user_info = session.get('user', {})
#     user_email = user_info.get('email')
#     users = load_users()
#     user_data = users.get(user_email, {})

#     # ---- assessment history ----
#     ATTEMPTS_DIR = os.path.join(os.path.dirname(__file__), 'attempts')
#     user_attempts = []
#     if os.path.exists(ATTEMPTS_DIR):
#         for fname in os.listdir(ATTEMPTS_DIR):
#             if not fname.endswith('.json'):
#                 continue
#             try:
#                 with open(os.path.join(ATTEMPTS_DIR, fname), encoding='utf-8') as f:
#                     att = json.load(f)
#                     if att.get('user') == user_email and att.get('submitted'):
#                         user_attempts.append(att)
#             except Exception:
#                 continue
#     user_attempts.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
#     total_attempts = len(user_attempts)
#     latest_results = user_attempts[0]['results'] if user_attempts else None

#     profile_data = {
#         'user_info': user_info,
#         'user_data': user_data,
#         'total_attempts': total_attempts,
#         'latest_results': latest_results,
#         'attempts_history': user_attempts[:5],
#         'join_date': user_data.get('created_at', ''),
#         'profile_completion': calculate_profile_completion(user_data),
#     }
#     return render_template('profile.html', **profile_data)

# ---- legacy url redirect (optional) ----
@app.route('/profile.html')
def profile_html_redirect():
    return redirect(url_for('profile'), code=301)

# ---- update endpoint ----
@app.route('/profile/update', methods=['POST'])
def update_profile():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    user_email = session['user']['email']
    users = load_users()
    if user_email not in users:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # update fields
    updates = {k: request.form.get(k, '').strip() for k in
               ['first_name', 'last_name', 'phone', 'address',
                'date_of_birth', 'gender', 'bio']}
    updates['updated_at'] = datetime.now(timezone.utc).isoformat()
    users[user_email].update({k: v for k, v in updates.items() if v})

    # rebuild full name
    fname = users[user_email].get('first_name', '')
    lname = users[user_email].get('last_name', '')
    users[user_email]['name'] = f"{fname} {lname}".strip() or users[user_email]['name']
    session['user']['name'] = users[user_email]['name']

    save_users(users)
    return jsonify({'success': True, 'message': 'Profile updated'})

@app.route('/logout')
def logout():
    # clear attempt_id if any
    attempt_id = session.pop('attempt_id', None)
    session.clear()
    # optionally remove attempt file if exists
    if attempt_id:
        try:
            os.remove(os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json"))
        except Exception:
            pass
    return redirect('/')


# @app.route('/assessment')
# def assessment():
#     # start or resume an attempt and redirect to first question
#     if not session.get('logged_in'):
#         return redirect(url_for('login', next='/assessment'))
#     os.makedirs(ATTEMPTS_DIR, exist_ok=True)
#     attempt_id = session.get('attempt_id')
#     attempt_path = os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json") if attempt_id else None

#     if not attempt_id or not os.path.exists(attempt_path):
#         qs = load_questions()
#         random.shuffle(qs)
#         for q in qs:
#             random.shuffle(q['Options'])
#         attempt_id = uuid.uuid4().hex
#         attempt = {
#             'id': attempt_id,
#             'user': session.get('user', {}).get('email'),
#             'start': datetime.utcnow().isoformat(),
#             'questions': qs,
#             'submitted': False,
#             'results': None,
#             'answers': {}
#         }
#         with open(os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json"), 'w', encoding='utf-8') as f:
#             json.dump(attempt, f)
#         session['attempt_id'] = attempt_id
#     else:
#         with open(attempt_path, 'r', encoding='utf-8') as f:
#             attempt = json.load(f)
#         # check timeout (30 minutes)
#         start = datetime.fromisoformat(attempt['start'])
#         if datetime.utcnow() - start > timedelta(minutes=30):
#             try:
#                 os.remove(attempt_path)
#             except Exception:
#                 pass
#             session.pop('attempt_id', None)
#             session.clear()
#             return redirect(url_for('login', next='/assessment', timeout=1))
#     # redirect to first question (or resume at 0)
#     return redirect(url_for('assessment_question', idx=0))

@app.route('/assessment/<int:idx>')
def assessment_question(idx):
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))
    attempt_id = session.get('attempt_id')
    if not attempt_id:
        return redirect(url_for('assessment'))
    attempt_path = os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json")
    if not os.path.exists(attempt_path):
        return redirect(url_for('assessment'))
    with open(attempt_path, 'r', encoding='utf-8') as f:
        attempt = json.load(f)
    # validate idx
    total = len(attempt['questions'])
    if idx < 0 or idx >= total:
        return redirect(url_for('assessment_question', idx=0))
    q = attempt['questions'][idx]
    selected = attempt.get('answers', {}).get(str(q.get('No')), None)
    return render_template('assessment.html', question=q, idx=idx, total=total, selected=selected)

@app.route('/answer', methods=['POST'])
def answer():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))
    attempt_id = session.get('attempt_id')
    if not attempt_id:
        return redirect(url_for('assessment'))
    attempt_path = os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json")
    if not os.path.exists(attempt_path):
        return redirect(url_for('assessment'))
    with open(attempt_path, 'r', encoding='utf-8') as f:
        attempt = json.load(f)
    try:
        qno = request.form.get('qno')
        choice = request.form.get('choice')
        idx = int(request.form.get('idx', '0'))
    except Exception:
        return redirect(url_for('assessment'))
    # store the answer
    if 'answers' not in attempt:
        attempt['answers'] = {}
    attempt['answers'][str(qno)] = choice
    with open(attempt_path, 'w', encoding='utf-8') as f:
        json.dump(attempt, f)
    # go to next question or submit
    total = len(attempt['questions'])
    next_idx = idx + 1
    if next_idx >= total:
        return redirect(url_for('submit'))
    return redirect(url_for('assessment_question', idx=next_idx))


@app.route('/submit', methods=['GET', 'POST'])
def submit():
    """
    Submit the assessment with robust normalization and category-based scoring.
    Fixes issue of repetitive results (always BM+CRM+MO).
    """
    import re
    from datetime import datetime

    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))

    attempt_id = session.get('attempt_id')
    if not attempt_id:
        return redirect('/assessment')

    attempt_path = os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json")
    if not os.path.exists(attempt_path):
        return redirect('/assessment')

    # Load the attempt
    with open(attempt_path, 'r', encoding='utf-8') as f:
        attempt = json.load(f)

    # Check for timeout (30 min)
    start = datetime.fromisoformat(attempt['start'])
    if datetime.utcnow() - start > timedelta(minutes=30):
        try:
            os.remove(attempt_path)
        except Exception:
            pass
        session.clear()
        return redirect(url_for('login', next='/assessment', timeout=1))

    # Get submitted answers
    answers = request.form if request.form else {('q' + k): v for k, v in attempt.get('answers', {}).items()}

    # --- Helper to normalize answer codes ---
    def normalize_choice(raw_val, question):
        """
        Convert answer to standardized code: FAR / BM / CRM / MO.
        Accepts formats: 'A', 'Option A', full text, or direct code.
        """
        if not raw_val:
            return None
        v = str(raw_val).strip()
        if not v:
            return None

        v_u = v.upper()
        if v_u in ('FAR', 'BM', 'CRM', 'MO'):
            return v_u

        # Letter mapping
        letter_map = {'A': 'FAR', 'B': 'BM', 'C': 'CRM', 'D': 'MO'}
        if len(v_u) == 1 and v_u in letter_map:
            return letter_map[v_u]

        # Patterns like "Option A" or "A) text"
        m = re.match(r'^(?:OPTION\s*)?([A-D])\b', v_u)
        if m:
            return letter_map.get(m.group(1))

        # Match option text
        opts = question.get('Options', []) or []
        lower_v = v.strip().lower()
        for opt in opts:
            opt_text = str(opt.get('text', '')).strip().lower()
            opt_code = opt.get('code', '').upper()
            if lower_v == opt_text or lower_v in opt_text:
                return opt_code or None

        return None

    # --- Initialize scoring structures ---
    scores = {'FAR': 0, 'BM': 0, 'CRM': 0, 'MO': 0}
    category_scores = {}  # category -> dict(FAR,BM,CRM,MO)
    debug_rows = []       # for logging / debugging input values

    # --- Process every question ---
    for q in attempt['questions']:
        qno = str(q.get('No'))
        key = f"q{qno}"
        raw_val = answers.get(key) or answers.get(qno)
        normalized = normalize_choice(raw_val, q)

        debug_rows.append({
            'question_no': qno,
            'category': q.get('Category'),
            'raw_value': raw_val,
            'normalized': normalized,
            'options': q.get('Options')
        })

        if not normalized:
            continue

        # Increment overall scores
        scores[normalized] = scores.get(normalized, 0) + 1

        # Category-level breakdown
        category = q.get('Category', 'Unknown').strip() or 'Unknown'
        if category not in category_scores:
            category_scores[category] = {'FAR': 0, 'BM': 0, 'CRM': 0, 'MO': 0}
        category_scores[category][normalized] += 1

    # Identify strongest dimension
    strongest = max(scores, key=scores.get) if any(scores.values()) else None

    # Compute higher-level attributes (if supported)
    attributes = calculate_attribute_scores(scores)

    # Attach results + debug info to attempt
    attempt['submitted'] = True
    attempt['submitted_at'] = datetime.utcnow().isoformat()
    attempt['results'] = {
        'scores': scores,
        'category_breakdown': category_scores,
        'strongest': strongest,
        'attributes': attributes
    }
    attempt['debug_submission'] = {
        'checked_at': datetime.utcnow().isoformat(),
        'debug_rows': debug_rows
    }

    # Save updated attempt
    with open(attempt_path, 'w', encoding='utf-8') as f:
        json.dump(attempt, f, indent=2)

    # Mark submission complete
    session['last_attempt_id'] = attempt_id
    session.pop('attempt_id', None)

    return redirect('/results')



# ------------------------------------------------------------------
#  NEW : dynamic Word-style report mapping  (no more hard-coded text)
# ------------------------------------------------------------------
# ------------------------------------------------------------------
#  NEW : dynamic Word-style report mapping  (no more hard-coded text)
# ------------------------------------------------------------------
@app.route('/results')
def results():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))

    last_id = session.get('last_attempt_id')
    if not last_id:
        return "No results available. Please take the assessment.", 400

    attempt_path = os.path.join(ATTEMPTS_DIR, f"{last_id}.json")
    if not os.path.exists(attempt_path):
        return "Results not found.", 404

    with open(attempt_path, 'r', encoding='utf-8') as f:
        attempt = json.load(f)
    if not attempt.get('results'):
        return "No results yet.", 400

    # 1. legacy data (kept for old template parts if any)
    results_data = attempt['results']
    attributes   = results_data.get('attributes', {})

    # 2. NEW : compute the Word-style skeleton from raw scores
    report_context = map_assessment_to_report(results_data['scores'])

    # 3. merge both dicts and render
    return render_template('results.html',
                         results=results_data['scores'],
                         strongest=results_data['strongest'],
                         attributes=attributes,
                         **report_context)          # <-- contains track_name, swot_*,
                                                     #     career_path, industry_trends…

@app.route('/download_career_blueprint')
def download_career_blueprint():
    """Generate and download the Career Strengths Blueprint report as Markdown"""
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))
    
    last_id = session.get('last_attempt_id')
    if not last_id:
        return "No recent attempt found.", 400
    
    attempt_path = os.path.join(ATTEMPTS_DIR, f"{last_id}.json")
    if not os.path.exists(attempt_path):
        return "Attempt data not found.", 404
    
    with open(attempt_path, 'r', encoding='utf-8') as f:
        attempt = json.load(f)
    
    if not attempt.get('results'):
        return "No results available.", 400
    
    # Get user info
    user_info = session.get('user', {})
    user_name = user_info.get('name', 'Candidate')
    
    # Get assessment results
    scores = attempt['results']['scores']
    attributes = attempt['results'].get('attributes', {})
    
    # Generate the Career Strengths Blueprint report
    report_content = generate_career_blueprint_report(user_name, scores, attributes)
    
    # Return as downloadable file
    response = Response(
        report_content,
        mimetype='text/markdown',
        headers={'Content-Disposition': f'attachment; filename="Career_Strengths_Blueprint_{user_name.replace(" ", "_")}.md"'}
    )
    
    return response

@app.route('/download_report')
def download_report():
    """Generate a detailed PDF report for the last attempt and send it as a downloadable file."""
    
    from io import BytesIO
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
    except Exception as e:
        return "<h2>PDF generation library not installed</h2><p>Install <code>reportlab</code> to enable PDF report generation.</p>", 500

    last_id = session.get('last_attempt_id')
    if not last_id:
        return "No recent attempt found.", 400
    attempt_path = os.path.join(ATTEMPTS_DIR, f"{last_id}.json")
    if not os.path.exists(attempt_path):
        return "Attempt data not found.", 404
    with open(attempt_path, 'r', encoding='utf-8') as f:
        attempt = json.load(f)

    # Basic scoring and analysis
    scores = attempt.get('results', {}).get('scores', {})
    total = sum(scores.values()) or 1
    percent = {k: (v/total)*100 for k,v in scores.items()}

    # Category friendly names and analysis templates
    category_info = {
        'FAR': {
            'name': 'Financial / Analytical Reasoning',
            'description': 'Comfort with numbers, risk analysis, and analytical decision-making.'
        },
        'BM': {
            'name': 'Business & Market Acumen',
            'description': 'Understanding of business context, market forces and commercial judgment.'
        },
        'CRM': {
            'name': 'Customer Relationship & Communication',
            'description': 'Strength in customer empathy, communication and stakeholder management.'
        },
        'MO': {
            'name': 'Motivation & Operational Orientation',
            'description': 'Drive, operational focus and ability to convert plans into execution.'
        }
    }

    # Build narrative per category
    narratives = {}
    for code in ['FAR','BM','CRM','MO']:
        p = percent.get(code, 0)
        info = category_info.get(code, {})
        narrative = []
        narrative.append(f"<b>{info.get('name','')}</b>")
        narrative.append(info.get('description',''))
        # Interpret score
        if p >= 40:
            narrative.append('Strength: This area is a clear strength — strong preference and consistent selections suggest solid capability here.')
            narrative.append('What this means: Likely to excel at tasks and roles that rely on these skills.')
            narrative.append('Suggested next steps: consider leadership stretch assignments, mentoring others, or deeper specialization.')
        elif p >= 20:
            narrative.append('Moderate capability: a balanced score — shows some aptitude but room to grow.')
            narrative.append('What this means: Good foundation; targeted training and on-the-job practice will help.')
            narrative.append('Suggested next steps: focused courses, small projects, and cross-functional exposure.')
        else:
            narrative.append('Opportunity / Weakness: Low relative score indicates this is a development area.')
            narrative.append('What this means: May struggle in roles that demand this ability; training and guided experience recommended.')
            narrative.append('Suggested next steps: basic courses, close coaching, and practical assignments to build confidence.')
        narratives[code] = narrative

    # Determine strengths and weaknesses summary
    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    strengths = [category_info.get(c[0],{}).get('name',c[0]) for c in sorted_cats[:2] if c[1]>0]
    weaknesses = [category_info.get(c[0],{}).get('name',c[0]) for c in sorted_cats[-2:] if c[1]>=0]

    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40,leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    heading = styles['Heading1']

    story = []
    title = Paragraph('Assessment Report', heading)
    story.append(title)
    story.append(Spacer(1, 12))
    user_name = attempt.get('user') or 'Candidate'
    submitted_at = attempt.get('submitted_at') or attempt.get('start') or ''
    story.append(Paragraph(f'<b>Candidate:</b> {user_name}', normal))
    story.append(Paragraph(f'<b>Date:</b> {submitted_at}', normal))
    story.append(Spacer(1,12))

    # Scores table
    data = [['Category','Count','Percent']]
    for code in ['FAR','BM','CRM','MO']:
        data.append([category_info[code]['name'], str(scores.get(code,0)), f"{percent.get(code,0):.1f}%"])
    tbl = Table(data, hAlign='LEFT', colWidths=[250,80,80])
    tbl.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f2f2f2')),
                            ('BOX',(0,0),(-1,-1),0.5,colors.grey),
                            ('INNERGRID',(0,0),(-1,-1),0.25,colors.grey),
                            ('FONT',(0,0),(-1,0),'Helvetica-Bold')]))
    story.append(tbl)
    story.append(Spacer(1,12))

    # Strengths & weaknesses summary
    story.append(Paragraph('<b>Strengths</b>', styles['Heading2']))
    if strengths:
        for s in strengths:
            story.append(Paragraph(f'- {s}', normal))
    else:
        story.append(Paragraph('No dominant strengths identified.', normal))
    story.append(Spacer(1,8))
    story.append(Paragraph('<b>Development Areas / Weaknesses</b>', styles['Heading2']))
    if weaknesses:
        for w in weaknesses:
            story.append(Paragraph(f'- {w}', normal))
    else:
        story.append(Paragraph('No clear weaknesses identified.', normal))
    story.append(Spacer(1,12))

    # Detailed per-category narratives
    for code in ['FAR','BM','CRM','MO']:
        story.append(Paragraph(category_info[code]['name'], styles['Heading3']))
        for para in narratives[code]:
            story.append(Paragraph(para, normal))
        story.append(Spacer(1,8))

    # Footer notes
    story.append(Spacer(1,12))
    story.append(Paragraph('Notes:', styles['Heading3']))
    story.append(Paragraph('This report is an automated synthesis of assessment responses. Use it as a guide — combine with interviews and practical evaluation for selection decisions.', normal))

    doc.build(story)

    buffer.seek(0)
    from flask import send_file
    return send_file(buffer, as_attachment=True, 
                    download_name=f'assessment_report_{last_id}.pdf', 
                    mimetype='application/pdf')

@app.route('/jobs')
def jobs_page():
    """
    Jobs page route - displays latest job listings
    """
    return render_template('jobs.html')

@app.route('/health')
def health_check():
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}, 200

@app.route('/api/jobs')
def api_jobs():
    """
    API endpoint to fetch latest jobs
    """
    try:
        num_jobs = request.args.get('limit', 50, type=int)
        jobs = get_latest_jobs(num_jobs)
        return jsonify({
            'success': True,
            'jobs': jobs,
            'total': len(jobs),
            'timestamp': datetime.now().isoformat() 
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'jobs': [],
            'total': 0
        }), 500

@app.route('/<path:filename>')
def static_files(filename):
    safe_path = os.path.join(SITE_DIR, filename)
    if os.path.exists(safe_path) and os.path.commonpath([os.path.abspath(safe_path), SITE_DIR]) == os.path.abspath(SITE_DIR):
        return send_from_directory(SITE_DIR, filename)
    return abort(404)

if __name__ == '__main__':
    print('Run: python app.py to start the Flask site (listening on 0.0.0.0:5000)')
    app.run(debug=False, host='0.0.0.0')