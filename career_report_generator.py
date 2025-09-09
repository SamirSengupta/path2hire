"""
Career Strengths Blueprint Report Generator for Skill2Hire
Maps assessment results to 10 key attributes and generates comprehensive reports
"""

from datetime import datetime
import random

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

def get_career_recommendations(attributes):
    """Generate career recommendations based on attribute scores"""
    
    # Sort attributes by score
    sorted_attrs = sorted(attributes.items(), key=lambda x: x[1], reverse=True)
    top_3 = [attr[0] for attr in sorted_attrs[:3]]
    
    recommendations = []
    
    # Financial Planning & Analysis
    if any(attr in top_3 for attr in ['Accounting Knowledge', 'Quantitative & Math Skill', 'Analytical & Critical Thinking']):
        recommendations.append({
            'title': 'Financial Planning & Analysis (FP&A)',
            'description': 'Perfect for analytical minds who enjoy working with numbers and strategic planning.',
            'next_steps': 'Consider FP&A certification, Excel/PowerBI training, and financial modeling courses.'
        })
    
    # Accounting Operations
    if any(attr in top_3 for attr in ['Accounting Knowledge', 'Attention to Detail', 'Compliance & Ethics']):
        recommendations.append({
            'title': 'Accounting Operations',
            'description': 'Ideal for detail-oriented professionals who value accuracy and compliance.',
            'next_steps': 'Pursue accounting certifications (CPA, ACCA), QuickBooks training, and process improvement skills.'
        })
    
    # Risk Management
    if any(attr in top_3 for attr in ['Analytical & Critical Thinking', 'Compliance & Ethics', 'Business & Economic Acumen']):
        recommendations.append({
            'title': 'Risk Management',
            'description': 'Great for strategic thinkers who can assess and mitigate business risks.',
            'next_steps': 'Study risk management frameworks, regulatory compliance, and business analysis techniques.'
        })
    
    # Business Analysis
    if any(attr in top_3 for attr in ['Business & Economic Acumen', 'Communication Skills', 'Analytical & Critical Thinking']):
        recommendations.append({
            'title': 'Business Analysis',
            'description': 'Suitable for professionals who bridge business needs with technical solutions.',
            'next_steps': 'Learn business analysis methodologies, stakeholder management, and process mapping.'
        })
    
    # Financial Consulting
    if any(attr in top_3 for attr in ['Communication Skills', 'Business & Economic Acumen', 'Financial Concepts']):
        recommendations.append({
            'title': 'Financial Consulting',
            'description': 'Perfect for client-facing roles requiring financial expertise and communication skills.',
            'next_steps': 'Develop presentation skills, industry knowledge, and client relationship management.'
        })
    
    return recommendations[:3]  # Return top 3 recommendations

def generate_swot_analysis(attributes, assessment_scores):
    """Generate SWOT analysis based on attributes"""
    
    sorted_attrs = sorted(attributes.items(), key=lambda x: x[1], reverse=True)
    
    # Strengths (top 3-4 attributes)
    strengths = []
    for attr, score in sorted_attrs[:4]:
        if score >= 7.0:
            strengths.append(f"Strong {attr.lower()} ({score}/10)")
        elif score >= 5.5:
            strengths.append(f"Good {attr.lower()} foundation ({score}/10)")
    
    # Weaknesses (bottom 2-3 attributes)
    weaknesses = []
    for attr, score in sorted_attrs[-3:]:
        if score < 4.0:
            weaknesses.append(f"Limited {attr.lower()} ({score}/10)")
        elif score < 6.0:
            weaknesses.append(f"Developing {attr.lower()} skills ({score}/10)")
    
    # Opportunities
    opportunities = [
        "Growing demand for finance professionals with tech skills",
        "Remote work opportunities in finance and accounting",
        "Skill2Hire's comprehensive training programs",
        "Industry certifications to boost credibility"
    ]
    
    # Threats
    threats = [
        "Automation of basic accounting tasks",
        "Increasing competition in finance job market",
        "Rapid changes in financial regulations",
        "Need for continuous skill updates"
    ]
    
    return {
        'strengths': strengths[:4],
        'weaknesses': weaknesses[:3],
        'opportunities': opportunities,
        'threats': threats
    }

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

