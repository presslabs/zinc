from django.conf import settings


def set_user_perms(details=None, user=None, is_new=False, **kwargs):
    if not details['email'].endswith('@presslabs.com'):
        return None
    if not is_new:
        return None
    if not user:
        return None

    if details['email'] in getattr(settings, 'SOCIAL_AUTH_ADMIN_EMAILS', []):
        user.is_staff = True
        user.is_superuser = True

    user.save()

    return None
