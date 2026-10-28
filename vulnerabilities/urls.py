from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BulletinViewSet, VulnerabilityViewSet, RemediationViewSet

router = DefaultRouter()
router.register(r'bulletins', BulletinViewSet, basename='bulletins')
router.register(r'list', VulnerabilityViewSet, basename='vulnerabilities')
router.register(r'remediations', RemediationViewSet, basename='remediations')

urlpatterns = [
    path('', include(router.urls)),
]