from datetime import datetime, timezone
import json

import boto3
import click

from aurora_echo.echo_const import ECHO_NEW_STAGE, ECHO_PROMOTE_COMMAND, ECHO_PROMOTE_STAGE, ECHO_RETIRE_STAGE
from aurora_echo.echo_util import EchoUtil
from aurora_echo.entry import root

rds = boto3.client('rds')
route53 = boto3.client('route53')


def log(): return '{0:%Y-%m-%d %H:%M:%S %Z} [{1}]'.format(datetime.now(timezone.utc), ECHO_PROMOTE_COMMAND)


def find_record_set(hosted_zone_id: str, record_set_name: str):

    response = route53.list_resource_record_sets(HostedZoneId=hosted_zone_id)
    record_sets_list = response['ResourceRecordSets']

    for record_set in record_sets_list:
        if record_set['Name'] == record_set_name:
            return record_set


def update_dns(hosted_zone_id: str, record_set: dict, cluster_endpoint: str, ttl: str, interactive: bool):
    # print out the record we're replacing
    currently_set_endpoint = 'nothing'
    if record_set['ResourceRecords']:
        currently_set_endpoint = record_set['ResourceRecords'][0]['Value']
    click.echo('{} Found record set {} currently pointed at {}'.format(log(), record_set['Name'], currently_set_endpoint))

    params = {
        'HostedZoneId': hosted_zone_id,
        'ChangeBatch': {
            'Comment': 'Modified by Aurora Echo',
            'Changes': [
                {
                    'Action': 'UPSERT',
                    'ResourceRecordSet': {
                        'Name': record_set['Name'],
                        'Type': record_set['Type'],
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

    click.echo('{} Parameters:'.format(log()))
    click.echo(json.dumps(params, indent=4, sort_keys=True))

    if interactive:
        click.confirm('{} Ready to update DNS record with these settings?'.format(log()), abort=True)  # exits entirely if no

    # update to the found instance endpoint
    response = route53.change_resource_record_sets(**params)
    click.echo('{} Success! DNS updated.'.format(log()))


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
        click.echo('{} Found promotable instance: {}'.format(log(), found_instance['DBInstanceIdentifier']))
        cluster_endpoint = found_instance['Endpoint']['Address']

        record_set_dict = find_record_set(hosted_zone_id, record_set)
        if record_set_dict:
            update_dns(hosted_zone_id, record_set_dict, cluster_endpoint, ttl, interactive)

            old_promoted_instance = util.find_instance_in_stage(managed_name, ECHO_PROMOTE_STAGE)
            if old_promoted_instance:
                click.echo('{} Retiring old instance: {}'.format(log(), old_promoted_instance['DBInstanceIdentifier']))
                util.add_stage_tag(managed_name, old_promoted_instance, ECHO_RETIRE_STAGE)

            click.echo('{} Updating tag for promoted instance: {}'.format(log(), found_instance['DBInstanceIdentifier']))
            util.add_stage_tag(managed_name, found_instance, ECHO_PROMOTE_STAGE)

            click.echo('{} Done!'.format(log()))
        else:
            click.echo('{} No record set found at hosted zone {} with name {}. Unable to promote instance.'.format(log(), hosted_zone_id, record_set))
    else:
        click.echo('{} No instance found in stage {} with status \'available\'. Not proceeding.'.format(log(), ECHO_NEW_STAGE))


if __name__ == '__main__':
    promote()
