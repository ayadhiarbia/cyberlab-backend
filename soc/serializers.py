from rest_framework import serializers
from .models import SecurityEvent, Alert, Incident


class SecurityEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityEvent
        fields = '__all__'


class AlertSerializer(serializers.ModelSerializer):
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Alert
        fields = [
            'id', 'title', 'description', 'severity', 'severity_display',
            'status', 'status_display', 'events', 'created_at'
        ]


class IncidentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    
    class Meta:
        model = Incident
        fields = [
            'id', 'title', 'description', 'severity', 'severity_display',
            'status', 'status_display', 'alert', 'assigned_to', 'assigned_to_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']



from .models import IncidentEvidence, IncidentHistory

class IncidentEvidenceSerializer(serializers.ModelSerializer):
    added_by_username = serializers.CharField(source='added_by.username', read_only=True)
    
    class Meta:
        model = IncidentEvidence
        fields = ['id', 'incident', 'description', 'file_hash', 'added_by', 'added_by_username', 'created_at']
        read_only_fields = ['id', 'incident', 'added_by', 'created_at']


class IncidentHistorySerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True)
    
    class Meta:
        model = IncidentHistory
        fields = ['id', 'incident', 'action', 'details', 'performed_by', 'performed_by_username', 'timestamp']
        read_only_fields = ['id', 'incident', 'performed_by', 'timestamp']