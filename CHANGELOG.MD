# Changelog

## Unrealeased changes
- Bump dependencies to `Django==1.11.29`, `djangorestframework==3.11.2`, `gevent==1.4.0`,
  `requests==2.20.1`, `celery==4.4.7`, `gevent==1.4.0`, `python-redis-lock==3.7.0`.
- Update AWS regions list

## 1.1.0 (2019-01-07)
- Added a command to delete stale zones.
- Return 429 error in API calls when being throttled by AWS.
- Better error messaging when no member is in a policy.
- Use python-redis-lock package insted of redis default lock.
- Better integration with lattice.
- Split overlength record values into chunks.
- Bumped boto3 version to 1.5.29.
- Use PyMySQL instead of mysqlclient.
- Use gevent workers for API.
- Fixed celery inside docker container.
- Added django-environ along with a .env.example file to help with configuration.


## 1.0.1 (2017-06-28)
- Added docker-compose.yml for starting zinc + services.
- Updated the readme file.

## 1.0.0 (2017-06-28)
_There is no changelog before this initial release._
