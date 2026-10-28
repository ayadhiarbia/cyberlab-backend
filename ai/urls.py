from django.urls import path
from . import views

urlpatterns = [
    path('status/', views.ai_status, name='ai-status'),
    path('generate-lab/', views.generate_lab, name='ai-generate-lab'),
    path('analyze-alert/', views.analyze_alert, name='ai-analyze-alert'),
]