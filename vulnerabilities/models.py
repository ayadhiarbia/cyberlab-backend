from django.conf import settings
from django.db import models
from labs.models import Lab


class Bulletin(models.Model):
    """A scraping session (e.g., Bulletin #001 from TunCERT)."""
    title = models.CharField(max_length=255)
    source = models.CharField(max_length=100, default="TunCERT")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Vulnerability(models.Model):
    """Represents a CVE (Common Vulnerability and Exposure)."""
    class Severity(models.TextChoices):
        LOW = 'LOW', 'Basse'
        MEDIUM = 'MEDIUM', 'Moyenne'
        HIGH = 'HIGH', 'Haute'
        CRITICAL = 'CRITICAL', 'Critique'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Ouverte'
        IN_PROGRESS = 'IN_PROGRESS', 'En cours de correction'
        RESOLVED = 'RESOLVED', 'Corrigée'
        RISK_ACCEPTED = 'RISK_ACCEPTED', 'Risque accepté'

    # --- Link to Bulletin & Lab ---
    bulletin = models.ForeignKey(Bulletin, on_delete=models.CASCADE, related_name='vulnerabilities', null=True)
    target_lab = models.ForeignKey(Lab, on_delete=models.SET_NULL, null=True, blank=True, related_name='vulnerabilities', help_text="Le lab où cette faille doit être corrigée")

    # --- Identifiants & Description ---
    cve_id = models.CharField(max_length=20, unique=True, help_text="ex: CVE-2024-1234")
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # --- Scoring & Risk ---
    cvss_score = models.FloatField(help_text="Score CVSS de 0.0 à 10.0", default=5.0)
    epss_score = models.FloatField(help_text="Score EPSS (0.0 à 1.0)", default=0.0, blank=True, null=True)
    is_kev = models.BooleanField(default=False, help_text="Est-ce dans le catalogue KEV ?")
    
    # --- Produit affecté (CPE) ---
    cpe_target = models.CharField(max_length=255, blank=True)
    affected_product = models.CharField(max_length=255)
    
    # --- Workflow ---
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-cvss_score', '-epss_score', '-created_at']

    def __str__(self):
        return f"[{self.severity}] {self.cve_id} - {self.title}"


class Remediation(models.Model):
    """The proof/fix applied for a vulnerability (done by the student)."""
    vulnerability = models.OneToOneField(Vulnerability, on_delete=models.CASCADE, related_name='remediation')
    patch_details = models.TextField(help_text="Description de la correction appliquée")
    proof_of_fix = models.TextField(blank=True, help_text="Lien, logs ou capture d'écran")
    
    fixed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    fixed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Remediation for {self.vulnerability.cve_id}"