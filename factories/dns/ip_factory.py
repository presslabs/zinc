from factory import Sequence
from factory.django import DjangoModelFactory


class IPFactory(DjangoModelFactory):
    hostname = Sequence(lambda n: 'hostname.{}'.format(n))
    friendly_name = Sequence(lambda n: 'friendly_name_{}'.format(n))
    enabled = True

    class Meta:
        model = 'zinc.IP'
        django_get_or_create = ('ip',)
