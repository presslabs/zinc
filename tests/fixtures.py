import botocore


class CleanupClient:
    """Wraps real boto3 client and tracks zone creation, so it can clean up at the end"""
    def __init__(self, client):
        self._client = client
        self._zone_ids = set([])

    def __getattr__(self, attr_name):
        return getattr(self._client, attr_name)

    def __hasattr__(self, attr_name):
        return hasattr(self._client, attr_name)

    def create_hosted_zone(self, **kwa):
        resp = self._client.create_hosted_zone(**kwa)
        zone_id = resp['HostedZone']['Id']
        self._zone_ids.add(zone_id)
        return resp

    def _cleanup_hosted_zones(self):
        for zone_id in self._zone_ids:
            try:
                records = self.list_resource_record_sets(HostedZoneId=zone_id)
                for record in records['ResourceRecordSets']:
                    if record['Type'] == 'A':
                        self.change_resource_record_sets(
                            HostedZoneId=zone_id,
                            ChangeBatch={
                                'Comment': 'zinc-fixture',
                                'Changes': [
                                    {
                                        'Action': 'DELETE',
                                        'ResourceRecordSet': record
                                    },
                                ]
                            })

                self._client.delete_hosted_zone(Id=zone_id)
            except botocore.exceptions.ClientError as excp:
                print("Failed to delete", zone_id, excp.response['Error']['Code'])
