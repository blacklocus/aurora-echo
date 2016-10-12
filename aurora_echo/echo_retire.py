##
# The MIT License (MIT)
#
# Copyright (c) 2016 BlackLocus
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

import boto3
import click

from aurora_echo.echo_const import ECHO_RETIRE_COMMAND, ECHO_RETIRE_STAGE
from aurora_echo.echo_util import EchoUtil, log_prefix_factory
from aurora_echo.entry import root

rds = boto3.client('rds')

log_prefix = log_prefix_factory(ECHO_RETIRE_COMMAND)


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
    
    click.echo('{} Parameters:'.format(log_prefix()))
    click.echo(json.dumps(instance_params, indent=4, sort_keys=True))
    click.echo(json.dumps(cluster_params, indent=4, sort_keys=True))

    if interactive:
        click.confirm('{} Ready to DELETE/DESTROY/REMOVE this database instance and cluster '
                      'along with ALL AUTOMATED BACKUPS?'.format(log_prefix()), abort=True)  # exits entirely if no

    # delete the instance first so the cluster is empty, otherwise it'll fail
    response = rds.delete_db_instance(**instance_params)
    response = rds.delete_db_cluster(**cluster_params)


@root.command()
@click.option('--aws_account_number', '-a', required=True)
@click.option('--region', '-r', required=True)
@click.option('--managed_name', '-n', required=True)
@click.option('--interactive', '-i', default=True, type=bool)
def retire(aws_account_number: str, region: str, managed_name: str, interactive: bool):
    click.echo('{} Starting aurora-echo'.format(log_prefix()))
    util = EchoUtil(region, aws_account_number)

    found_instance = util.find_instance_in_stage(managed_name, ECHO_RETIRE_STAGE)
    if found_instance:
        click.echo('{} Found instance ready for retirement: {}'.format(log_prefix(), found_instance['DBInstanceIdentifier']))
        delete_instance(found_instance, interactive)

        click.echo('{} Done!'.format(log_prefix()))
    else:
        click.echo('{} No instance found in stage {}. Not proceeding.'.format(log_prefix(), ECHO_RETIRE_STAGE))
