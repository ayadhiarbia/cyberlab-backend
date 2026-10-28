from rest_framework import serializers
from .models import Bulletin, Vulnerability, Remediation


class BulletinSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    vulnerability_count = serializers.IntegerField(source='vulnerabilities.count', read_only=True)

    class Meta:
        model = Bulletin
        fields = ['id', 'title', 'source', 'created_by', 'created_by_username', 'vulnerability_count', 'created_at']
        read_only_fields = ['id', 'created_by', 'created_at']


class VulnerabilitySerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    lab_title = serializers.CharField(source='target_lab.title', read_only=True, default=None)

    class Meta:
        model = Vulnerability
        fields = [
            'id', 'bulletin', 'target_lab', 'lab_title',
            'cve_id', 'title', 'description', 'severity', 'severity_display',
            'cvss_score', 'epss_score', 'is_kev', 'cpe_target', 'affected_product',
            'status', 'status_display', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RemediationSerializer(serializers.ModelSerializer):
    fixed_by_username = serializers.CharField(source='fixed_by.username', read_only=True)

    class Meta:
        model = Remediation
        fields = ['id', 'vulnerability', 'patch_details', 'proof_of_fix', 'fixed_by', 'fixed_by_username', 'fixed_at']
        read_only_fields = ['id', 'vulnerability', 'fixed_by', 'fixed_at']