from datetime import datetime, timezone
import json

import boto3
import click

from aurora_echo.echo_const import ECHO_RETIRE_COMMAND, ECHO_RETIRE_STAGE
from aurora_echo.echo_util import EchoUtil
from aurora_echo.entry import root

rds = boto3.client('rds')


def log(): return '{0:%Y-%m-%d %H:%M:%S %Z} [{1}]'.format(datetime.now(timezone.utc), ECHO_RETIRE_COMMAND)


def delete_instance(instance: dict, interactive: bool):
    instance_identifier = instance['DBInstanceIdentifier']
    instance_params = {
        'DBInstanceIdentifier': instance_identifier,
        'SkipFinalSnapshot': True,
    }
    
    cluster_identifier = instance['DBClusterIdentifier']
    cluster_params = {
        'DBClusterIdentifier': cluster_identifier,
        'SkipFinalSnapshot': True,
    }
    
    click.echo('{} Parameters:'.format(log()))
    click.echo(json.dumps(instance_params, indent=4, sort_keys=True))
    click.echo(json.dumps(cluster_params, indent=4, sort_keys=True))

    if interactive:
        click.confirm('{} Ready to DELETE/DESTROY/REMOVE this database instance '
                     'and cluster along with ALL AUTOMATED BACKUPS?'.format(log()), abort=True)  # exits entirely if no

    # delete the instance first so the cluster is empty, otherwise it'll fail
    response = rds.delete_db_instance(**instance_params)
    response = rds.delete_db_cluster(**cluster_params)


@root.command()
@click.option('--aws_account_number', '-a', required=True)
@click.option('--region', '-r', required=True)
@click.option('--managed_name', '-n', required=True)
@click.option('--interactive', '-i', default=True, type=bool)
def retire(aws_account_number: str, region: str, managed_name: str, interactive: bool):
    util = EchoUtil(region, aws_account_number)

    found_instance = util.find_instance_in_stage(managed_name, ECHO_RETIRE_STAGE)
    if found_instance:
        click.echo('{} Found instance ready for retirement: {}'.format(log(), found_instance['DBInstanceIdentifier']))
        delete_instance(found_instance, interactive)

        click.echo('{} Done!'.format(log()))
    else:
        click.echo('{} No instance found in stage {}. Not proceeding.'.format(log(), ECHO_RETIRE_STAGE))


if __name__ == '__main__':
    retire()
