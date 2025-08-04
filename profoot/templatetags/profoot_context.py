# profoot/templatetags/profoot_context.py
from ..models import Notification # N'oubliez pas l'import relatif
from django.contrib.auth.models import User
from django.db.models import Count

def unread_notifications_count(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}