from pprint import pprint

import boto3
import click

from aurora_echo.echo_const import ECHO_RETIRE_STAGE
from aurora_echo.echo_util import Util
from aurora_echo.entry import root

rds = boto3.client('rds')


def delete_instance(instance: dict):
    instance_identifier = instance['DBInstanceIdentifier']
    cluster_identifier = instance['DBClusterIdentifier']
    cluster_dict = {
        'DBClusterIdentifier': cluster_identifier,
        'SkipFinalSnapshot': True,
    }
    dict = {
        'DBInstanceIdentifier': instance_identifier,
        'SkipFinalSnapshot': True,
    }
    pprint(dict)  # show the user what we're passing in
    pprint(cluster_dict)
    if click.confirm('Ready to DELETE/DESTROY/REMOVE this database instance '
                     'and cluster along with ALL AUTOMATED BACKUPS?', abort=True):
        response = rds.delete_db_instance(**dict)
        # pprint(response)
        response = rds.delete_db_cluster(**cluster_dict)
        # pprint(response)


@root.command()
@click.option('--aws_account_number', '-a', required=True)
@click.option('--region', '-r', required=True)
@click.option('--managed_name', '-n', required=True)
def retire(aws_account_number: str, region: str, managed_name: str):
    util = Util(region, aws_account_number)

    found_instance = util.find_instance_in_stage(managed_name, ECHO_RETIRE_STAGE)
    if found_instance:
        print('Found instance ready for retirement: ', found_instance['DBInstanceIdentifier'])
        delete_instance(found_instance)

        print('Done!')
    else:
        print('No instance found in state ', ECHO_RETIRE_STAGE)


if __name__ == '__main__':
    retire()