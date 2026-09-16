import copy
import unittest
from unittest.mock import patch

from host_ip_swapper.dns.cloudflare_helper import CloudFlareHelper
from host_ip_swapper.dns.route53_helper import Route53Helper


class Route53Tests(unittest.TestCase):
    def setUp(self):
        with patch('host_ip_swapper.dns.route53_helper.boto3.client') as client:
            self.helper = Route53Helper('zone', 'region', 'key', 'secret')
        self.client = client.return_value
        self.record = {'Name': 'host.example.', 'Type': 'A', 'TTL': 3600,
                       'ResourceRecords': [{'Value': '192.0.2.1'}]}
        self.client.list_resource_record_sets.return_value = {
            'ResourceRecordSets': [self.record], 'IsTruncated': False}

    def test_reads_control_plane_and_preserves_ttl_on_update(self):
        self.assertEqual(self.helper.get_current_ip('HOST.example'), '192.0.2.1')
        self.helper.update_dns_with_ip('host.example.', '192.0.2.2')
        changes = self.client.change_resource_record_sets.call_args.kwargs['ChangeBatch']['Changes']
        self.assertEqual(changes, [{'Action': 'UPSERT', 'ResourceRecordSet': {
            'Name': 'host.example.', 'Type': 'A', 'TTL': 3600,
            'ResourceRecords': [{'Value': '192.0.2.2'}]}}])
        self.assertEqual(self.record['ResourceRecords'], [{'Value': '192.0.2.1'}])

    def test_rejects_missing_neighbor_multiple_alias_and_routing_records(self):
        neighbor = dict(self.record, Name='other.example.')
        alias = {'Name': 'host.example.', 'Type': 'A', 'AliasTarget': {
            'DNSName': 'target.example.', 'HostedZoneId': 'zone', 'EvaluateTargetHealth': False}}
        multiple = dict(self.record, ResourceRecords=[{'Value': '192.0.2.1'}, {'Value': '192.0.2.3'}])
        weighted = dict(self.record, SetIdentifier='weighted', Weight=1)
        health_checked = dict(self.record, HealthCheckId='check')
        for records in ([], [neighbor], [alias], [multiple], [weighted], [health_checked],
                        [self.record, self.record]):
            with self.subTest(records=records):
                self.client.list_resource_record_sets.return_value = {'ResourceRecordSets': records}
                with self.assertRaises(ValueError):
                    self.helper.get_current_ip('host.example')
                with self.assertRaises(ValueError):
                    self.helper.update_dns_with_ip('host.example', '192.0.2.2')
                self.client.change_resource_record_sets.assert_not_called()

    def test_read_failure_does_not_mutate(self):
        self.client.list_resource_record_sets.side_effect = RuntimeError('permission denied')
        with self.assertRaises(RuntimeError):
            self.helper.update_dns_with_ip('host.example', '192.0.2.2')
        self.client.change_resource_record_sets.assert_not_called()

    def test_rejects_invalid_current_and_replacement_addresses(self):
        self.record['ResourceRecords'][0]['Value'] = '2001:db8::1'
        with self.assertRaises(ValueError):
            self.helper.get_current_ip('host.example')
        with self.assertRaises(ValueError):
            self.helper.update_dns_with_ip('host.example', 'not-an-ip')
        self.client.change_resource_record_sets.assert_not_called()


class CloudflareTests(unittest.TestCase):
    def setUp(self):
        with patch('host_ip_swapper.dns.cloudflare_helper.CloudFlare.CloudFlare') as client:
            self.helper = CloudFlareHelper('zone', 'email', 'key')
        self.records = client.return_value.zones.dns_records
        self.record = {'id': 'record', 'name': 'host.example', 'type': 'A',
                       'content': '192.0.2.1', 'proxied': True, 'ttl': 1,
                       'comment': 'keep me', 'tags': ['owner:team'],
                       'settings': {'ipv4_only': True}}
        self.records.get.return_value = [self.record]

    def test_reads_proxied_origin_and_preserves_record_metadata(self):
        original = copy.deepcopy(self.record)

        def apply_patch(zone, record_id, data):
            self.assertEqual((zone, record_id), ('zone', 'record'))
            self.record.update(data)

        self.records.patch.side_effect = apply_patch
        self.assertEqual(self.helper.get_current_ip('HOST.example.'), '192.0.2.1')
        self.helper.update_dns_with_ip('host.example', '192.0.2.2')
        self.assertEqual(self.record, dict(original, content='192.0.2.2'))
        self.records.put.assert_not_called()

    def test_rejects_missing_multiple_and_nonmatching_records(self):
        for records in ([], [self.record, dict(self.record, id='second')],
                        [dict(self.record, type='CNAME')],
                        [dict(self.record, name='other.example')]):
            with self.subTest(records=records):
                self.records.get.return_value = records
                with self.assertRaises(ValueError):
                    self.helper.get_current_ip('host.example')
                with self.assertRaises(ValueError):
                    self.helper.update_dns_with_ip('host.example', '192.0.2.2')
                self.records.patch.assert_not_called()
                self.records.put.assert_not_called()

    def test_rejects_invalid_current_and_replacement_addresses(self):
        self.record['content'] = '2001:db8::1'
        with self.assertRaises(ValueError):
            self.helper.get_current_ip('host.example')
        with self.assertRaises(ValueError):
            self.helper.update_dns_with_ip('host.example', 'not-an-ip')
        self.records.patch.assert_not_called()

    def test_write_failure_is_not_silent_success(self):
        self.records.patch.side_effect = RuntimeError('permission denied')
        with self.assertRaises(RuntimeError):
            self.helper.update_dns_with_ip('host.example', '192.0.2.2')


if __name__ == '__main__':
    unittest.main()
