from django.core.validators import RegexValidator


validate_hostname = RegexValidator(
    regex=(r'^(?=[a-z0-9\-\.]{1,253}$)([a-z0-9](([a-z0-9\-]){,61}[a-z0-9])?\.)'
           r'*([a-z0-9](([a-z0-9\-]){,61}[a-z0-9])?)$'),
    message=u'Invalid hostname',
    code='invalid_hostname'
)

# Regex inspired from django.core.validators.URLValidator
validate_domain = RegexValidator(
    regex=(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.(?!-)[a-z0-9-]{1,63}(?<!-))'
           r'*\.(?!-)(?:[a-z-]{2,63}|xn--[a-z0-9]{1,59})(?<!-)\.?$'),
    message=u'Invalid root domain',
    code='invalid_root_domain'
)
