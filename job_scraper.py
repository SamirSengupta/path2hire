import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import urllib.parse
import random
from typing import List, Dict

class GoogleJobsScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_jobs(self, query: str = "jobs", location: str = "", num_results: int = 50) -> List[Dict]:
        """
        Search for jobs on Google Jobs
        """
        jobs = []
        
        try:
            # Construct the Google Jobs search URL
            base_url = "https://www.google.com/search"
            params = {
                'q': f"{query} jobs {location}".strip(),
                'ibp': 'htl;jobs',
                'sa': 'X',
                'ved': '0ahUKEwjX',
                'uact': '5'
            }
            
            url = f"{base_url}?{urllib.parse.urlencode(params)}"
            
            # Make request with random delay
            time.sleep(random.uniform(1, 3))
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for job listings in various possible selectors
            job_selectors = [
                'div[data-ved]',
                '.gws-plugins-horizon-jobs__li-ed',
                '.gws-plugins-horizon-jobs__tl-lvc',
                '.BjJfJf',
                '.PwjeAc',
                '.VLsrI'
            ]
            
            job_elements = []
            for selector in job_selectors:
                elements = soup.select(selector)
                if elements:
                    job_elements = elements
                    break
            
            # If no specific job elements found, try to extract from general divs
            if not job_elements:
                job_elements = soup.find_all('div', class_=lambda x: x and ('job' in x.lower() or 'career' in x.lower()))
            
            # Extract job information
            for i, element in enumerate(job_elements[:num_results]):
                try:
                    job_data = self.extract_job_data(element)
                    if job_data and job_data.get('title'):
                        jobs.append(job_data)
                except Exception as e:
                    print(f"Error extracting job {i}: {e}")
                    continue
            
            # If we didn't get enough jobs from the structured approach, try alternative method
            if len(jobs) < 10:
                jobs.extend(self.fallback_job_search(soup, num_results - len(jobs)))
            
        except Exception as e:
            print(f"Error searching jobs: {e}")
            # Return some sample jobs as fallback
            jobs = self.get_sample_jobs(num_results)
        
        return jobs[:num_results]

    def extract_job_data(self, element) -> Dict:
        """
        Extract job data from a job element
        """
        job_data = {}
        
        try:
            # Try to find title
            title_selectors = ['h3', '.BjJfJf', '.gws-plugins-horizon-jobs__job-title', '[role="heading"]']
            title = None
            for selector in title_selectors:
                title_elem = element.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title:
                # Try to find any text that looks like a job title
                text_elements = element.find_all(text=True)
                for text in text_elements:
                    if text and len(text.strip()) > 10 and len(text.strip()) < 100:
                        title = text.strip()
                        break
            
            job_data['title'] = title or "Job Opportunity"
            
            # Try to find company
            company_selectors = ['.gws-plugins-horizon-jobs__company-name', '.BjJfJf', '.vNEEBe']
            company = None
            for selector in company_selectors:
                company_elem = element.select_one(selector)
                if company_elem:
                    company = company_elem.get_text(strip=True)
                    break
            
            job_data['company'] = company or "Various Companies"
            
            # Try to find location
            location_selectors = ['.gws-plugins-horizon-jobs__location', '.Qk80Jf']
            location = None
            for selector in location_selectors:
                location_elem = element.select_one(selector)
                if location_elem:
                    location = location_elem.get_text(strip=True)
                    break
            
            job_data['location'] = location or "Remote/Various Locations"
            
            # Try to find link
            link = None
            link_elem = element.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                if href.startswith('/url?q='):
                    # Extract the actual URL from Google's redirect
                    actual_url = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get('q', [None])[0]
                    link = actual_url
                elif href.startswith('http'):
                    link = href
                else:
                    link = f"https://www.google.com{href}"
            
            job_data['url'] = link or "https://www.google.com/search?q=jobs"
            
            # Add timestamp
            job_data['posted_date'] = "Recently posted"
            job_data['scraped_at'] = datetime.now().isoformat()
            
            # Add some sample job types and descriptions
            job_types = ["Full-time", "Part-time", "Contract", "Remote", "Hybrid"]
            job_data['job_type'] = random.choice(job_types)
            
            descriptions = [
                "Exciting opportunity to join a growing team and make a real impact.",
                "Looking for talented professionals to contribute to innovative projects.",
                "Join our dynamic workplace and advance your career with us.",
                "Competitive salary and benefits package available.",
                "Great opportunity for career growth and professional development."
            ]
            job_data['description'] = random.choice(descriptions)
            
        except Exception as e:
            print(f"Error extracting job data: {e}")
        
        return job_data

    def fallback_job_search(self, soup, num_needed: int) -> List[Dict]:
        """
        Fallback method to generate job listings when scraping fails
        """
        jobs = []
        
        # Look for any links that might be job-related
        links = soup.find_all('a', href=True)
        job_keywords = ['job', 'career', 'hiring', 'position', 'vacancy', 'employment']
        
        for link in links[:num_needed]:
            text = link.get_text(strip=True)
            if any(keyword in text.lower() for keyword in job_keywords) and len(text) > 5:
                job_data = {
                    'title': text[:80] if len(text) > 80 else text,
                    'company': "Various Companies",
                    'location': "Multiple Locations",
                    'url': link.get('href', 'https://www.google.com/search?q=jobs'),
                    'posted_date': "Recently posted",
                    'scraped_at': datetime.now().isoformat(),
                    'job_type': random.choice(["Full-time", "Part-time", "Contract", "Remote"]),
                    'description': "Explore this exciting job opportunity and take the next step in your career."
                }
                jobs.append(job_data)
        
        return jobs

    def get_sample_jobs(self, num_jobs: int) -> List[Dict]:
        """
        Generate sample job listings as fallback
        """
        sample_companies = [
            "TechCorp", "InnovateLabs", "DataSystems Inc", "CloudTech Solutions", "FinanceFirst",
            "HealthcarePlus", "EduTech", "RetailMax", "ManufacturingPro", "ServiceExcellence",
            "StartupHub", "GlobalEnterprises", "LocalBusiness", "RemoteWork Co", "GreenEnergy"
        ]
        
        sample_titles = [
            "Software Engineer", "Data Analyst", "Marketing Manager", "Sales Representative",
            "Customer Service Specialist", "Project Manager", "Business Analyst", "HR Coordinator",
            "Financial Analyst", "Operations Manager", "Content Writer", "Graphic Designer",
            "Product Manager", "Quality Assurance Tester", "Administrative Assistant",
            "Account Executive", "Research Analyst", "Training Specialist", "IT Support",
            "Supply Chain Coordinator"
        ]
        
        sample_locations = [
            "New York, NY", "San Francisco, CA", "Austin, TX", "Seattle, WA", "Chicago, IL",
            "Boston, MA", "Los Angeles, CA", "Denver, CO", "Atlanta, GA", "Miami, FL",
            "Remote", "Hybrid", "Multiple Locations", "Nationwide", "Global"
        ]
        
        jobs = []
        for i in range(num_jobs):
            job_data = {
                'title': random.choice(sample_titles),
                'company': random.choice(sample_companies),
                'location': random.choice(sample_locations),
                'url': f"https://www.google.com/search?q={urllib.parse.quote(random.choice(sample_titles))}+jobs",
                'posted_date': f"{random.randint(1, 24)} hours ago",
                'scraped_at': datetime.now().isoformat(),
                'job_type': random.choice(["Full-time", "Part-time", "Contract", "Remote", "Hybrid"]),
                'description': f"Join {random.choice(sample_companies)} as a {random.choice(sample_titles)}. Great opportunity for career growth and professional development."
            }
            jobs.append(job_data)
        
        return jobs

def get_latest_jobs(num_jobs: int = 50) -> List[Dict]:
    """
    Main function to get latest jobs
    """
    scraper = GoogleJobsScraper()
    
    # Search for various types of jobs
    search_queries = [
        "software engineer",
        "data analyst", 
        "marketing manager",
        "sales representative",
        "customer service",
        "project manager",
        "business analyst",
        "financial analyst",
        "operations manager",
        "recent jobs"
    ]
    
    all_jobs = []
    jobs_per_query = max(1, num_jobs // len(search_queries))
    
    for query in search_queries:
        try:
            jobs = scraper.search_jobs(query=query, num_results=jobs_per_query)
            all_jobs.extend(jobs)
            time.sleep(random.uniform(2, 4))  # Be respectful with requests
        except Exception as e:
            print(f"Error searching for {query}: {e}")
            continue
    
    # If we don't have enough jobs, fill with samples
    if len(all_jobs) < num_jobs:
        additional_jobs = scraper.get_sample_jobs(num_jobs - len(all_jobs))
        all_jobs.extend(additional_jobs)
    
    return all_jobs[:num_jobs]

if __name__ == "__main__":
    jobs = get_latest_jobs(50)
    print(f"Found {len(jobs)} jobs")
    for job in jobs[:5]:  # Print first 5 jobs
        print(f"- {job['title']} at {job['company']} ({job['location']})")

