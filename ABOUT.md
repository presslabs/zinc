# Zinc - Policy Records for Route53

Zinc provides a simple REST API for your basic DNS needs and implements policy records for
Route 53 using either
[Weighted Routing](http://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy.html#routing-policy-weighted) or
[Latency-Based Routing](http://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy.html#routing-policy-latency)

## Our use case

We have hundreds of sites hosted on our geographically distributed fleet of front-end servers. We
want to ensure availability through redundancy (no customer site should be served by a single
server), and a fast experience for all our customers' visitors through latency-based routing (when
someone tries to access a site, the server with the lowest latency should serve it for them).

## Why would one not use route53's policy based records?

If you're like us and have several hundred policy routed records, the costs can be prohibitive.

## Does it support other DNS providers?

Not yet, but one of the benefits of using Zinc is lower dependency on AWS. We figured in case we
ever do decide to switch providers, adding support to Zinc should be easy and have the benefit of
requiring only one system in our infrastructure to change.
