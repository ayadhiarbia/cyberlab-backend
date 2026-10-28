from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SecurityEventViewSet, AlertViewSet, IncidentViewSet, SOCDashboardView

router = DefaultRouter()
router.register(r'events', SecurityEventViewSet, basename='events')
router.register(r'alerts', AlertViewSet, basename='alerts')
router.register(r'incidents', IncidentViewSet, basename='incidents')

urlpatterns = [
    path('dashboard/', SOCDashboardView.as_view(), name='soc-dashboard'),  # <-- ADD THIS
    path('', include(router.urls)),
]