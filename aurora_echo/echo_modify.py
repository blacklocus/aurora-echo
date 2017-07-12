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


import boto3
import click

from aurora_echo.echo_const import ECHO_NEW_STAGE, ECHO_MODIFY_COMMAND, ECHO_MODIFY_STAGE
from aurora_echo.echo_util import EchoUtil, log_prefix_factory, validate_input_param
from aurora_echo.entry import root

rds = boto3.client('rds')

log_prefix = log_prefix_factory(ECHO_MODIFY_COMMAND)


def is_cluster_available(cluster_identifier: str):
    """
    Look up the cluster and make sure it's not currently being created,
    as we will not be able to modify it yet

    return if cluster is available for modification
    """

    response = rds.describe_db_clusters(DBClusterIdentifier=cluster_identifier)
    cluster_map = response['DBClusters'][0]  # we got the cluster from the instance, so assume it exists
    return cluster_map['Status'] == 'available'


def modify_iam(cluster_identifier: str, iam_role_names: tuple, interactive: bool, util: EchoUtil):
    """
    Update the IAM role on the cluster

    If we add more modifications, consolidate them into one method so we can prompt the user only once
    """

    if iam_role_names:
        iam_role_arn_list = []
        for iam_name in iam_role_names:
            arn = util.construct_iam_arn(iam_name)
            iam_role_arn_list.append(arn)
            click.echo('{} IAM: {}'.format(log_prefix(), arn))

        # pop out of the loop to ask if this is all good
        if interactive:
            click.confirm('{} Ready to modify cluster with these settings?'.format(log_prefix()), abort=True)  # exits entirely if no

        click.echo('{} Adding IAM to cluster...'.format(log_prefix()))

        for iam_role_arn in iam_role_arn_list:
            iam_response = rds.add_role_to_db_cluster(DBClusterIdentifier=cluster_identifier, RoleArn=iam_role_arn)
    else:
        # even if they didn't want an IAM added, it still successfully passed through this stage
        click.echo('{} No IAM roles provided. Nothing to do! {}'.format(log_prefix(), cluster_identifier))



@root.command()
@click.option('--aws-account-number', '-a', callback=validate_input_param, required=True)
@click.option('--region', '-r', callback=validate_input_param, required=True)
@click.option('--managed-name', '-n', callback=validate_input_param, required=True)
@click.option('--iam-role-name', '-iam', default=None, multiple=True)
@click.option('--interactive', '-i', default=True, type=bool)
def modify(aws_account_number: str, region: str, managed_name: str, iam_role_name: tuple, interactive: bool):
    click.echo('{} Starting aurora-echo for {}'.format(log_prefix(), managed_name))
    util = EchoUtil(region, aws_account_number)

    # click doesn't allow mismatches between option and parameter names, so just for clarity, this is a tuple
    iam_role_names = iam_role_name

    found_instance = util.find_instance_in_stage(managed_name, ECHO_NEW_STAGE)
    if found_instance:

        cluster_identifier = found_instance['DBClusterIdentifier']

        if is_cluster_available(cluster_identifier):
            click.echo('{} Instance has modifiable cluster: {}'.format(log_prefix(), cluster_identifier))

            modify_iam(cluster_identifier, iam_role_names, interactive, util)

            click.echo('{} Updating tag for modified instance: {}'.format(log_prefix(), found_instance['DBInstanceIdentifier']))
            util.add_stage_tag(managed_name, found_instance, ECHO_MODIFY_STAGE)

            click.echo('{} Done!'.format(log_prefix()))
        else:
            click.echo('{} Cluster {} does not have status \'available\'. Not proceeding.'.format(log_prefix(), cluster_identifier))
    else:
        click.echo('{} No instance found in stage {}. Not proceeding.'.format(log_prefix(), ECHO_NEW_STAGE))
