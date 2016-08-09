from django.core.validators import RegexValidator


validate_hostname = RegexValidator(
    regex=r'^(?=[a-z0-9\-\.]{1,253}$)([a-z0-9](([a-z0-9\-]){,61}[a-z0-9])?\.)*([a-z0-9](([a-z0-9\-]){,61}[a-z0-9])?)$',
    message=u'Invalid hostname',
    code='invalid_hostname'
)

