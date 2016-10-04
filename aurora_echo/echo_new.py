from datetime import datetime
from pprint import pprint

import boto3
import click

from aurora_echo.echo_util import EchoUtil
from aurora_echo.entry import root
from aurora_echo.echo_const import ECHO_NEW_STAGE

rds = boto3.client('rds')

today_string = '{0:%Y-%m-%d}'.format(datetime.utcnow())


def find_snapshot(cluster_name: str):

    response = rds.describe_db_cluster_snapshots(DBClusterIdentifier=cluster_name)
    snapshot_list = response['DBClusterSnapshots']
    # sort/filter by newest and available
    available_snapshots = [snap for snap in snapshot_list if snap['Status'] == 'available']
    sorted_snapshot_list = sorted(available_snapshots, key=lambda snap: snap['SnapshotCreateTime'], reverse=True)
    chosen_cluster_snapshot = sorted_snapshot_list[0]

    print('Located cluster snapshot %s', chosen_cluster_snapshot['DBClusterSnapshotIdentifier'])  # TODO how does logging

    return chosen_cluster_snapshot['DBClusterSnapshotIdentifier']


def restore_cluster(cluster_snapshot_identifier: str, new_cluster_name: str, db_subnet_group_name: str,
                    engine: str, vpc_security_group_id: list, tags: list):
    """
    Convert parameters into a dict of known values appropriate to be used in an RDS API call.
    :return: params
    """

    params = {}

    # Required params
    params['SnapshotIdentifier'] = cluster_snapshot_identifier
    params['DBClusterIdentifier'] = new_cluster_name
    params['DBSubnetGroupName'] = db_subnet_group_name
    params['Engine'] = engine

    # Optional params
    if vpc_security_group_id:
        params['VpcSecurityGroupIds'] = [vpc for vpc in vpc_security_group_id]

    # Our tags indicating the instance is managed, plus optional user-defined tags
    params['Tags'] = tags  # a list of dicts

    # Optional inputs we do not use and therefore do not support yet
    """
        EngineVersion='string',
        Port=123,
        DatabaseName='string',
        OptionGroupName='string',
    """

    pprint(params)  # TODO logging

    # TODO make option to disable prompting
    if click.confirm('Ready to create cluster with these settings?', abort=True):
        response = rds.restore_db_cluster_from_snapshot(**params)

    return response['DBCluster']


def create_instance_in_cluster(restored_cluster_info: dict, new_instance_name: str, engine: str, db_instance_class: str,
                               availability_zone: str, tags: list):

    cluster_identifier = restored_cluster_info['DBClusterIdentifier']

    params = {}

    # Required params
    params['DBInstanceIdentifier'] = new_instance_name
    params['DBClusterIdentifier'] = cluster_identifier
    params['Engine'] = engine
    params['DBInstanceClass'] = db_instance_class

    # Optional params
    if availability_zone:
        params['AvailabilityZone'] = availability_zone

    # Our tags indicating the instance is managed, plus optional user-defined tags
    params['Tags'] = tags  # a list of dicts

    pprint(params)  # TODO logging

    # TODO prompt again? wait. maybe I should collect all params first, blahhhhh
    if click.confirm('Ready to create instance with these settings?', abort=True):
        response = rds.create_db_instance(**params)

        pprint(response)


@root.command()
@click.option('--aws_account_number', '-a', required=True)
@click.option('--region', '-r', required=True)
@click.option('--cluster_snapshot_name', '-s', required=True)
@click.option('--managed_name', '-n', required=True)
@click.option('--db_subnet_group_name', '-sub', required=True)
@click.option('--db_instance_class', '-c', required=True)
@click.option('--engine', '-e', default='aurora')
@click.option('--availability_zone', '-az')
@click.option('--vpc_security_group_id', '-sg', multiple=True)
@click.option('--tag', '-t', multiple=True)
@click.option('--minimum_age_hours', '-h', default=20)
def new(aws_account_number: str, region: str, cluster_snapshot_name: str, managed_name: str, db_subnet_group_name: str, db_instance_class: str,
        engine: str, availability_zone: str, vpc_security_group_id: list, tag: list, minimum_age_hours: int):

    util = EchoUtil(region, aws_account_number)
    if not util.instance_too_new(managed_name, minimum_age_hours):

        cluster_snapshot_identifier = find_snapshot(cluster_snapshot_name)

        restore_cluster_name = managed_name + '-' + today_string

        tag_set = util.construct_managed_tag_set(managed_name, ECHO_NEW_STAGE)
        user_tags = util.construct_user_tag_set(tag)
        if user_tags:
            tag_set.extend(user_tags)

        cluster = restore_cluster(cluster_snapshot_identifier, restore_cluster_name, db_subnet_group_name, engine, vpc_security_group_id, tag_set)
        create_instance_in_cluster(cluster, restore_cluster_name, engine, db_instance_class, availability_zone, tag_set)
        print('Created new instance and cluster!')
    else:
        print('Found managed instance created less than %d hours ago. Not proceeding.'.format(minimum_age_hours))
