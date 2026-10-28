from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChallengeViewSet, LeaderboardViewSet

router = DefaultRouter()
router.register(r'challenges', ChallengeViewSet, basename='challenges')
router.register(r'leaderboard', LeaderboardViewSet, basename='leaderboard')

urlpatterns = [
    path('', include(router.urls)),
]