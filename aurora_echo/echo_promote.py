from pprint import pprint

import boto3
import click

from aurora_echo.echo_const import ECHO_NEW_STAGE, ECHO_PROMOTE_STAGE, ECHO_RETIRE_STAGE
from aurora_echo.echo_util import EchoUtil
from aurora_echo.entry import root

rds = boto3.client('rds')
route53 = boto3.client('route53')


def update_dns(hosted_zone_id: str, record_set: str, cluster_endpoint: str, ttl: str):

    response = route53.list_resource_record_sets(HostedZoneId=hosted_zone_id)
    record_sets_list = response['ResourceRecordSets']

    currently_set_endpoint = 'nothing'

    our_record_set = [x for x in record_sets_list if x['Name'] == record_set][0]
    if our_record_set:
        # print out the record we're replacing I guess
        if our_record_set['ResourceRecords']:  # make sure it's actually pointed at something
            currently_set_endpoint = our_record_set['ResourceRecords'][0]['Value']
        print('Found record set which is currently pointed at ', currently_set_endpoint)

        print('Record set to be updated:')
        pprint(our_record_set)
        print('New cluster endpoint: ', cluster_endpoint)

        # update to the found instance endpoint
        if click.confirm('Ready to update DNS record with these settings?', abort=True):
            response = route53.change_resource_record_sets(
                HostedZoneId=hosted_zone_id,
                ChangeBatch={
                    'Comment': 'Modified by aurora_echo',
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': our_record_set['Name'],
                                'Type': our_record_set['Type'],
                                'TTL': ttl,
                                'ResourceRecords': [
                                    {
                                        'Value': cluster_endpoint
                                    },
                                ],
                            }
                        },
                    ]
                }
            )

    pprint(response)


@root.command()
@click.option('--aws_account_number', '-a', required=True)
@click.option('--region', '-r', required=True)
@click.option('--managed_name', '-n', required=True)
@click.option('--hosted_zone_id', '-z', required=True)
@click.option('--record_set', '-rs', required=True)
@click.option('--ttl', default=60)
def promote(aws_account_number: str, region: str, managed_name: str, hosted_zone_id: str, record_set: str, ttl: str):
    util = EchoUtil(region, aws_account_number)

    found_instance = util.find_instance_in_stage(managed_name, ECHO_NEW_STAGE)
    if found_instance:
        print('Found promotable instance: ', found_instance['DBInstanceIdentifier'])
        cluster_endpoint = found_instance['Endpoint']['Address']
        update_dns(hosted_zone_id, record_set, cluster_endpoint, ttl)

        old_promoted_instance = util.find_instance_in_stage(managed_name, ECHO_PROMOTE_STAGE)
        if old_promoted_instance:
            print('Retiring old instance: ', old_promoted_instance['DBInstanceIdentifier'])
            util.add_tag(managed_name, old_promoted_instance, ECHO_RETIRE_STAGE)

        print('Updating tag for promoted instance: ', found_instance['DBInstanceIdentifier'])
        util.add_tag(managed_name, found_instance, ECHO_PROMOTE_STAGE)

        print('Done!')
    else:
        print('No promotable instance found.')


if __name__ == '__main__':
    promote()
