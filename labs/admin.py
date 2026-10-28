from django.contrib import admin
from .models import Lab, LabSession, LabReview


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'difficulty', 'status', 'source', 'created_by', 'created_at')
    list_filter = ('status', 'source', 'category', 'difficulty')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'published_at')


@admin.register(LabSession)
class LabSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'lab', 'status', 'solved', 'score', 'started_at')
    list_filter = ('status', 'solved')
    search_fields = ('user__username', 'lab__title')


@admin.register(LabReview)
class LabReviewAdmin(admin.ModelAdmin):
    list_display = ('lab', 'reviewer', 'decision', 'created_at')
    list_filter = ('decision',)