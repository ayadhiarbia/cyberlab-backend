from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from . import views

router = DefaultRouter()
router.register(r'users', views.UserAdminViewSet, basename='admin-users')

urlpatterns = [
    # Health check
    path('status/', views.api_status, name='api-status'),

    # Auth
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', views.logout_view, name='logout'),
    path('me/', views.MeView.as_view(), name='me'),

    # Password reset (email code flow)
    path('password/request-code/', views.password_reset_request, name='password-request-code'),
    path('password/verify-code/',  views.password_reset_verify,  name='password-verify-code'),
    path('password/reset/',        views.password_reset_confirm, name='password-reset'),

    # Admin routes
    path('', include(router.urls)),
]