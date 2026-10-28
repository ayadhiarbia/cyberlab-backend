from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import SecurityEvent, Alert, Incident, IncidentEvidence, IncidentHistory
from .serializers import (
    SecurityEventSerializer, AlertSerializer, IncidentSerializer,
    IncidentEvidenceSerializer, IncidentHistorySerializer
)
from accounts.permissions import IsAdminRole
from labs.permissions import IsTrainerOrAdmin
from rest_framework.views import APIView
from django.db.models import Count, Q


class SecurityEventViewSet(viewsets.ModelViewSet):
    """
    API to create and view Security Events.
    """
    queryset = SecurityEvent.objects.all()
    serializer_class = SecurityEventSerializer
    permission_classes = [IsAuthenticated] # Anyone logged in can submit an event (e.g., from a lab)

    def perform_create(self, serializer):
        event = serializer.save()
        
        # --- Simple Rule Engine ---
        # If this event is HIGH or CRITICAL, check if 3+ similar events happened in the last 5 minutes
        if event.severity in ['HIGH', 'CRITICAL']:
            time_threshold = timezone.now() - timedelta(minutes=5)
            recent_events = SecurityEvent.objects.filter(
                event_type=event.event_type,
                source_ip=event.source_ip,
                severity__in=['HIGH', 'CRITICAL'],
                timestamp__gte=time_threshold
            )
            
            if recent_events.count() >= 3:
                # Check if we already created an alert for this exact thing recently
                if not Alert.objects.filter(title=f"Multiple {event.event_type} detected", created_at__gte=time_threshold).exists():
                    alert = Alert.objects.create(
                        title=f"Multiple {event.event_type} detected",
                        description=f"Detected {recent_events.count()} {event.event_type} events from {event.source_ip} within 5 minutes.",
                        severity=event.severity
                    )
                    alert.events.set(recent_events)


class AlertViewSet(viewsets.ModelViewSet):
    """
    API to view and manage alerts.
    """
    queryset = Alert.objects.all().order_by('-created_at')
    serializer_class = AlertSerializer

    def get_permissions(self):
        # Only trainers/admins can ignore alerts
        if self.action in ['ignore']:
            return [IsAuthenticated(), IsTrainerOrAdmin()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='promote-to-incident')
    def promote_to_incident(self, request, pk=None):
        """Convert an Alert into an Incident."""
        alert = self.get_object()
        
        if alert.status == Alert.Status.INCIDENT:
            raise ValidationError({"detail": "This alert is already an incident."})
            
        incident = Incident.objects.create(
            title=f"Incident: {alert.title}",
            description=alert.description,
            severity=alert.severity,
            alert=alert
        )
        
        alert.status = Alert.Status.INCIDENT
        alert.save()
        
        return Response(
            {"detail": "Alert promoted to Incident.", "incident_id": incident.id},
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], url_path='analyze-ai')
    def analyze_ai(self, request, pk=None):
        """Trigger the local LLM to analyze this alert."""
        from ai.services import SOCAgent
        from ai.llm_client import OllamaError

        alert = self.get_object()
        
        # Gather events associated with this alert
        events_list = [
            f"[{e.severity}] {e.event_type} from {e.source_ip} on {e.target_asset}" 
            for e in alert.events.all()
        ]

        agent = SOCAgent()
        try:
            analysis = agent.analyze(
                alert_type=alert.title,
                initial_severity=alert.severity,
                source=alert.events.first().source_ip if alert.events.exists() else "Unknown",
                target=alert.events.first().target_asset if alert.events.exists() else "Unknown",
                events=events_list
            )
            return Response({
                "alert_id": alert.id,
                "ai_analysis": analysis
            }, status=status.HTTP_200_OK)
            
        except OllamaError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )



class IncidentViewSet(viewsets.ModelViewSet):
    """
    API to manage Incident lifecycle (investigation, resolution).
    """
    queryset = Incident.objects.all().order_by('-created_at')
    serializer_class = IncidentSerializer

    def get_permissions(self):
        # Only trainers/admins can assign an incident
        if self.action in ['assign']:
            return [IsAuthenticated(), IsTrainerOrAdmin()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['patch'], url_path='assign')
    def assign(self, request, pk=None):
        """Assign an incident to an analyst."""
        incident = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            raise ValidationError({"detail": "user_id is required."})
            
        incident.assigned_to_id = user_id
        incident.status = Incident.Status.INVESTIGATING
        incident.save()
        
        # Log the action in history
        IncidentHistory.objects.create(
            incident=incident,
            action="Incident Assigné",
            details=f"Assigné à l'utilisateur ID {user_id}",
            performed_by=request.user
        )
        
        return Response({"detail": "Incident assigned."})

    @action(detail=True, methods=['post'], url_path='add-evidence')
    def add_evidence(self, request, pk=None):
        """Add a piece of evidence to the incident."""
        incident = self.get_object()
        serializer = IncidentEvidenceSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(incident=incident, added_by=request.user)
            
            # Log the action
            IncidentHistory.objects.create(
                incident=incident,
                action="Preuve Ajoutée",
                details=request.data.get('description', ''),
                performed_by=request.user
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='resolve')
    def resolve(self, request, pk=None):
        """Close the incident with a resolution."""
        incident = self.get_object()
        resolution = request.data.get('resolution', '')
        
        if not resolution:
            raise ValidationError({"detail": "Une description de la résolution est requise."})
            
        incident.status = Incident.Status.RESOLVED
        incident.save()
        
        # Log the action
        IncidentHistory.objects.create(
            incident=incident,
            action="Incident Résolu",
            details=resolution,
            performed_by=request.user
        )
        
        return Response({"detail": "Incident resolved successfully."})

    @action(detail=True, methods=['get'], url_path='history')
    def get_history(self, request, pk=None):
        """View the full audit trail of the incident."""
        incident = self.get_object()
        history = incident.history.all()
        serializer = IncidentHistorySerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='evidences')
    def get_evidences(self, request, pk=None):
        """View all evidence attached to the incident."""
        incident = self.get_object()
        evidences = incident.evidences.all()
        serializer = IncidentEvidenceSerializer(evidences, many=True)
        return Response(serializer.data)




class SOCDashboardView(APIView):
    """
    GET /api/soc/dashboard/
    Returns global statistics for the SOC.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Events stats
        total_events = SecurityEvent.objects.count()
        critical_events = SecurityEvent.objects.filter(severity='CRITICAL').count()

        # 2. Alerts stats
        total_alerts = Alert.objects.count()
        new_alerts = Alert.objects.filter(status='NEW').count()

        # 3. Incidents stats
        total_incidents = Incident.objects.count()
        open_incidents = Incident.objects.filter(
            status__in=['OPEN', 'INVESTIGATING']
        ).count()
        resolved_incidents = Incident.objects.filter(status='RESOLVED').count()

        return Response({
            "events": {
                "total": total_events,
                "critical": critical_events,
            },
            "alerts": {
                "total": total_alerts,
                "unresolved": new_alerts,
            },
            "incidents": {
                "total": total_incidents,
                "open": open_incidents,
                "resolved": resolved_incidents,
            }
        }, status=status.HTTP_200_OK)
    