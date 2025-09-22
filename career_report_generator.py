"""
Career Strengths Blueprint Report Generator for Skill2Hire
Maps assessment results to 10 key attributes and generates comprehensive reports
FIXED: Changed BD references to BM to match actual assessment codes
"""

from datetime import datetime
import random

# ------------------------------------------------------------------
#  WORD-DOC BULLETS  (copy-pasted from the 15 docx you supplied)
# ------------------------------------------------------------------
def map_assessment_to_report(scores: dict) -> dict:
    """
    Convert raw assessment scores -> Word-style report dictionary.
    scores = {'FAR': 6, 'BM': 3, 'CRM': 8, 'MO': 5}  # example
    
    FIXED: Changed all BD references to BM to match actual assessment categories

    Returns dict with keys:
        track_name, swot_strengths, swot_weaknesses, swot_opportunities,
        swot_threats, career_focus_title, career_focus_desc, industry_trends,
        potential_roles, career_path, core_certs, interview_steps, growth_tips,
        closing_paragraph, next_steps
    """
    # 1. normalise to %
    total = max(sum(scores.values()), 1)
    pct = {k: (v / total) * 100 for k, v in scores.items()}

    # 2. decide which Word template to use  (MVP rules – refine later)
    # FIXED: Changed all BD to BM
    if pct.get('CRM', 0) >= 35 and pct.get('BM', 0) >= 25 and pct.get('MO', 0) >= 25:
        return _bm_crm_mo_track()
    elif pct.get('CRM', 0) >= 35 and pct.get('BM', 0) >= 25:
        return _bm_crm_track()
    elif pct.get('BM', 0) >= 35 and pct.get('MO', 0) >= 25:
        return _bm_mo_track()
    elif pct.get('BM', 0) >= 40:
        return _bm_only_track()
    elif pct.get('CRM', 0) >= 40 and pct.get('MO', 0) >= 25:
        return _crm_mo_track()
    elif pct.get('CRM', 0) >= 40:
        return _crm_only_track()
    elif pct.get('FAR', 0) >= 30 and pct.get('BM', 0) >= 25 and pct.get('CRM', 0) >= 25 and pct.get('MO', 0) >= 25:
        return _far_bm_crm_mo_track()
    elif pct.get('FAR', 0) >= 30 and pct.get('BM', 0) >= 25 and pct.get('CRM', 0) >= 25:
        return _far_bm_crm_track()
    elif pct.get('FAR', 0) >= 30 and pct.get('BM', 0) >= 25 and pct.get('MO', 0) >= 25:
        return _far_bm_mo_track()
    elif pct.get('FAR', 0) >= 30 and pct.get('CRM', 0) >= 25 and pct.get('MO', 0) >= 25:
        return _far_crm_mo_track()
    elif pct.get('FAR', 0) >= 30 and pct.get('BM', 0) >= 25:
        return _far_bm_track()
    elif pct.get('FAR', 0) >= 30 and pct.get('CRM', 0) >= 25:
        return _far_crm_track()
    elif pct.get('FAR', 0) >= 30 and pct.get('MO', 0) >= 25:
        return _far_mo_track()
    elif pct.get('FAR', 0) >= 40:
        return _far_only_track()
    elif pct.get('MO', 0) >= 40:
        return _mo_only_track()
    else:
        return _generic_track()


# ----------  individual skeleton builders (copy-pasted from Word files) ----------
def _bm_crm_mo_track():
    return {
        "track_name": "Business & Market Acumen (BM) + Compliance & Risk Management (CRM) + Management & Operations (MO) Track",
        "swot_strengths": [
            "Exceptional at navigating complex processes and regulations",
            "Persuasive communicator, adept at relationship-building",
            "Skilled at driving change and managing cross-functional teams",
            "Process-driven; ensures business growth is ethical and compliant",
            "Strong at implementing policies and motivating diverse groups"
        ],
        "swot_weaknesses": [
            "May underemphasize deep technical finance or analytics",
            "Can become risk-averse, slowing rapid decision-making",
            "Might find ambiguous, highly creative roles uncomfortable",
            "Occasionally at risk of over-focusing on structure or rules",
            "Could overlook subtle details when managing large teams"
        ],
        "swot_opportunities": [
            "Growing demand for leaders bridging business, compliance, and ops",
            "Expansion of client-facing, regulated industries (fintech, pharma)",
            "Digital transformation in business processes and controls",
            "ESG, anti-bribery, and global risk focus increase specialist roles",
            "Operational excellence as a competitive advantage for organizations"
        ],
        "swot_threats": [
            "Regular regulatory changes require continuous upskilling",
            "Automation reducing compliance/ops entry-level roles",
            "High competition for stakeholder management positions",
            "Being seen as 'policy enforcer' can hinder relationship building"
        ],
        "career_focus_title": "BM + CRM + MO",
        "career_focus_desc": (
            "Based on your assessment results, your strongest potential lies in roles that require a blend of business acumen, "
            "compliance oversight, and proactive operations management. You excel at understanding market dynamics, ensuring all activities "
            "meet regulatory standards, and leading teams to execute plans smoothly and ethically."
        ),
        "industry_trends": [
            "Integrated Leadership Roles: Companies seek professionals able to unite compliance, business strategy, and process improvement into revenue-supporting functions.",
            "Regtech & Digital Ops: Fintech, healthcare, consulting, and SaaS companies drive demand for compliance-savvy business leaders.",
            "Risk & Growth: Heightened focus on anti-corruption, KYC/AML, and process accountability in client/service businesses (e.g., banking, logistics).",
            "Operational Transformation: Businesses are digitizing operations and require management that understands both people and process, underpinned by regulatory insight."
        ],
        "potential_roles": [
            {"title": "Business Operations Manager", "employers": "Fintech, corporates, banking, SaaS"},
            {"title": "Compliance Business Partner", "employers": "Global MNCs, consulting firms, GBS centers"},
            {"title": "KYC/AML Operations Manager", "employers": "BFSI, finance BPOs/KPOs, insurance"},
            {"title": "Risk & Controls Project Coordinator", "employers": "Healthcare, pharma, logistics, telecom"},
            {"title": "Business Process Manager (Regulated)", "employers": "Tech, outsourcing, supply chain firms"},
            {"title": "ESG & Sustainability Operations Lead", "employers": "Consumer, finance, manufacturing"}
        ],
        "career_path": [
            {"title": "Analyst/Coordinator", "focus": "Manages compliance-focused operations, risk reviews, small team oversight"},
            {"title": "Business/Process Lead", "focus": "Owns business programs, implements policies, bridges business and compliance"},
            {"title": "Manager/Senior Facilitator", "focus": "Oversees business portfolio, leads change projects, enforces controls and training"},
            {"title": "Head of Operations/Compliance", "focus": "Sets cross-functional policy, manages large teams and business engagements, liaises with regulators/stakeholders"}
        ],
        "core_certs": [
            "KYC & AML: Essential for client-facing roles in regulated industries.",
            "Process Management & Lean Six Sigma: Key for operational improvement and efficiency.",
            "Project Management (CAPM, Agile): Enhances ability to drive and lead change across teams.",
            "Digital Tools: CRM (Salesforce/HubSpot), ERP basics, compliance tools (GRC platforms).",
            "ESG & Data Privacy: Growing roles require knowledge/training in sustainability, privacy, anti-corruption."
        ],
        "interview_steps": [
            "Enroll in KYC/AML, project/process management, or Lean training.",
            "Prepare stories showing how you drove compliance/adaptation in business operations.",
            "Build confidence with business process flows, operational maps, or workflow charts.",
            "Stay updated on compliance changes; follow business transformation and process improvement trends.",
            "Practice discussing how you balance growth, ethics, and team performance."
        ],
        "growth_tips": [
            "Seek internships or leadership in club projects with 'compliance + business + ops' scope—e.g., organizing events, leading operational projects, running quality initiatives.",
            "Network with professionals in regulatory project management, operational risk, or business transformation roles.",
            "Offer to lead process updates, compliance trainings, or new business launches at work or in internships.",
            "Pursue formal Lean Six Sigma, process management, or regulatory certifications as you gain experience."
        ],
        "closing_paragraph": (
            "This blend of strengths positions you for the next generation of leadership roles—where business acumen, "
            "compliance/risk, and operational excellence are all crucial. Companies across tech, finance, consulting, and even "
            "'old economy' sectors are hiring for integrated profiles like yours to drive sustainable, compliant, and efficient growth."
        ),
        "next_steps": [
            "KYC and AML",
            "Order to Cash (O2C), Procure to Pay (P2P), Record to Report (R2R)",
            "Project/Process Management (Lean, CAPM, Agile)",
            "CRM and workflow automation platforms",
            "ESG, data privacy, and corporate ethics"
        ]
    }


# --------------  quick stubs for the remaining tracks  -----------------
# (copy the same pattern – bullets pasted from the Word files you supplied)
# FIXED: Renamed all functions from BD to BM

def _bm_crm_track():          return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _bm_mo_track():           return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _bm_only_track():         return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _crm_mo_track():          return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _crm_only_track():        return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _far_bm_crm_mo_track():   return _bm_crm_mo_track()          # multi – reuse skeleton for now
def _far_bm_crm_track():      return _bm_crm_mo_track()          # multi – reuse skeleton for now
def _far_bm_mo_track():       return _bm_crm_mo_track()          # multi – reuse skeleton for now
def _far_crm_mo_track():      return _bm_crm_mo_track()          # multi – reuse skeleton for now
def _far_bm_track():          return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _far_crm_track():         return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _far_mo_track():          return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _far_only_track():        return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _mo_only_track():         return _bm_crm_mo_track()          # subset – reuse skeleton for now
def _generic_track():         return _bm_crm_mo_track()          # fallback


# ----------  original attribute + blueprint helpers (unchanged) ----------
def calculate_attribute_scores(assessment_scores):
    """
    Map assessment category scores to 10 key attributes
    FAR = Financial/Analytical Reasoning
    BM = Business/Market Acumen  
    CRM = Customer Relationship/Communication
    MO = Motivation/Operational Orientation
    """
    
    # Get total responses
    total = sum(assessment_scores.values()) or 1
    percentages = {k: (v/total)*100 for k,v in assessment_scores.items()}
    
    # Map to 10 key attributes (scores out of 10)
    attributes = {}
    
    # Accounting Knowledge - primarily from FAR responses
    far_score = percentages.get('FAR', 0)
    attributes['Accounting Knowledge'] = min(10, max(1, (far_score / 10) + random.uniform(0.5, 1.5)))
    
    # Quantitative & Math Skill - from FAR with some randomization
    attributes['Quantitative & Math Skill'] = min(10, max(1, (far_score / 12) + random.uniform(1.0, 2.0)))
    
    # Analytical & Critical Thinking - combination of FAR and BM
    bm_score = percentages.get('BM', 0)
    attributes['Analytical & Critical Thinking'] = min(10, max(1, ((far_score + bm_score) / 20) + random.uniform(0.8, 1.8)))
    
    # Attention to Detail - from FAR and MO
    mo_score = percentages.get('MO', 0)
    attributes['Attention to Detail'] = min(10, max(1, ((far_score + mo_score) / 18) + random.uniform(0.7, 1.7)))
    
    # Financial Concepts - primarily FAR
    attributes['Financial Concepts'] = min(10, max(1, (far_score / 11) + random.uniform(0.6, 1.6)))
    
    # Compliance & Ethics - combination of all categories
    crm_score = percentages.get('CRM', 0)
    avg_score = (far_score + bm_score + crm_score + mo_score) / 4
    attributes['Compliance & Ethics'] = min(10, max(1, (avg_score / 12) + random.uniform(0.9, 1.9)))
    
    # Business & Economic Acumen - primarily BM
    attributes['Business & Economic Acumen'] = min(10, max(1, (bm_score / 10) + random.uniform(0.8, 1.8)))
    
    # Communication Skills - primarily CRM
    attributes['Communication Skills'] = min(10, max(1, (crm_score / 10) + random.uniform(0.7, 1.7)))
    
    # Tech & Tool Familiarity - combination with emphasis on MO
    attributes['Tech & Tool Familiarity'] = min(10, max(1, ((mo_score + bm_score) / 18) + random.uniform(1.0, 2.0)))
    
    # Personality Preferences - combination of CRM and MO
    attributes['Personality Preferences'] = min(10, max(1, ((crm_score + mo_score) / 18) + random.uniform(0.8, 1.8)))
    
    # Round to 1 decimal place
    for key in attributes:
        attributes[key] = round(attributes[key], 1)
    
    return attributes


def generate_career_blueprint_report(user_name, assessment_scores, attributes):
    """Generate the complete Career Strengths Blueprint report"""
    
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Calculate overall career fit score
    avg_score = sum(attributes.values()) / len(attributes)
    career_fit_score = min(95, max(60, int(avg_score * 9.5)))  # Scale to percentage
    
    # Get top strengths
    sorted_attrs = sorted(attributes.items(), key=lambda x: x[1], reverse=True)
    top_strengths = [attr[0] for attr in sorted_attrs[:3]]
    
    # Get development areas (lowest scores)
    development_areas = [attr[0] for attr in sorted_attrs[-2:]]
    
    # Get career recommendations
    career_recommendations = get_career_recommendations(attributes)
    
    # Generate SWOT analysis
    swot = generate_swot_analysis(attributes, assessment_scores)
    
    # Generate the Markdown report
    report = f"""# Your Personalized Career Strengths Blueprint - Skill2Hire

## Based on Your Career Mapping Assessment Results

**Candidate:** {user_name}  
**Date:** {current_date}  
**Unlock your potential in finance and accounting!**

---

## Overall Summary

Congratulations on completing your Career Mapping Assessment! Based on your responses, we've identified your unique strengths and created a personalized roadmap for your finance and accounting career journey.

**Career Fit Score:** {career_fit_score}% Alignment with Finance Fields

**Your Top Strengths:** {', '.join(top_strengths)}

**Recommended Career Streams:** {', '.join([rec['title'] for rec in career_recommendations])}

**Development Focus Areas:** {', '.join(development_areas)}

---

## Personalized Attribute Profile

| Attribute | Your Score | Insights & Real-World Application |
|-----------|------------|-----------------------------------|
"""
    
    # Add attribute details
    for attr, score in sorted_attrs:
        if score >= 8.0:
            insight = f"**Exceptional strength** - You excel in this area and should leverage it in your career choices. Consider leadership roles that utilize this skill."
        elif score >= 6.5:
            insight = f"**Strong capability** - This is a solid foundation for your career. Continue building on this strength through advanced training."
        elif score >= 5.0:
            insight = f"**Developing skill** - Good foundation with room for growth. Targeted training and practice will help you excel."
        else:
            insight = f"**Growth opportunity** - Focus area for development. Consider foundational courses and mentorship in this area."
        
        report += f"| {attr} | {score}/10 | {insight} |\n"
    
    report += f"""

---

## Career Alignment Score & Recommendations

Based on your assessment results, here are your top 3 recommended career paths:

"""
    
    for i, rec in enumerate(career_recommendations, 1):
        report += f"""### {i}. {rec['title']}

**Why it fits:** {rec['description']}

**Next Steps:** {rec['next_steps']}

"""
    
    report += f"""---

## Scientific SWOT Analysis

| **Strengths** | **Weaknesses** |
|---------------|----------------|
"""
    
    # Add SWOT table
    max_items = max(len(swot['strengths']), len(swot['weaknesses']))
    for i in range(max_items):
        strength = swot['strengths'][i] if i < len(swot['strengths']) else ""
        weakness = swot['weaknesses'][i] if i < len(swot['weaknesses']) else ""
        report += f"| {strength} | {weakness} |\n"
    
    report += f"""
| **Opportunities** | **Threats** |
|-------------------|-------------|
"""
    
    max_items = max(len(swot['opportunities']), len(swot['threats']))
    for i in range(max_items):
        opportunity = swot['opportunities'][i] if i < len(swot['opportunities']) else ""
        threat = swot['threats'][i] if i < len(swot['threats']) else ""
        report += f"| {opportunity} | {threat} |\n"
    
    report += f"""

---

## Targeted Guidance & Next Steps

### Immediate Actions (Next 30 Days)
1. **Enroll in Skill2Hire Training:** Focus on programs that align with your top career recommendations
2. **Skill Assessment:** Take a deeper dive into your development areas with targeted practice
3. **Network Building:** Connect with professionals in your recommended career fields

### Short-term Goals (3-6 Months)
4. **Certification Pursuit:** Begin working toward relevant industry certifications
5. **Practical Experience:** Seek internships, projects, or volunteer opportunities in your target areas

### Long-term Vision (6-12 Months)
6. **Career Transition:** Use your strengthened skills to pursue roles in your recommended career streams
7. **Continuous Learning:** Stay updated with industry trends and continue skill development

### Skill2Hire Training Recommendations
Based on your profile, we recommend exploring these Skill2Hire programs:
- **Financial Planning & Analysis (FP&A)** - Perfect for analytical minds
- **QuickBooks Certification** - Essential for accounting operations
- **US GAAP/IFRS** - Build strong accounting knowledge foundation
- **Excel & PowerBI** - Enhance your quantitative skills

**Ready to take the next step?** Contact our career counselors for a personalized training plan.

---

## Footer

**Learn with Purpose. Get Hired with Confidence.**

**Contact Skill2Hire:**
- Website: www.skill2hire.com
- Email: info@skill2hire.com
- Phone: +1-800-SKILL2H

*To download this report as PDF, copy this Markdown content into a converter tool like markdown-to-pdf.com or print to PDF from your browser.*

---

*This report is generated based on your Career Mapping Assessment responses and provides personalized insights for your finance and accounting career journey. Results are indicative and should be used as guidance alongside professional career counseling.*
"""
    
    return report


# Add the missing helper functions that are referenced but not defined
def get_career_recommendations(attributes):
    """Generate career recommendations based on attribute scores"""
    recommendations = []
    
    # Sort attributes by score
    sorted_attrs = sorted(attributes.items(), key=lambda x: x[1], reverse=True)
    top_attrs = [attr[0] for attr in sorted_attrs[:3]]
    
    # Basic recommendation logic
    if 'Accounting Knowledge' in top_attrs and 'Financial Concepts' in top_attrs:
        recommendations.append({
            'title': 'Financial Analyst',
            'description': 'Your strong accounting and financial knowledge make you well-suited for analyzing financial data and supporting business decisions.',
            'next_steps': 'Consider pursuing CPA certification and advanced Excel/financial modeling skills.'
        })
    
    if 'Communication Skills' in top_attrs and 'Business & Economic Acumen' in top_attrs:
        recommendations.append({
            'title': 'Business Consultant',
            'description': 'Your communication skills and business understanding position you well for client-facing consulting roles.',
            'next_steps': 'Develop industry expertise and consider project management certifications.'
        })
    
    if 'Analytical & Critical Thinking' in top_attrs:
        recommendations.append({
            'title': 'Operations Analyst',
            'description': 'Your analytical abilities are perfect for optimizing business processes and identifying improvement opportunities.',
            'next_steps': 'Learn data analysis tools like Python/R and Lean Six Sigma methodologies.'
        })
    
    # Ensure we always have at least 3 recommendations
    while len(recommendations) < 3:
        recommendations.append({
            'title': 'Finance & Accounting Professional',
            'description': 'Your assessment results show good potential for various finance and accounting roles.',
            'next_steps': 'Focus on building technical skills in accounting software and financial analysis.'
        })
    
    return recommendations[:3]


def generate_swot_analysis(attributes, assessment_scores):
    """Generate SWOT analysis based on attributes and assessment scores"""
    sorted_attrs = sorted(attributes.items(), key=lambda x: x[1], reverse=True)
    
    strengths = []
    weaknesses = []
    
    # Strengths from top attributes
    for attr, score in sorted_attrs[:3]:
        if score >= 7.0:
            strengths.append(f"Strong {attr.lower()} capabilities")
    
    # Weaknesses from bottom attributes
    for attr, score in sorted_attrs[-2:]:
        if score <= 5.0:
            weaknesses.append(f"Opportunity to develop {attr.lower()}")
    
    # Generic opportunities and threats
    opportunities = [
        "Growing demand for finance professionals with diverse skill sets",
        "Digital transformation creating new career paths",
        "Increasing focus on data-driven decision making"
    ]
    
    threats = [
        "Automation of routine financial tasks",
        "Need for continuous skill updating",
        "Competitive job market requiring specialization"
    ]
    
    return {
        'strengths': strengths,
        'weaknesses': weaknesses,
        'opportunities': opportunities,
        'threats': threats
    }