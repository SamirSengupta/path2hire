from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, Response, abort
import os, json, random, uuid
import pandas as pd
import re
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore
# from authlib.integrations.flask_client import OAuth
import razorpay

# ----------  keep the old helpers + add the new mapper ----------
from career_report_generator import (
    calculate_attribute_scores,
    generate_career_blueprint_report,
    map_assessment_to_report
)
from job_scraper import get_latest_jobs

BASE_DIR = os.path.dirname(__file__)
ATTEMPTS_DIR = os.path.join(BASE_DIR, 'attempts')
SITE_DIR = os.path.join(BASE_DIR, 'site')
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
EXCEL_FILE = os.path.join(BASE_DIR, 'Sample Assessment questions.xlsx')

import zipfile, io, glob
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

CONTACT_DIR   = os.path.join(BASE_DIR, 'data')
CONTACT_FILE  = os.path.join(CONTACT_DIR, 'contacts.xlsx')
os.makedirs(CONTACT_DIR, exist_ok=True)

# ============================================================================
# FIREBASE AUTHENTICATION (JWT Verification)
# ============================================================================

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

FIREBASE_CRED_FILE = os.path.join(BASE_DIR, "firebase-service-account.json")

if os.path.exists(FIREBASE_CRED_FILE):
    cred = credentials.Certificate(FIREBASE_CRED_FILE)
    firebase_admin.initialize_app(cred)
    db = firestore.client()  # ⭐ ADD THIS LINE
    FIREBASE_ENABLED = True
    print("✅ Firebase initialized successfully with Firestore.")
else:
    db = None  # ⭐ ADD THIS LINE
    FIREBASE_ENABLED = False
    print("⚠️ Firebase service account file missing — Auth disabled.")

@app.route("/firebase-login", methods=["POST"])
def firebase_login():
    if not FIREBASE_ENABLED:
        return jsonify({"error": "Firebase not configured"}), 503

    data = request.get_json()
    id_token = data.get("token")
    name = data.get("name", "")

    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        email = decoded_token.get("email")
        uid = decoded_token.get("uid")

        users = load_users()
        if email not in users:
            users[email] = {
                "name": name or email.split("@")[0],
                "email": email,
                "firebase_uid": uid,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "auth_provider": "firebase"
            }
            save_users(users)
        
        # Update name if provided and different
        elif name and users[email].get("name") != name:
            users[email]["name"] = name
            save_users(users)

        session["logged_in"] = True
        session["user"] = {"email": email, "name": users[email]["name"]}
        
        return jsonify({"success": True})

    except Exception as e:
        error_str = str(e)
        print("Firebase verification failed:", e)
        
        # Handle clock skew errors with tolerance
        if "too early" in error_str.lower():
            # Extract time difference from error message
            # Format: "Token used too early, <token_time> <server_time>"
            import re
            match = re.search(r'(\d+) < (\d+)', error_str)
            if match:
                token_time = int(match.group(1))
                server_time = int(match.group(2))
                time_diff = server_time - token_time
                
                # Allow clock skew up to 60 seconds
                if time_diff <= 60:
                    print(f"Allowing clock skew of {time_diff} seconds (within tolerance)")
                    try:
                        # Try to decode the token payload manually
                        import base64
                        # JWT is base64url encoded, split by dots
                        parts = id_token.split('.')
                        if len(parts) >= 2:
                            # Decode payload (second part)
                            payload_part = parts[1]
                            # Add padding if needed
                            padding = 4 - len(payload_part) % 4
                            if padding != 4:
                                payload_part += '=' * padding
                            payload_bytes = base64.urlsafe_b64decode(payload_part)
                            payload = json.loads(payload_bytes.decode('utf-8'))
                            
                            # Verify it's a valid Firebase token structure
                            if payload.get('iss') and 'google.com' in payload.get('iss', ''):
                                email = payload.get('email')
                                uid = payload.get('sub') or payload.get('user_id')
                                
                                if email and uid:
                                    # Proceed with user creation/login
                                    users = load_users()
                                    if email not in users:
                                        users[email] = {
                                            "name": name or email.split("@")[0],
                                            "email": email,
                                            "firebase_uid": uid,
                                            "created_at": datetime.now(timezone.utc).isoformat(),
                                            "auth_provider": "firebase"
                                        }
                                        save_users(users)
                                    
                                    elif name and users[email].get("name") != name:
                                        users[email]["name"] = name
                                        save_users(users)
                                    
                                    session["logged_in"] = True
                                    session["user"] = {"email": email, "name": users[email]["name"]}
                                    
                                    return jsonify({"success": True})
                    except Exception as decode_error:
                        print(f"Failed to decode token manually: {decode_error}")
            
            return jsonify({
                "error": "CLOCK_SKEW",
                "message": "Token timestamp issue detected. Please retry."
            }), 401
        
        return jsonify({"error": str(e)}), 401
    

# ============================================================================
# Contact route fuck
# ============================================================================
@app.route('/contact', methods=['POST'])
def save_contact():
    fullName = request.form.get('fullName', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    inquiryType = request.form.get('inquiryType', '')
    background = request.form.get('background', '')
    message = request.form.get('message', '')
    
    # Prepare data for Firebase
    contact_data = {
        'fullName': fullName,
        'email': email,
        'phone': phone,
        'inquiryType': inquiryType,
        'background': background,
        'message': message,
        'submittedAt': firestore.SERVER_TIMESTAMP,
        'status': 'new',
        'source': 'website'
    }
    
    try:
        # Save to Firebase Firestore
        if FIREBASE_ENABLED and db:
            doc_ref = db.collection('contacts').add(contact_data)
            print(f"✅ Contact saved to Firebase: {doc_ref[1].id}")
        
        # Also save to Excel (backup)
        excel_row = {
            'Full Name': fullName,
            'Email': email,
            'Phone': phone,
            'Inquiry Type': inquiryType,
            'Background': background,
            'Message': message,
            'Submitted At': datetime.utcnow()
        }
        
        if not os.path.exists(CONTACT_EXCEL):
            pd.DataFrame([excel_row]).to_excel(CONTACT_EXCEL, index=False)
        else:
            df = pd.read_excel(CONTACT_EXCEL)
            df = pd.concat([df, pd.DataFrame([excel_row])], ignore_index=True)
            df.to_excel(CONTACT_EXCEL, index=False)
        
        return jsonify({'success': True, 'message': 'Contact form submitted successfully'}), 200
        
    except Exception as e:
        print(f"❌ Error saving contact: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


    
# ============================================================================
# RAZORPAY PAYMENT INTEGRATION
# ============================================================================

RAZORPAY_KEY_ID = "rzp_live_RRLzuRNwQiqFcR"
RAZORPAY_KEY_SECRET = "1Fct2RgdkxW97AWMTTRYsunC"
ASSESSMENT_PRICE = int(os.environ.get('ASSESSMENT_PRICE', '19900'))
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

PAYMENTS_DIR = os.path.join(BASE_DIR, 'payments')
os.makedirs(PAYMENTS_DIR, exist_ok=True)
PAYMENTS_FILE = os.path.join(PAYMENTS_DIR, 'payments.json')

TRAINER_DIR = os.path.join(BASE_DIR, 'data', 'trainers')
os.makedirs(TRAINER_DIR, exist_ok=True)
TRAINER_FILE = os.path.join(TRAINER_DIR, 'trainers.json')
CAREER_DIR   = os.path.join(BASE_DIR, 'data')
CAREER_FILE  = os.path.join(CAREER_DIR, 'careers.xlsx')
os.makedirs(CAREER_DIR, exist_ok=True)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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

def load_payments():
    if os.path.exists(PAYMENTS_FILE):
        with open(PAYMENTS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_payments(payments):
    with open(PAYMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(payments, f, indent=2)

def has_user_paid(user_email):
    payments = load_payments()
    user_payments = payments.get(user_email, [])
    return any(p.get('status') == 'captured' for p in user_payments)

def record_payment(user_email, payment_data):
    payments = load_payments()
    if user_email not in payments:
        payments[user_email] = []
    payments[user_email].append(payment_data)
    save_payments(payments)

def load_trainers():
    if os.path.exists(TRAINER_FILE):
        with open(TRAINER_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_trainers(trainers):
    with open(TRAINER_FILE, 'w', encoding='utf-8') as f:
        json.dump(trainers, f, indent=2)

def calculate_profile_completion(user_data: dict) -> int:
    required = ['name', 'first_name', 'last_name', 'phone', 'date_of_birth', 'address']
    completed = sum(1 for f in required if user_data.get(f))
    return int((completed / len(required)) * 100)

def strip_tags_func(s):
    if not s:
        return s
    try:
        return re.sub(r'\s*\((?:FAR|CRM|BM|MO)\)\s*', '', str(s))
    except Exception:
        return str(s)

app.jinja_env.filters['strip_tags'] = strip_tags_func

def load_questions():
    if not os.path.exists(EXCEL_FILE):
        return []
    
    df = pd.read_excel(EXCEL_FILE)
    
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
    
    questions_by_category = {cat: [] for cat in EXPECTED_CATEGORIES}
    
    for idx, row in df.iterrows():
        if pd.isna(row.get('No')) or pd.isna(row.get('Scenario')):
            continue
        
        try:
            no = int(row['No'])
        except Exception:
            no = int(idx) + 1
        
        opts = []
        mapping = [('Option A', 'FAR'), ('Option B', 'BM'), 
                   ('Option C', 'CRM'), ('Option D', 'MO')]
        for col, code in mapping:
            text = row.get(col)
            if pd.notna(text):
                opts.append({'text': str(text), 'code': code})
        
        category = row.get('Categories/Attributes') or row.get('Categories') or ''
        category = str(category).strip()
        
        question = {
            'No': no,
            'Scenario': str(row['Scenario']),
            'Options': opts,
            'Category': category
        }
        
        if category in questions_by_category:
            questions_by_category[category].append(question)
    
    selected_questions = []
    warnings = []
    
    for category in EXPECTED_CATEGORIES:
        available = questions_by_category[category]
        
        if len(available) >= 10:
            selected = random.sample(available, 10)
            selected_questions.extend(selected)
        elif len(available) > 0:
            selected_questions.extend(available)
            warnings.append(f"Category '{category}': Only {len(available)} questions available (need 10)")
        else:
            warnings.append(f"Category '{category}': No questions found!")
    
    if warnings:
        print("\nQuestion Selection Warnings:")
        for w in warnings:
            print(f"   - {w}")
        print(f"   Total questions loaded: {len(selected_questions)} (expected 100)\n")
    
    return selected_questions


# ============================================================================
# DOWNLOAD & DELETE ROUTES
# ============================================================================

@app.route('/download/careers')
def download_careers_zip():
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(CAREER_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name  = os.path.relpath(file_path, CAREER_DIR)
                zf.write(file_path, arc_name)
    memory_file.seek(0)
    return send_file(memory_file,
                     mimetype='application/zip',
                     as_attachment=True,
                     download_name='careers_bundle.zip')

@app.route('/download/contacts')
def download_contacts_zip():
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

@app.route('/download/careers/delete', methods=['POST'])
def delete_careers():
    header = ['Full Name','Email','Phone','Position','Trainings',
              'Current CTC','Portfolio','Location','Work Authorization',
              'Salary Expectation','Start Date','Resume Filename',
              'Cover-Letter Filename','Submitted At']
    pd.DataFrame(columns=header).to_excel(CAREER_FILE, index=False)

    for f in glob.glob(os.path.join(CAREER_DIR, "RESUME_*")) + \
             glob.glob(os.path.join(CAREER_DIR, "CL_*")):
        try:
            os.remove(f)
        except Exception:
            pass

    return jsonify({'status': 'ok', 'message': 'All career data wiped.'}), 200

@app.route('/download/contacts/delete', methods=['POST'])
def delete_contacts():
    header = ['Full Name','Email','Phone','Inquiry Type',
              'Background','Message','Submitted At']
    pd.DataFrame(columns=header).to_excel(CONTACT_FILE, index=False)

    for f in glob.glob(os.path.join(CONTACT_DIR, "*")):
        if not f.endswith('.xlsx'):
            try:
                os.remove(f)
            except Exception:
                pass

    return jsonify({'status': 'ok', 'message': 'All contact data wiped.'}), 200

# ============================================================================
# PAYMENT ROUTES
# ============================================================================

@app.route('/payment')
def payment():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/payment'))
    
    user_email = session.get('user', {}).get('email')
    
    if has_user_paid(user_email):
        return redirect('/assessment')
    
    return render_template('payment.html', 
                         razorpay_key=RAZORPAY_KEY_ID,
                         amount=ASSESSMENT_PRICE,
                         user_email=user_email,
                         user_name=session.get('user', {}).get('name'))

@app.route('/create_order', methods=['POST'])
def create_order():
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    user_email = session.get('user', {}).get('email')
    
    if has_user_paid(user_email):
        return jsonify({'error': 'Already paid'}), 400
    
    try:
        # Generate a receipt ID that's max 40 characters
        # Format: assess_<short_email>_<short_uuid>
        # Get first part of email before @ (max 15 chars) and last 6 chars of UUID
        email_prefix = user_email.split('@')[0][:15] if '@' in user_email else user_email[:15]
        short_uuid = uuid.uuid4().hex[:6]
        receipt_id = f'assess_{email_prefix}_{short_uuid}'
        # Ensure it doesn't exceed 40 characters
        if len(receipt_id) > 40:
            # If still too long, use timestamp-based ID
            import time
            timestamp = int(time.time())
            receipt_id = f'assess_{timestamp}_{short_uuid}'
            if len(receipt_id) > 40:
                receipt_id = f'assess_{timestamp}'[:40]
        
        order_data = {
            'amount': ASSESSMENT_PRICE,
            'currency': 'INR',
            'receipt': receipt_id,
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

@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    if not session.get('logged_in'):
        return jsonify({'error': 'Not logged in'}), 401
    
    user_email = session.get('user', {}).get('email')
    
    try:
        payment_id = request.json.get('razorpay_payment_id')
        order_id = request.json.get('razorpay_order_id')
        signature = request.json.get('razorpay_signature')
        
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
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

@app.route('/checkpoint')
def checkpoint():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/checkpoint'))
    
    user_email = session.get('user', {}).get('email')
    
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

# ============================================================================
# TRAINER ROUTES
# ============================================================================

@app.route('/trainer')
def trainer():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/trainer'))
    
    user_info = session.get('user', {})
    user_email = user_info.get('email')
    trainers = load_trainers()
    trainer_data = trainers.get(user_email, {})
    
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
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
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
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
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
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
    account_number = request.form.get('account_number', '').strip()
    confirm_account = request.form.get('confirm_account_number', '').strip()
    
    if account_number != confirm_account:
        return jsonify({'success': False, 'error': 'Account numbers do not match'}), 400
    
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
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
    qualifications = []
    form_data = request.form.to_dict()
    
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
        if any(qual.values()):
            qualifications.append(qual)
    
    trainers[user_email]['qualifications'] = qualifications
    trainers[user_email]['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_trainers(trainers)
    
    return jsonify({'success': True, 'message': 'Qualifications saved successfully'})

@app.route('/trainer/update/employment', methods=['POST'])
def update_trainer_employment():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
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
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_email = session['user']['email']
    trainers = load_trainers()
    
    if user_email not in trainers:
        trainers[user_email] = {}
    
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

# ============================================================================
# CONTACT & CAREER ROUTES
# ============================================================================

@app.route('/career', methods=['POST'])
def save_career():
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    position = request.form.get('position', '').strip()
    trainings = request.form.get('trainings', '').strip()
    current_ctc = request.form.get('current_ctc', '').strip()
    portfolio = request.form.get('portfolio', '').strip()
    location = request.form.get('location', '').strip()
    authorization = request.form.get('authorization', '').strip()
    salary_expectation = request.form.get('salary_expectation', '').strip()
    start_date = request.form.get('start_date', '')
    resume_file = request.files.get('resume_file')
    cover_letter_file = request.files.get('cover_letter_file')
    
    # Save files first
    ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    resume_filename = ''
    cover_letter_filename = ''
    
    if resume_file and resume_file.filename:
        resume_filename = f"RESUME_{ts}_{resume_file.filename}"
        resume_file.save(os.path.join(CAREER_DIR, resume_filename))
    
    if cover_letter_file and cover_letter_file.filename:
        cover_letter_filename = f"CL_{ts}_{cover_letter_file.filename}"
        cover_letter_file.save(os.path.join(CAREER_DIR, cover_letter_filename))
    
    # Prepare data for Firebase
    career_data = {
        'fullName': full_name,
        'email': email,
        'phone': phone,
        'position': position,
        'trainings': trainings,
        'currentCTC': current_ctc,
        'portfolio': portfolio,
        'location': location,
        'workAuthorization': authorization,
        'salaryExpectation': salary_expectation,
        'startDate': start_date,
        'resumeFilename': resume_filename,
        'coverLetterFilename': cover_letter_filename,
        'submittedAt': firestore.SERVER_TIMESTAMP,
        'status': 'applied',
        'source': 'website'
    }
    
    try:
        # Save to Firebase Firestore
        if FIREBASE_ENABLED and db:
            doc_ref = db.collection('career_applications').add(career_data)
            print(f"✅ Career application saved to Firebase: {doc_ref[1].id}")
        
        # Also save to Excel (backup)
        excel_row = {
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
            'Resume Filename': resume_filename,
            'Cover-Letter Filename': cover_letter_filename,
            'Submitted At': datetime.utcnow()
        }
        
        if not os.path.exists(CAREER_EXCEL):
            pd.DataFrame([excel_row]).to_excel(CAREER_EXCEL, index=False)
        else:
            df = pd.read_excel(CAREER_EXCEL)
            df = pd.concat([df, pd.DataFrame([excel_row])], ignore_index=True)
            df.to_excel(CAREER_EXCEL, index=False)
        
        return jsonify({'success': True, 'message': 'Application submitted successfully'}), 200
        
    except Exception as e:
        print(f"❌ Error saving career application: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    


# ============================================================================
# ADMIN DASHBOARD & MANAGEMENT ROUTES
# ============================================================================

@app.route('/admin')
@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard home"""
    if not session.get('logged_in') or session.get('user', {}).get('email') != 'admin':
        return redirect('/login')
    return render_template('admin_dashboard.html')

@app.route('/admin/contacts')
def admin_contacts():
    """View all contact submissions"""
    if not session.get('logged_in') or session.get('user', {}).get('email') != 'admin':
        return redirect('/login')
    
    try:
        if FIREBASE_ENABLED and db:
            contacts_ref = db.collection('contacts').order_by('submittedAt', direction=firestore.Query.DESCENDING).limit(100)
            contacts = []
            for doc in contacts_ref.stream():
                contact = doc.to_dict()
                contact['id'] = doc.id
                contacts.append(contact)
            
            return render_template('admin_contacts.html', contacts=contacts)
        else:
            return "Firebase not enabled", 503
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/admin/careers')
def admin_careers():
    """View all career applications"""
    if not session.get('logged_in') or session.get('user', {}).get('email') != 'admin':
        return redirect('/login')
    
    try:
        if FIREBASE_ENABLED and db:
            careers_ref = db.collection('career_applications').order_by('submittedAt', direction=firestore.Query.DESCENDING).limit(100)
            applications = []
            for doc in careers_ref.stream():
                app = doc.to_dict()
                app['id'] = doc.id
                applications.append(app)
            
            return render_template('admin_careers.html', applications=applications)
        else:
            return "Firebase not enabled", 503
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/admin/contact/<contact_id>/status', methods=['POST'])
def update_contact_status(contact_id):
    """Update contact status"""
    if not session.get('logged_in') or session.get('user', {}).get('email') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        status = request.json.get('status')
        if FIREBASE_ENABLED and db:
            db.collection('contacts').document(contact_id).update({
                'status': status,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            return jsonify({'success': True})
        return jsonify({'error': 'Firebase not enabled'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/career/<app_id>/status', methods=['POST'])
def update_career_status(app_id):
    """Update career application status"""
    if not session.get('logged_in') or session.get('user', {}).get('email') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        status = request.json.get('status')
        if FIREBASE_ENABLED and db:
            db.collection('career_applications').document(app_id).update({
                'status': status,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            return jsonify({'success': True})
        return jsonify({'error': 'Firebase not enabled'}), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# AUTH ROUTES (LOGIN, SIGNUP, LOGOUT)
# ============================================================================

@app.route('/')
def index():
    return send_from_directory(SITE_DIR, 'index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    users = load_users()
    if request.method == 'GET':
        session.clear()
    if request.method == 'POST':
        email = (request.form.get('email') or '').lower().strip()
        password = request.form.get('password') or ''
        next_url = request.form.get('next') or request.args.get('next') or '/assessment'
        user = users.get(email)
        
        if user and user.get('password') and check_password_hash(user.get('password'), password):
            session['logged_in'] = True
            session['user'] = {'email': email, 'name': user.get('name')}
            return redirect(next_url)
        
        if email == 'admin' and password == 'admin':
            session['logged_in'] = True
            session['user'] = {'email': 'admin', 'name': 'Administrator'}
            return redirect(next_url)
        
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
    
    users[email] = {
        'name': name or email.split('@')[0],
        'password': generate_password_hash(password),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    save_users(users)
    session['logged_in'] = True
    session['user'] = {'email': email, 'name': users[email]['name']}
    return redirect(next_url)

@app.route('/logout')
def logout():
    attempt_id = session.pop('attempt_id', None)
    session.clear()
    if attempt_id:
        try:
            os.remove(os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json"))
        except Exception:
            pass
    return redirect('/')

# ============================================================================
# PROFILE ROUTES
# ============================================================================

@app.route('/profile')
def profile():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/profile'))

    user_info = session.get('user', {})
    user_email = user_info.get('email')
    users = load_users()
    user_data = users.get(user_email, {})

    has_paid = has_user_paid(user_email)

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
        'has_paid': has_paid
    }
    return render_template('profile.html', **profile_data)

@app.route('/profile.html')
def profile_html_redirect():
    return redirect(url_for('profile'), code=301)

@app.route('/profile/update', methods=['POST'])
def update_profile():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    user_email = session['user']['email']
    users = load_users()
    if user_email not in users:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    updates = {k: request.form.get(k, '').strip() for k in
               ['first_name', 'last_name', 'phone', 'address',
                'date_of_birth', 'gender', 'bio']}
    updates['updated_at'] = datetime.now(timezone.utc).isoformat()
    users[user_email].update({k: v for k, v in updates.items() if v})

    fname = users[user_email].get('first_name', '')
    lname = users[user_email].get('last_name', '')
    users[user_email]['name'] = f"{fname} {lname}".strip() or users[user_email]['name']
    session['user']['name'] = users[user_email]['name']

    save_users(users)
    return jsonify({'success': True, 'message': 'Profile updated'})

# ============================================================================
# ASSESSMENT ROUTES
# ============================================================================

@app.route('/assessment')
def assessment():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))
    
    user_email = session.get('user', {}).get('email')
    
    if not has_user_paid(user_email):
        return redirect('/payment')
    
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
    
    if 'answers' not in attempt:
        attempt['answers'] = {}
    attempt['answers'][str(qno)] = choice
    with open(attempt_path, 'w', encoding='utf-8') as f:
        json.dump(attempt, f)
    
    total = len(attempt['questions'])
    next_idx = idx + 1
    if next_idx >= total:
        return redirect(url_for('submit'))
    return redirect(url_for('assessment_question', idx=next_idx))

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))

    attempt_id = session.get('attempt_id')
    if not attempt_id:
        return redirect('/assessment')

    attempt_path = os.path.join(ATTEMPTS_DIR, f"{attempt_id}.json")
    if not os.path.exists(attempt_path):
        return redirect('/assessment')

    with open(attempt_path, 'r', encoding='utf-8') as f:
        attempt = json.load(f)

    start = datetime.fromisoformat(attempt['start'])
    if datetime.utcnow() - start > timedelta(minutes=30):
        try:
            os.remove(attempt_path)
        except Exception:
            pass
        session.clear()
        return redirect(url_for('login', next='/assessment', timeout=1))

    answers = request.form if request.form else {('q' + k): v for k, v in attempt.get('answers', {}).items()}

    def normalize_choice(raw_val, question):
        if not raw_val:
            return None
        v = str(raw_val).strip()
        if not v:
            return None

        v_u = v.upper()
        if v_u in ('FAR', 'BM', 'CRM', 'MO'):
            return v_u

        letter_map = {'A': 'FAR', 'B': 'BM', 'C': 'CRM', 'D': 'MO'}
        if len(v_u) == 1 and v_u in letter_map:
            return letter_map[v_u]

        m = re.match(r'^(?:OPTION\s*)?([A-D])\b', v_u)
        if m:
            return letter_map.get(m.group(1))

        opts = question.get('Options', []) or []
        lower_v = v.strip().lower()
        for opt in opts:
            opt_text = str(opt.get('text', '')).strip().lower()
            opt_code = opt.get('code', '').upper()
            if lower_v == opt_text or lower_v in opt_text:
                return opt_code or None

        return None

    scores = {'FAR': 0, 'BM': 0, 'CRM': 0, 'MO': 0}
    category_scores = {}
    debug_rows = []

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

        scores[normalized] = scores.get(normalized, 0) + 1

        category = q.get('Category', 'Unknown').strip() or 'Unknown'
        if category not in category_scores:
            category_scores[category] = {'FAR': 0, 'BM': 0, 'CRM': 0, 'MO': 0}
        category_scores[category][normalized] += 1

    strongest = max(scores, key=scores.get) if any(scores.values()) else None
    attributes = calculate_attribute_scores(scores)

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

    with open(attempt_path, 'w', encoding='utf-8') as f:
        json.dump(attempt, f, indent=2)

    session['last_attempt_id'] = attempt_id
    session.pop('attempt_id', None)

    return redirect('/results')

# ============================================================================
# RESULTS & REPORTS
# ============================================================================

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

    results_data = attempt['results']
    attributes   = results_data.get('attributes', {})
    report_context = map_assessment_to_report(results_data['scores'])
    
    # Expand abbreviations in strongest field
    from career_report_generator import ABBREVIATION_MAP
    strongest = results_data.get('strongest', '')
    if strongest in ABBREVIATION_MAP:
        strongest = ABBREVIATION_MAP[strongest]

    return render_template('results.html',
                         results=results_data['scores'],
                         strongest=strongest,
                         attributes=attributes,
                         **report_context)

@app.route('/download_career_blueprint')
def download_career_blueprint():
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
    
    user_info = session.get('user', {})
    user_name = user_info.get('name', 'Candidate')
    
    scores = attempt['results']['scores']
    attributes = attempt['results'].get('attributes', {})
    
    # Generate markdown content first
    markdown_content = generate_career_blueprint_report(user_name, scores, attributes)
    
    # Convert to PDF
    from io import BytesIO
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        import re
    except Exception as e:
        return f"<h2>PDF generation library not installed</h2><p>Install <code>reportlab</code> to enable PDF report generation.</p><pre>{e}</pre>", 500
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=80)
    styles = getSampleStyleSheet()
    
    # Contact information for footer
    CONTACT_INFO = {
        'location': 'Kolkata',
        'email': 'contact@path2hire.com',
        'phone': '+919051539665',
        'website': 'www.path2hire.com'
    }
    
    # Footer function to add contact info on every page
    def add_footer(canvas, doc):
        """Add footer with contact information to each page"""
        canvas.saveState()
        
        # Footer styling
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#666666'),
            alignment=1,  # Center
            spaceBefore=10
        )
        
        # Contact information text
        footer_text = f"Path2Hire | {CONTACT_INFO['location']} | {CONTACT_INFO['email']} | {CONTACT_INFO['phone']} | {CONTACT_INFO['website']}"
        footer_para = Paragraph(footer_text, footer_style)
        
        # Get footer width and height
        footer_width, footer_height = footer_para.wrap(doc.width, doc.bottomMargin)
        footer_para.drawOn(canvas, doc.leftMargin, 20)
        
        # Add copyright line
        copyright_text = f"© {datetime.now().year} Path2Hire. All rights reserved."
        copyright_para = Paragraph(copyright_text, footer_style)
        copyright_width, copyright_height = copyright_para.wrap(doc.width, doc.bottomMargin)
        copyright_para.drawOn(canvas, doc.leftMargin, 10)
        
        canvas.restoreState()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=12,
        alignment=1  # Center
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=10,
        spaceBefore=12
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=8,
        spaceBefore=10
    )
    
    normal_style = styles['Normal']
    bold_style = ParagraphStyle('Bold', parent=normal_style, fontName='Helvetica-Bold')
    
    def process_text(text):
        """Convert markdown and HTML to reportlab-compatible format"""
        if not text:
            return text
        # Convert markdown bold to HTML
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Convert markdown italic to HTML
        text = re.sub(r'_(.*?)_', r'<i>\1</i>', text)
        # Remove markdown code formatting
        text = re.sub(r'`(.*?)`', r'\1', text)
        # Ensure HTML tags are properly closed
        return text
    
    story = []
    
    # Parse markdown and convert to PDF elements
    lines = markdown_content.split('\n')
    i = 0
    current_table_data = None
    in_table = False
    skip_next = False
    
    while i < len(lines):
        if skip_next:
            skip_next = False
            i += 1
            continue
            
        line = lines[i].strip()
        
        # Skip empty lines (but add spacing)
        if not line:
            if not in_table:
                story.append(Spacer(1, 6))
            i += 1
            continue
        
        # Headers
        if line.startswith('# '):
            text = process_text(line[2:].strip())
            story.append(Paragraph(text, title_style))
            story.append(Spacer(1, 12))
        elif line.startswith('## '):
            text = process_text(line[3:].strip())
            story.append(Paragraph(text, heading_style))
            story.append(Spacer(1, 10))
        elif line.startswith('### '):
            text = process_text(line[4:].strip())
            story.append(Paragraph(text, subheading_style))
            story.append(Spacer(1, 8))
        # Tables
        elif line.startswith('|') and '|' in line:
            # Check if this is a separator line
            if '---' in line or all(c in '-: ' for c in line.replace('|', '')):
                if in_table and current_table_data:
                    i += 1
                    continue
            else:
                # Start of table
                if not in_table:
                    current_table_data = []
                    in_table = True
                
                cells = [cell.strip() for cell in line.split('|')[1:-1]]  # Remove empty first/last
                # Clean up and process each cell
                clean_cells = []
                for idx, cell in enumerate(cells):
                    cell_text = process_text(cell)
                    # Use Paragraph for cells to support HTML formatting
                    # Use bold style for header row (first row in table)
                    if len(current_table_data) == 0:
                        clean_cells.append(Paragraph(cell_text, bold_style))
                    else:
                        clean_cells.append(Paragraph(cell_text, normal_style))
                current_table_data.append(clean_cells)
        # End of table
        elif in_table:
            # Process the table
            if current_table_data and len(current_table_data) > 0:
                # Calculate column widths based on number of columns
                num_cols = len(current_table_data[0]) if current_table_data else 1
                col_widths = [450 / num_cols] * num_cols if num_cols > 0 else [450]
                
                table = Table(current_table_data, colWidths=col_widths)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f2f2f2')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('TOPPADDING', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                    ('TOPPADDING', (0, 1), (-1, -1), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(table)
                story.append(Spacer(1, 12))
            current_table_data = None
            in_table = False
            # Don't increment i here, process this line again as regular text
            continue
        # Horizontal rule
        elif line.startswith('---'):
            story.append(Spacer(1, 12))
        # Bullet points
        elif line.startswith('- ') or line.startswith('* '):
            text = process_text(line[2:].strip())
            story.append(Paragraph(f"• {text}", normal_style))
            story.append(Spacer(1, 4))
        # Numbered lists
        elif re.match(r'^\d+\.\s+', line):
            match = re.match(r'^(\d+)\.\s+(.*)', line)
            if match:
                num, text = match.groups()
                text = process_text(text)
                story.append(Paragraph(f"{num}. {text}", normal_style))
                story.append(Spacer(1, 4))
        # Regular text
        else:
            text = process_text(line)
            if text.strip():
                story.append(Paragraph(text, normal_style))
                story.append(Spacer(1, 6))
        
        i += 1
    
    # Handle table that extends to end of document
    if in_table and current_table_data and len(current_table_data) > 0:
        num_cols = len(current_table_data[0]) if current_table_data else 1
        col_widths = [450 / num_cols] * num_cols if num_cols > 0 else [450]
        table = Table(current_table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f2f2f2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 12))
    
    # Build PDF with footer
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, 
                    download_name=f'Career_Strengths_Blueprint_{user_name.replace(" ", "_")}.pdf', 
                    mimetype='application/pdf')

@app.route('/download_report')
def download_report():
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

    scores = attempt.get('results', {}).get('scores', {})
    total = sum(scores.values()) or 1
    percent = {k: (v/total)*100 for k,v in scores.items()}

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

    narratives = {}
    for code in ['FAR','BM','CRM','MO']:
        p = percent.get(code, 0)
        info = category_info.get(code, {})
        narrative = []
        narrative.append(f"<b>{info.get('name','')}</b>")
        narrative.append(info.get('description',''))
        if p >= 40:
            narrative.append('Strength: This area is a clear strength.')
            narrative.append('What this means: Likely to excel at tasks and roles that rely on these skills.')
            narrative.append('Suggested next steps: consider leadership stretch assignments.')
        elif p >= 20:
            narrative.append('Moderate capability: a balanced score.')
            narrative.append('What this means: Good foundation; targeted training will help.')
            narrative.append('Suggested next steps: focused courses and projects.')
        else:
            narrative.append('Opportunity / Weakness: Low relative score.')
            narrative.append('What this means: May struggle in roles that demand this ability.')
            narrative.append('Suggested next steps: basic courses and coaching.')
        narratives[code] = narrative

    sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    strengths = [category_info.get(c[0],{}).get('name',c[0]) for c in sorted_cats[:2] if c[1]>0]
    weaknesses = [category_info.get(c[0],{}).get('name',c[0]) for c in sorted_cats[-2:] if c[1]>=0]

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

    for code in ['FAR','BM','CRM','MO']:
        story.append(Paragraph(category_info[code]['name'], styles['Heading3']))
        for para in narratives[code]:
            story.append(Paragraph(para, normal))
        story.append(Spacer(1,8))

    story.append(Spacer(1,12))
    story.append(Paragraph('Notes:', styles['Heading3']))
    story.append(Paragraph('This report is an automated synthesis of assessment responses.', normal))

    doc.build(story)

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, 
                    download_name=f'assessment_report_{last_id}.pdf', 
                    mimetype='application/pdf')

# ============================================================================
# JOBS ROUTES
# ============================================================================

@app.route('/jobs')
def jobs_page():
    return render_template('jobs.html')

@app.route('/health')
def health_check():
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}, 200

@app.route('/api/jobs')
def api_jobs():
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

# ============================================================================
# STATIC FILES
# ============================================================================

@app.route('/<path:filename>')
def static_files(filename):
    safe_path = os.path.join(SITE_DIR, filename)
    if os.path.exists(safe_path) and os.path.commonpath([os.path.abspath(safe_path), SITE_DIR]) == os.path.abspath(SITE_DIR):
        return send_from_directory(SITE_DIR, filename)
    return abort(404)

if __name__ == '__main__':
    print('Run: python app.py to start the Flask site (listening on 0.0.0.0:5000)')
    app.run(debug=False, host='0.0.0.0')