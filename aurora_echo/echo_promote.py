import json

import boto3
import click

from aurora_echo.echo_const import ECHO_NEW_STAGE, ECHO_PROMOTE_STAGE, ECHO_RETIRE_STAGE
from aurora_echo.echo_util import EchoUtil
from aurora_echo.entry import root

rds = boto3.client('rds')
route53 = boto3.client('route53')


def update_dns(hosted_zone_id: str, record_set: str, cluster_endpoint: str, ttl: str, interactive: bool):

    response = route53.list_resource_record_sets(HostedZoneId=hosted_zone_id)
    record_sets_list = response['ResourceRecordSets']

    currently_set_endpoint = 'nothing'

    our_record_set = [x for x in record_sets_list if x['Name'] == record_set][0]
    if our_record_set:
        # print out the record we're replacing
        if our_record_set['ResourceRecords']:  # make sure it's actually pointed at something
            currently_set_endpoint = our_record_set['ResourceRecords'][0]['Value']
        click.echo('Found record set {} currently pointed at {}'.format(our_record_set['Name'], currently_set_endpoint))

        params = {
                'HostedZoneId': hosted_zone_id,
                'ChangeBatch': {
                    'Comment': 'Modified by Aurora Echo',
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
        }

        click.echo('Parameters:')
        click.echo(json.dumps(params, indent=4, sort_keys=True))

        if interactive:
            click.confirm('Ready to update DNS record with these settings?', abort=True)  # exits entirely if no

        # update to the found instance endpoint
        response = route53.change_resource_record_sets(**params)

    else:
        click.echo('No record set found at hosted zone {} with name {}'.format(hosted_zone_id, record_set))
        # TODO HEY THIS NEEDS TO STOP ALL DOWNSTREAM PROCESSING SO WE DON'T UPDATE TAGS


@root.command()
@click.option('--aws_account_number', '-a', required=True)
@click.option('--region', '-r', required=True)
@click.option('--managed_name', '-n', required=True)
@click.option('--hosted_zone_id', '-z', required=True)
@click.option('--record_set', '-rs', required=True)
@click.option('--ttl', default=60)
@click.option('--interactive', '-i', default=True, type=bool)
def promote(aws_account_number: str, region: str, managed_name: str, hosted_zone_id: str, record_set: str, ttl: str,
            interactive: bool):
    util = EchoUtil(region, aws_account_number)

    found_instance = util.find_instance_in_stage(managed_name, ECHO_NEW_STAGE)
    if found_instance and found_instance['DBInstanceStatus'] == 'available':
        click.echo('Found promotable instance: {}'.format(found_instance['DBInstanceIdentifier']))
        cluster_endpoint = found_instance['Endpoint']['Address']
        update_dns(hosted_zone_id, record_set, cluster_endpoint, ttl, interactive)

        old_promoted_instance = util.find_instance_in_stage(managed_name, ECHO_PROMOTE_STAGE)
        if old_promoted_instance:
            click.echo('Retiring old instance: {}'.format(old_promoted_instance['DBInstanceIdentifier']))
            util.add_tag(managed_name, old_promoted_instance, ECHO_RETIRE_STAGE)

        click.echo('Updating tag for promoted instance: {}'.format(found_instance['DBInstanceIdentifier']))
        util.add_tag(managed_name, found_instance, ECHO_PROMOTE_STAGE)

        click.echo('Done!')
    else:
        click.echo('No promotable instance found.')


if __name__ == '__main__':
    promote()
