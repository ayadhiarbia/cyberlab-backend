import requests
from datetime import datetime, timedelta
from .models import Vulnerability

def scrape_nvd_for_bulletin(bulletin):
    """
    Fetches real CVEs from the NVD API for the last 7 days
    and saves them to the provided bulletin.
    Returns the number of vulnerabilities added.
    """
    # 1. Define the time range (Last 7 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    # Format dates for the NVD API (ISO 8601)
    start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.000')
    end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.000')
    
    # 2. Call the NVD API
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?pubStartDate={start_str}&pubEndDate={end_str}"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to connect to NVD: {str(e)}")

    vulnerabilities = data.get('vulnerabilities', [])
    
    if not vulnerabilities:
        return 0

    count = 0
    # We limit to 15 to avoid taking too long in a single test
    for item in vulnerabilities[:15]: 
        cve = item.get('cve', {})
        cve_id = cve.get('id')
        
        # Skip if we already have this CVE in the database
        if Vulnerability.objects.filter(cve_id=cve_id).exists():
            continue

        # --- Extract Description ---
        descriptions = cve.get('descriptions', [])
        description = next((d['value'] for d in descriptions if d['lang'] == 'en'), "No description available.")
        
        # --- Extract CVSS Score & Severity ---
        metrics = cve.get('metrics', {})
        cvss_data = metrics.get('cvssMetricV31', [{}])[0].get('cvssData', {})
        
        cvss_score = cvss_data.get('baseScore', 0.0)
        severity = cvss_data.get('baseSeverity', 'MEDIUM').upper()
        
        # Create the record
        Vulnerability.objects.create(
            bulletin=bulletin,
            cve_id=cve_id,
            title=f"Vulnerability in {cve_id}",
            description=description,
            cvss_score=cvss_score,
            severity=severity,
            affected_product="See description", # NVD uses complex CPE strings, we simplify for now
            status=Vulnerability.Status.OPEN
        )
        count += 1

    return count