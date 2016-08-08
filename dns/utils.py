from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _


def validate_positive(value):
    if value < 0:
        raise ValidationError(
            _('%(value)s is not an positive number'),
            params={'value': value},
        )

validate_hostname = RegexValidator(
    regex=r'^(?=[a-z0-9\-\.]{1,253}$)([a-z0-9](([a-z0-9\-]){,61}[a-z0-9])?\.)*([a-z0-9](([a-z0-9\-]){,61}[a-z0-9])?)$',
    message=u'Invalid hostname',
    code='invalid_hostname'
)