def re_fetch(obj):
    """Re-fetch an object from the DB"""
    return type(obj).objects.get(pk=obj.pk)
