from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from .models import Bulletin, Vulnerability, Remediation
from .serializers import BulletinSerializer, VulnerabilitySerializer, RemediationSerializer
from .scraper import scrape_nvd_for_bulletin  # <-- Real Scraper Import
from labs.models import Lab
from labs.permissions import IsTrainerOrAdmin
from ai.llm_client import OllamaClient, OllamaError


class BulletinViewSet(viewsets.ModelViewSet):
    """API to manage Scraped Bulletins."""
    queryset = Bulletin.objects.all().order_by('-created_at')
    serializer_class = BulletinSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'], url_path='scrape')
    def scrape(self, request, pk=None):
        """Trigger the real NVD scraper for this bulletin."""
        bulletin = self.get_object()
        
        try:
            count = scrape_nvd_for_bulletin(bulletin)
            if count == 0:
                return Response({"detail": "No new vulnerabilities found in the last 7 days."})
            return Response({"detail": f"Successfully scraped {count} real vulnerabilities from NVD into '{bulletin.title}'."})
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class VulnerabilityViewSet(viewsets.ModelViewSet):
    """API to manage Vulnerabilities."""
    queryset = Vulnerability.objects.all().order_by('-cvss_score')
    serializer_class = VulnerabilitySerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['patch'], url_path='assign-to-lab')
    def assign_to_lab(self, request, pk=None):
        """Assign a vulnerability to a specific Lab."""
        if request.user.role not in ['TRAINER', 'ADMIN']:
            raise ValidationError({"detail": "Accès refusé."})
            
        vuln = self.get_object()
        lab_id = request.data.get('lab_id')
        
        if not lab_id:
            raise ValidationError({"detail": "lab_id is required."})
            
        try:
            lab = Lab.objects.get(id=lab_id)
        except Lab.DoesNotExist:
            raise ValidationError({"detail": "Lab not found."})
            
        vuln.target_lab = lab
        vuln.save()
        return Response({"detail": f"Vulnerability assigned to {lab.title}."})

    @action(detail=True, methods=['post'], url_path='ai-recommendation')
    def ai_recommendation(self, request, pk=None):
        """Use the LLM to suggest a fix for this vulnerability."""
        vuln = self.get_object()
        client = OllamaClient()
        
        prompt = f"""Tu es un expert en cybersécurité. Voici une faille :
CVE: {vuln.cve_id}
Produit: {vuln.affected_product}
Description: {vuln.description}

Donne une recommandation technique détaillée pour corriger cette faille."""
        
        try:
            response = client.generate(prompt=prompt, system="Tu es un expert en cybersécurité.")
            return Response({"cve": vuln.cve_id, "ai_recommendation": response})
        except OllamaError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class RemediationViewSet(viewsets.ModelViewSet):
    """API to submit a fix for a vulnerability."""
    queryset = Remediation.objects.all()
    serializer_class = RemediationSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        vuln = serializer.validated_data['vulnerability']
        
        # Mark the vulnerability as resolved automatically
        vuln.status = Vulnerability.Status.RESOLVED
        vuln.save()
        
        serializer.save(fixed_by=self.request.user)