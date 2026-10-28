"""
Generates a synthetic — but realistically noisy — dataset of security
events for training the AI SOC Analyst event classifier.

Compared to a "trivial" synthetic dataset, this version includes:
  - ambiguous examples (text that could belong to 2 classes)
  - class imbalance (realistic — attacks are rare, normal traffic is common)
  - label noise (3% of labels are deliberately wrong — real SOCs are noisy)
  - varied formats (different log styles, mixed casing, junk characters)

6 classes: BRUTE_FORCE, SQL_INJECTION, XSS, PHISHING, MALWARE, NORMAL
"""

import csv
import random
from pathlib import Path

random.seed(42)

OUTPUT = Path(__file__).parent / "events_dataset.csv"

# Class imbalance — NORMAL is common, attacks are rarer (realistic)
CLASS_WEIGHTS = {
    "NORMAL": 180,
    "BRUTE_FORCE": 120,
    "SQL_INJECTION": 90,
    "XSS": 70,
    "PHISHING": 80,
    "MALWARE": 60,
}

LABEL_NOISE_RATE = 0.03   # 3% of examples get a wrong label on purpose


def _rand_ip():
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _rand_internal_ip():
    return f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _rand_user():
    return random.choice([
        "admin", "root", "user01", "alice", "bob", "carol",
        "oracle", "postgres", "ubuntu", "guest", "test", "sysadmin"
    ])


def _noisy(text):
    """Randomly corrupt text to simulate real-world log noise."""
    r = random.random()
    if r < 0.05:
        return text.upper()
    if r < 0.10:
        return text.lower()
    if r < 0.15:
        # Random typo: swap two adjacent chars
        i = random.randint(0, max(0, len(text) - 2))
        return text[:i] + text[i + 1] + text[i] + text[i + 2:]
    return text


# ---------------------------------------------------------------------------
# Generators — each class
# ---------------------------------------------------------------------------

def gen_brute_force():
    """Some are obvious, some are ambiguous (successful login after failures)."""
    user = _rand_user()
    ip = _rand_ip()
    port = random.randint(1024, 65000)
    variants = [
        # Obvious
        f"Failed password for {user} from {ip} port {port} ssh2",
        f"authentication failure for {user} from {ip}",
        f"Failed login attempt for '{user}' from {ip}",
        # Success AFTER failures — still brute force (attack succeeded)
        f"Accepted password for {user} from {ip} after 5 failed attempts",
        f"User {user} logged in from {ip} following 12 consecutive failures",
        # Very subtle
        f"pam_unix(sshd:auth): {user} {ip} repeated auth requests",
    ]
    return _noisy(random.choice(variants))


def gen_sql_injection():
    payload = random.choice([
        "1' OR '1'='1", "1 UNION SELECT username, password FROM users--",
        "'; DROP TABLE users;--", "admin'--", "' OR 1=1--",
    ])
    path = random.choice(["/index.php", "/login.php", "/product.php", "/search.php"])
    # Some look "clean" but are actually injection attempts
    variants = [
        f"GET {path}?id={payload} HTTP/1.1 200",
        f"POST {path} HTTP/1.1 500 (username='{payload}')",
        f"SQL error: syntax error near '{payload}'",
        f"WAF alert: sql_injection blocked on parameter id",
        # Ambiguous: SQL error but not necessarily injection (could be a bug)
        f"Database error 1064 in query on {path}",
    ]
    return _noisy(random.choice(variants))


def gen_xss():
    payload = random.choice([
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<svg/onload=alert(1)>",
    ])
    path = random.choice(["/search", "/comment", "/profile"])
    variants = [
        f"GET {path}?q={payload} HTTP/1.1 200",
        f"Reflected XSS detected in parameter 'q'",
        f"Stored XSS in profile bio: {payload}",
        # AMBIGUOUS: legitimate search containing a <script> tag as plain text
        f"GET /search?q=how+to+use+%3Cscript%3E+tag HTTP/1.1 200",
    ]
    return _noisy(random.choice(variants))


def gen_phishing():
    domain = random.choice(["paypa1.com", "micros0ft.net", "bank-login.org"])
    sender = random.choice(["support", "security", "no-reply"])
    subject = random.choice([
        "Urgent: verify your account",
        "Your password will expire",
        "Unusual sign-in activity",
    ])
    variants = [
        f"Email from {sender}@{domain} subject='{subject}' with suspicious link",
        f"Phishing email blocked: sender={sender}@{domain}",
        # AMBIGUOUS: legitimate password-reset request
        f"User requested password reset email from {sender}@internal.corp",
        f"Marketing email from {sender}@company.com flagged by user",
    ]
    return _noisy(random.choice(variants))


def gen_malware():
    process = random.choice(["svchost.exe", "rundll32.exe", "powershell.exe"])
    path = random.choice([
        r"C:\Temp\update.exe", r"C:\Users\Public\svc.exe",
        r"C:\Windows\Temp\a1b2.tmp",
    ])
    variants = [
        f"Process {process} spawned from {path}",
        f"AV alert: suspicious file {path}",
        f"Registry Run key modified: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
        # AMBIGUOUS: signed binary in a normal location, but unusual
        f"Process {process} executed from C:\\Windows\\System32 (signed)",
    ]
    return _noisy(random.choice(variants))


def gen_normal():
    user = _rand_user()
    ip = _rand_internal_ip()
    path = random.choice(["/", "/dashboard", "/api/status", "/health"])
    variants = [
        f"User {user} logged in successfully from {ip}",
        f"GET {path} HTTP/1.1 200 OK",
        f"Session started for {user}",
        f"Scheduled backup completed successfully",
        # AMBIGUOUS: failed login due to typo (not an attack)
        f"Failed login for {user} — user mistyped password (1 attempt only)",
        # AMBIGUOUS: contains '<script>' as plain text (not XSS)
        f"GET /search?q=%3Cscript%3E+example HTTP/1.1 200",
        # AMBIGUOUS: email that mentions "password" but is internal
        f"Internal email from helpdesk@corp.local about password policy",
        # AMBIGUOUS: SQL keyword in a legitimate search
        f"GET /docs?topic=SELECT+statement+in+SQL HTTP/1.1 200",
    ]
    return _noisy(random.choice(variants))


GENERATORS = {
    "BRUTE_FORCE": gen_brute_force,
    "SQL_INJECTION": gen_sql_injection,
    "XSS": gen_xss,
    "PHISHING": gen_phishing,
    "MALWARE": gen_malware,
    "NORMAL": gen_normal,
}


def main():
    rows = []
    for label, gen in GENERATORS.items():
        for _ in range(CLASS_WEIGHTS[label]):
            rows.append({"text": gen(), "label": label})

    # Inject label noise (3% of labels randomly swapped)
    for row in rows:
        if random.random() < LABEL_NOISE_RATE:
            row["label"] = random.choice(list(GENERATORS.keys()))

    random.shuffle(rows)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(rows)

    # Print distribution
    print(f"Dataset written to {OUTPUT}")
    print(f"Total rows: {len(rows)}")
    from collections import Counter
    counts = Counter(r["label"] for r in rows)
    for label, count in sorted(counts.items()):
        print(f"  {label}: {count}")


if __name__ == "__main__":
    main()