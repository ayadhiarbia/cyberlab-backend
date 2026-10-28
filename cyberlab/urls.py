from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
     path('api/ai/', include('ai.urls')),
     path('api/', include('labs.urls')),
     path('api/ctf/', include('ctf.urls')),
     path('api/soc/', include('soc.urls')),
     path('api/vulnerabilities/', include('vulnerabilities.urls')), 
]