import pytest
from django.core.exceptions import ValidationError

from zinc.models import Policy


@pytest.mark.django_db
def test_policy_name_validation_not_unique_first_chars():
    Policy(name="dev01").save()
    with pytest.raises(ValidationError):
        Policy(name="dev011").full_clean()

    Policy(name="dev022").save()
    with pytest.raises(ValidationError):
        Policy(name="dev02").full_clean()


@pytest.mark.django_db
def test_policy_name_validation_regex():
    with pytest.raises(ValidationError):
        Policy(name="not-allowed-chars;").full_clean()

    with pytest.raises(ValidationError):
        Policy(name="UpperCaseName").full_clean()
