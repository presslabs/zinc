# zinc
[![Build Status](https://drone.presslabs.net/api/badges/PressLabs/zinc/status.svg)](https://drone.presslabs.net/PressLabs/zinc)

# Welcome to Zinc

Zinc is a Route 53 zone manager.

Zinc was developed by the awesome engineering team at [Presslabs](https://www.presslabs.com/), 
a Managed WordPress Hosting provider.

For more open-source projects, check [Presslabs Code](https://www.presslabs.org/). 

# Policy Records on the Cheap

Q: Why would one use Zinc over AWS's Policy Records?

A: Price. 50$ per Record adds up quickly.


# Overview

## IPs, Policies and Policy Records

At the end of the day your domain name `example.com` needs to resolve to one or more
ip addresses. Here's how we go about it.

### IPs

Should be self explanatory. An IP can be enabled or disabled.

There is no explicit handling in zinc of multiple IPs belonging to one server.

Enabling or disabling can be done from the admin or by implementing a django app (see
lattice_sync for an example).

**N.B.** If implementing your own app it's your responsibility to call
`ip.mark_policy_records_dirty` if the IP changes, so that zinc's reconcile loop will
actually pick up the changes.


### HealthChecks

Zinc will create a Route53 Health Check for each IP. If Route53 deems the IP unavailable,
it will stop routing traffic to it.

Currently the Health Checks are hardcoded to expect all servers to accept requests with the
same FQDN (defaults to node.presslabs.net, set `ZINC_HEALTH_CHECK_FQDN` to change).

### Policies

A policy groups several IPs together. There are 2 types of policies:
 * Weighted
 * Latency

Note that an IP can be a member of multiple Policies at the same time. A PolicyMember
can has it's own enabled flag, so you can disable an IP for one Policy only, or you can
disable the it for all Policies by setting the enabled flag on the IP model.

#### Weighted

Trafic will be routed to all IP's based on their weights. Bigger weight means more trafic.

#### Latency

Each IP you add to a Policy will have a region specified as well. The region must be an AWS
region. IPs will still have weights, which will be used to balance the trafic within a
region. When a cliend does a DNS lookup, they'll get directed to the region with the lowest
latency, and then an IP will be picked based on weight.

The resulting setup will be similar to the example described here:
http://docs.aws.amazon.com/Route53/latest/DeveloperGuide/dns-failover-complex-configs.html

### Policy Records

Your desired DNS record. In Route53 it will be an alias to the Latency or Weighted records
that make up a Policy.

## Reconcile Loops and the Single Source of Truth

For simple records in a zone (anything except a PolicyRecord) AWS is the Sigle Source of
Truth. Zinc never stores those locally.

For Zones, HealthChecks and PolicyRecords Zinc's database is the single source of truth.
Zinc runs reconcile loops and attempts to update your AWS data to match the expected state
in the DB. To minimize throttling by AWS, in most cases, Zinc only attempts to reconcile
objects marked deemed dirty. This means it is possible to have a missmatch between what you
have in AWS and Zinc's expected state if you make changes bypassing Zinc (using the AWS
console, or the api).

## API

You are encouraged to install django-rest-swagger, run zinc locally and explore the API at
http://localhost:8080/swagger

### Policies

Policies are read only trough the API. You can define them in the admin.

#### Policy listing.
`GET /policies`

#### Policy detail. Example:
`GET /policies/{id}`

```
GET /policies/344b7bee-da33-4234-b645-805cc26adab0
{
  "id": "344b7bee-da33-4234-b645-805cc26adab0",
  "name": "policy-one",
  "members": [
    {
      "id": "6bcb4e77-04dc-45f7-bebb-a2fcfadd7669",
      "region": "us-east-1",
      "ip": "192.0.2.11",
      "weight": 10,
      "enabled": true
    },
    {
      "id": "4f83d47f-af0c-4fa7-80c8-710cb32e4928",
      "region": "us-west-1",
      "ip": "192.0.2.11",
      "weight": 10,
      "enabled": true
    }
  ],
  "url": "https://zinc.stage.presslabs.net/policies/344b7bee-da33-4234-b645-805cc26adab0"
}
```

### Zones

#### Zone listing.
`GET /zones/`

#### Zone creation.
`POST /zones/`

Args:

| argument | required | default | description |
| --- | --- | --- | --- |
| root | required | - | The domain name of this zone. Trailing dot is optional. |

Returns the newly created zone object.

#### Delete a zone.
`DELETE /zones/{zone_id}/`

#### Zone detail.
`GET /zones/{zone_id}`

Example:
```
GET /zones/102
{
  "root": "zinc.example.presslabs.net.",
  "url": "https://zinc.stage.presslabs.net/zones/102",
  "records_url": "https://zinc.stage.presslabs.net/zones/102/records",
  "records": [
    {
      "name": "@",
      "fqdn": "zinc.example.presslabs.net.",
      "type": "NS",
      "values": [
        "ns-389.awsdns-48.com.",
        "ns-1596.awsdns-07.co.uk.",
        "ns-1008.awsdns-62.net.",
        "ns-1294.awsdns-33.org."
      ],
      "ttl": 172800,
      "dirty": false,
      "id": "Z6k504rwKzbamNZ9ZmY5lvkoOJGDW0",
      "url": "https://zinc.stage.presslabs.net/zones/102/records/Z6k504rwKzbamNZ9ZmY5lvkoOJGDW0",
      "managed": true
    },
    {
      "name": "@",
      "fqdn": "zinc.example.presslabs.net.",
      "type": "SOA",
      "values": [
        "ns-389.awsdns-48.com. awsdns-hostmaster.amazon.com. 1 7200 900 1209600 86400"
      ],
      "ttl": 900,
      "dirty": false,
      "id": "Z6k504rwKzbamNZ6Z7doJ0yg98j9zA",
      "url": "https://zinc.stage.presslabs.net/zones/102/records/Z6k504rwKzbamNZ6Z7doJ0yg98j9zA",
      "managed": true
    }
  ],
  "route53_id": "Z8QRF09VVGAC6",
  "dirty": false,
  "ns_propagated": false
}
```

### Records

#### List records in a zone.
`GET /zones/{zone_id}/records`

Example:
```
GET /zones/102/records
[
  {
    "name": "@",
    "fqdn": "zinc.example.presslabs.net.",
    "type": "NS",
    "values": [
      "ns-389.awsdns-48.com.",
      "ns-1596.awsdns-07.co.uk.",
      "ns-1008.awsdns-62.net.",
      "ns-1294.awsdns-33.org."
    ],
    "ttl": 172800,
    "dirty": false,
    "id": "Z6k504rwKzbamNZ9ZmY5lvkoOJGDW0",
    "url": "https://zinc.stage.presslabs.net/zones/102/records/Z6k504rwKzbamNZ9ZmY5lvkoOJGDW0",
    "managed": true
  },
  {
    "name": "@",
    "fqdn": "zinc.example.presslabs.net.",
    "type": "SOA",
    "values": [
      "ns-389.awsdns-48.com. awsdns-hostmaster.amazon.com. 1 7200 900 1209600 86400"
    ],
    "ttl": 900,
    "dirty": false,
    "id": "Z6k504rwKzbamNZ6Z7doJ0yg98j9zA",
    "url": "https://zinc.stage.presslabs.net/zones/102/records/Z6k504rwKzbamNZ6Z7doJ0yg98j9zA",
    "managed": true
  }
]
```

#### Create a record.
`POST /zones/{zone_id}/records`

Args:

| argument | required | default | description |
| --- | --- | --- | --- |
| name | required | - | The domain name (without the zone root). |
| type | required | - | The record type. Must be either POLICY\_ROUTED or a valid record type. |
| values | required | - | List of values. Should be one IP for A, MX records, a policy id for POLICY_ROUTED, one or more domain names for NS records. |
| ttl | optional | 300 | The TTL for DNS. |


#### Delete a record.
`DELETE /zones/{zone_id}/records/{record_id}`

#### Record detail.
`GET /zones/{zone_id}/records/{record_id}`

Example:
```
GET /zones/102/records/Z6k504rwKzbamNZ1ZxLxRR4BKly04J
{
  "name": "www",
  "fqdn": "www.zinc.example.presslabs.net.",
  "type": "POLICY_ROUTED",
  "values": [
    "344b7bee-da33-4234-b645-805cc26adab0"
  ],
  "ttl": null,
  "dirty": false,
  "id": "Z6k504rwKzbamNZ1ZxLxRR4BKly04J",
  "url": "https://zinc.stage.presslabs.net/zones/102/records/Z6k504rwKzbamNZ1ZxLxRR4BKly04J",
  "managed": false
}
```

#### Update an existing record.
`PATCH /zones/{zone_id}/records/{record_id}`

The type and name can't be changed.
Missing attributes don't change.

| argument | required | default | description |
| --- | --- | --- | --- |
| values | optional | - | List of values. Should be one IP for A, MX records, a policy id for POLICY_ROUTED, one or more domain names for NS records. |
| ttl | optional | - | The TTL for DNS. |


# Installing and Running

The recomended way to get up and running is using our Docker container.

```
cd contrib/
docker-compose up
```

## Config

If you run the django project with default settings, you can configure zinc by setting
environment variables. If you're using the provided docker-compose.yml you can set the
environment in ./zinc.env

The following are essential and required:
```
ZINC_AWS_KEY - AWS Key
ZINC_AWS_SECRET - AWS Secret
ZINC_SECRET_KEY - Django secret
```

You can also set the following:
```
ZINC_ALLOWED_HOSTS - Django Allowed Hosts
ZINC_BROKER_URL - Celery Broker URL, defaults to ${REDIS_URL}/0
ZINC_CELERY_RESULT_BACKEND - Celery Result Backend, defaults to ${REDIS_URL}/1
ZINC_DATA_DIR - PROJECT_ROOT
ZINC_DB_ENGINE - The django db engine to use. Defaults to 'django.db.backends.sqlite3'
ZINC_DB_HOST -
ZINC_DB_NAME - zinc
ZINC_DB_PASSWORD - password
ZINC_DB_PORT -
ZINC_DB_USER - zinc
ZINC_DEBUG - Django debug. Defaults to False. Set to the string "True" to turn on debugging.
ZINC_DEFAULT_TTL - 300
ZINC_ENV_NAME - The environment for sentry reporting.
ZINC_GOOGLE_OAUTH2_KEY - For use with social-django. If you don't set this, social-django will be disabled.
ZINC_GOOGLE_OAUTH2_SECRET - For use with social-django.
ZINC_SOCIAL_AUTH_ADMIN_EMAILS - List of email addresses that will be automatically granted admin access.
ZINC_SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_DOMAINS - see http://python-social-auth.readthedocs.io/en/latest/configuration/settings.html?highlight=whitelisted#whitelists
ZINC_HEALTH_CHECK_FQDN - Hostname to use in Health Checks. Defaults to 'node.presslabs.net.'
ZINC_LOCK_SERVER_URL - Used with redis-lock. Defaults to ${REDIS_URL}/2.
ZINC_LOG_LEVEL - Defaults to INFO
ZINC_NS_CHECK_RESOLVERS - NameServers to use when checking zone propagation. Default: ['8.8.8.8']
ZINC_REDIS_URL - Defaults to 'redis://localhost:6379'
ZINC_SECRET_KEY - The secret key used by the django app.
ZINC_SENTRY_DSN - Set this to enable sentry error reporting.
ZINC_STATIC_URL - Defaults to '/static/'
ZINC_ZONE_OWNERSHIP_COMMENT - Set this comment on records, to Defaults to 'zinc'
```

# Development

**Warning! Don't use production AWS credentials when developing or testing Zinc!**

After you've cloned the code:
```
pip install -r requirements.dev.txt
python setup.py develop
cp local_settings.py.example local_settings.py
# open local_settings.py in your favorite editor, and set AWS credentials
```

To run the tests:
```
# all tests
py.test .

# to skip tests that need AWS
py.test -k 'not with_aws' .
```
