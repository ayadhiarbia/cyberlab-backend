from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LabViewSet, LabSessionViewSet

router = DefaultRouter()
router.register(r'labs', LabViewSet, basename='labs')
router.register(r'sessions', LabSessionViewSet, basename='labsessions')

urlpatterns = [
    path('', include(router.urls)),
]