##
# The MIT License (MIT)
#
# Copyright (c) 2017 BlackLocus
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
##

import json
from datetime import datetime, timezone

import boto3
import click

from aurora_echo.echo_const import ECHO_CLONE_STAGE, ECHO_CLONE_COMMAND
from aurora_echo.echo_util import EchoUtil, log_prefix_factory, validate_input_param
from aurora_echo.entry import root

rds = boto3.client('rds')

today_string = '{0:%Y-%m-%d}'.format(datetime.now(timezone.utc))

log_prefix = log_prefix_factory(ECHO_CLONE_COMMAND)


def collect_clone_params(source_cluster_name: str, new_cluster_name: str, db_subnet_group_name: str,
                         vpc_security_group_id: list, tags: list):
    """
    Convert parameters into a dict of known values appropriate to be used in an RDS API call.

    Optional inputs we do not use and therefore do not support yet
        Port=123,
        OptionGroupName='string',
        KmsKeyId='string',
        EnableIAMDatabaseAuthentication='string',
        RestoreToTime=datetime(2015, 1, 1),

    RestoreToTime is mutually exclusive with RestoreType='copy-on-write'. We currently do not support full copies.

    :return: params
    """

    params = {}

    # Required params
    params['DBClusterIdentifier'] = new_cluster_name
    params['RestoreType'] = 'copy-on-write'
    params['SourceDBClusterIdentifier'] = source_cluster_name
    params['UseLatestRestorableTime'] = True
    params['DBSubnetGroupName'] = db_subnet_group_name

    # Optional params
    if vpc_security_group_id:
        params['VpcSecurityGroupIds'] = [vpc for vpc in vpc_security_group_id]

    # Our tags indicating the instance is managed, plus optional user-defined tags
    params['Tags'] = tags  # a list of dicts

    return params


def collect_instance_params(cluster_identifier: str, new_instance_name: str, engine: str, db_instance_class: str,
                           availability_zone: str, tags: list, db_parameter_group_name: str):
    """
    Convert parameters into a dict of known values appropriate to be used in an RDS API call.
    :return: params
    """

    params = {}

    # Required params
    params['DBInstanceIdentifier'] = new_instance_name
    params['DBClusterIdentifier'] = cluster_identifier  # this is replaced later with the value returned from AWS. Here now to show the user our intention
    params['Engine'] = engine
    params['DBInstanceClass'] = db_instance_class

    # Optional params
    if availability_zone:
        params['AvailabilityZone'] = availability_zone

    # db parameter group name
    if db_parameter_group_name:
        params['DBParameterGroupName'] = db_parameter_group_name

    # Our tags indicating the instance is managed, plus optional user-defined tags
    params['Tags'] = tags  # a list of dicts

    return params


def create_clone_cluster_and_instance(clone_params: dict, instance_params: dict, interactive: bool):
    click.echo('{} Clone settings:'.format(log_prefix()))
    click.echo(json.dumps(clone_params, indent=4, sort_keys=True))

    if interactive:
        click.confirm('{} Ready to create cluster clone and instance with these settings?'.format(log_prefix()), abort=True)  # exits entirely if no

    click.echo('{} Creating copy-on-write clone...'.format(log_prefix()))
    response = rds.restore_db_cluster_to_point_in_time(**clone_params)

    # don't assume the cluster name came back exactly the same; use the one we received from aws
    cluster_identifier = response['DBCluster']['DBClusterIdentifier']
    instance_params['DBClusterIdentifier'] = cluster_identifier
    response = rds.create_db_instance(**instance_params)

    click.echo('{} Success! Clone and instance created.'.format(log_prefix()))
    click.echo(json.dumps(response, indent=4, sort_keys=True))


@root.command()
@click.option('--aws-account-number', '-a', callback=validate_input_param, required=True)
@click.option('--region', '-r', callback=validate_input_param, required=True)
@click.option('--source-cluster-name', '-s', callback=validate_input_param, required=True)
@click.option('--managed-name', '-n', callback=validate_input_param, required=True)
@click.option('--db-subnet-group-name', '-sub', callback=validate_input_param, required=True)
@click.option('--db-instance-class', '-c', callback=validate_input_param, required=True)
@click.option('--engine', '-e', default='aurora')
@click.option('--availability-zone', '-az')
@click.option('--vpc-security-group-id', '-sg', multiple=True)
@click.option('--tag', '-t', multiple=True)
@click.option('--minimum-age-hours', '-h', default=20, type=float)
@click.option('--interactive', '-i', default=True, type=bool)
@click.option('--db-parameter-group-name', '-pgn')
@click.option('--suffix', '-sf', default=None)
def clone(aws_account_number: str, region: str, source_cluster_name: str, managed_name: str, db_subnet_group_name: str, db_instance_class: str,
          engine: str, availability_zone: str, vpc_security_group_id: list, tag: list, minimum_age_hours: int, interactive: bool, db_parameter_group_name: str, suffix: str):
    click.echo('{} Starting aurora-echo for {}'.format(log_prefix(), managed_name))
    util = EchoUtil(region, aws_account_number)
    if not util.instance_too_new(managed_name, minimum_age_hours):

        restore_cluster_name = managed_name + '-' + today_string

        if suffix is not None:
            restore_cluster_name += '-' + suffix

        tag_set = util.construct_managed_tag_set(managed_name, ECHO_CLONE_STAGE)
        user_tags = util.construct_user_tag_set(tag)
        if user_tags:
            tag_set.extend(user_tags)

        # collect parameters up front so we only have to prompt the user once
        cluster_params = collect_clone_params(source_cluster_name, restore_cluster_name, db_subnet_group_name, vpc_security_group_id, tag_set)
        instance_params = collect_instance_params(restore_cluster_name, restore_cluster_name, engine, db_instance_class, availability_zone, tag_set, db_parameter_group_name)  # instance and cluster names are the same
        create_clone_cluster_and_instance(cluster_params, instance_params, interactive)

    else:
        click.echo('{} Found managed instance created less than {} hours ago. Not proceeding.'.format(log_prefix(), minimum_age_hours))
