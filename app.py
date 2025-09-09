from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, Response
import os, json, random, uuid
import pandas as pd
import re
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from career_report_generator import calculate_attribute_scores, generate_career_blueprint_report
from job_scraper import get_latest_jobs

BASE_DIR = os.path.dirname(__file__)
ATTEMPTS_DIR = os.path.join(BASE_DIR, 'attempts')
SITE_DIR = os.path.join(BASE_DIR, 'site')
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
EXCEL_FILE = os.path.join(BASE_DIR, 'Sample Assessment questions.xlsx')

app = Flask(__name__, static_folder=None, template_folder='templates')
# Production-ready defaults
app.secret_key = 'unicorn-secret-please-change'
app.config['DEBUG'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_PERMANENT'] = False


def strip_tags_func(s):
    """Remove internal tag markers like (FAR), (CRM), (BM), (MO) from display text."""
    if not s:
        return s
    try:
        return re.sub(r'\s*\((?:FAR|CRM|BM|MO)\)\s*', '', str(s))
    except Exception:
        return str(s)

app.jinja_env.filters['strip_tags'] = strip_tags_func

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
def load_questions():
    if not os.path.exists(EXCEL_FILE):
        return []
    df = pd.read_excel(EXCEL_FILE)
    questions = []
    for _, row in df.iterrows():
        # Ensure required columns exist
        if pd.isna(row.get('No')) or pd.isna(row.get('Scenario')):
            continue
        try:
            no = int(row['No'])
        except Exception:
            no = int(_)+1
        opts = []
        mapping = [('Option A','FAR'), ('Option B','BM'), ('Option C','CRM'), ('Option D','MO')]
        for col, code in mapping:
            text = row.get(col)
            if pd.notna(text):
                opts.append({'text': str(text), 'code': code})
        questions.append({
            'No': no, 
            'Scenario': str(row['Scenario']), 
            'Options': opts, 
            'Category': row.get('Categories/Attributes','')
        })
    return questions

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


@app.route('/assessment')
def assessment():
    # start or resume an attempt and redirect to first question
    if not session.get('logged_in'):
        return redirect(url_for('login', next='/assessment'))
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
            'user': session.get('user', {}).get('email'),
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
        # check timeout (30 minutes)
        start = datetime.fromisoformat(attempt['start'])
        if datetime.utcnow() - start > timedelta(minutes=30):
            try:
                os.remove(attempt_path)
            except Exception:
                pass
            session.pop('attempt_id', None)
            session.clear()
            return redirect(url_for('login', next='/assessment', timeout=1))
    # redirect to first question (or resume at 0)
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
    
    # Handle GET request (when user reaches end of assessment)
    if request.method == 'GET':
        # Auto-submit the assessment using saved answers
        pass
    
    # tally answers (support form-submission or per-question saved answers)
    scores = {}
    # prefer request.form (legacy), otherwise use attempt['answers']
    answers = request.form if request.form else {('q'+k):v for k,v in attempt.get('answers', {}).items()}
    for q in attempt['questions']:
        key = f"q{q['No']}"
        val = answers.get(key) if answers.get(key) else answers.get(str(q['No']))
        if val:
            scores[val] = scores.get(val, 0) + 1
    strongest = max(scores, key=scores.get) if scores else None
    
    # Calculate attribute scores using the new system
    attributes = calculate_attribute_scores(scores)
    
    attempt['submitted'] = True
    attempt['submitted_at'] = datetime.utcnow().isoformat()
    attempt['results'] = {
        'scores': scores, 
        'strongest': strongest,
        'attributes': attributes
    }
    with open(attempt_path, 'w', encoding='utf-8') as f:
        json.dump(attempt, f)
    session['last_attempt_id'] = attempt_id
    session.pop('attempt_id', None)
    return redirect('/results')

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
    attributes = results_data.get('attributes', {})
    
    return render_template('results.html', 
                         results=results_data['scores'], 
                         strongest=results_data['strongest'],
                         attributes=attributes)

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