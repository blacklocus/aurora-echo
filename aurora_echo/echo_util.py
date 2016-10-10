from datetime import datetime, timezone

import boto3
import click
from dateutil.relativedelta import relativedelta

rds = boto3.client('rds')


class EchoUtil(object):

    def __init__(self, region: str, account_number: str):
        self.region = region
        self.account_number = account_number

    def construct_arn(self, db_instance_identifier: str):
        return 'arn:aws:rds:%s:%s:db:%s' % (self.region, self.account_number, db_instance_identifier)

    def construct_stage_tag(self, managed_name: str):
        return 'aurora_echo:%s:stage' % managed_name

    def construct_managed_tag_set(self, managed_name: str, stage: str):
        tags = [
            {'Key': self.construct_stage_tag(managed_name), 'Value': stage},
        ]
        return tags

    def parse_user_tag(self, full_tag: str):
        split = full_tag.split('=', 1)
        return split[0], split[1]

    def construct_user_tag_set(self, tags: list):
        tag_list = []
        if tags:
            for t in tags:
                k, v = self.parse_user_tag(t)
                tag_dict = { 'Key': k, 'Value': v}
                tag_list.append(tag_dict)
        return tag_list

    def add_stage_tag(self, managed_name: str, instance: dict, next_stage: str):
        resource_arn = self.construct_arn(instance['DBInstanceIdentifier'])
        tags = [
            {'Key': self.construct_stage_tag(managed_name), 'Value': next_stage},
        ]
        response = rds.add_tags_to_resource(ResourceName=resource_arn, Tags=tags)
        return response

    def find_managed_instances(self, managed_name: str):
        stage_tag = self.construct_stage_tag(managed_name)
        managed_instances_and_tags = []

        # get list of instances
        response = rds.describe_db_instances()

        # get all their tags
        for instance in response['DBInstances']:
            tags = rds.list_tags_for_resource(ResourceName=self.construct_arn(instance['DBInstanceIdentifier']))
            tag_list = tags['TagList']
            for tag in tag_list:
                # does it have our managed tag?
                if tag['Key'] == stage_tag:
                    # (instance, current_stage_of_instance)
                    managed_instances_and_tags.append((instance, tag['Value']))
                    break  # don't keep iterating through the tag list, we're done with this instance

        return managed_instances_and_tags

    def find_instance_in_stage(self, managed_name: str, desired_stage: str):
        managed_instances_and_tags = self.find_managed_instances(managed_name)
        # filter on the stage we want
        instances_in_stage = [instance for instance, tag in managed_instances_and_tags if tag == desired_stage]

        # TODO complain about too many managed instances?
        if instances_in_stage:
            # choose most recent created time. Fun fact: instances only have the InstanceCreateTime field after creation
            sorted_instances = sorted(instances_in_stage, key=lambda inst: inst.get('InstanceCreateTime'), reverse=True)
            chosen_instance = sorted_instances[0]
            click.echo('Found instance in stage {}: {}'.format(desired_stage, chosen_instance['DBInstanceIdentifier']))
            return chosen_instance

    def instance_too_new(self, managed_name: str, min_age_in_hours: int):
        """
        Have we already made a database in the last n hours?

        :param managed_name: managed name
        :param min_age_in_hours: how many hours old is too old?
        :return: True if the database was created less than n hours ago and is therefore too new, False otherwise
        """

        today = datetime.now(timezone.utc)
        newest_allowed_date = today - relativedelta(hours=min_age_in_hours)

        instance_list = self.find_managed_instances(managed_name)
        if instance_list:
            instances = [x[0] for x in instance_list]  # we don't care about tags, but we got tags
            for instance in instances:
                if instance['DBInstanceStatus'] == 'creating':
                    return True  # an instance that is still spinning up falls under the category of "too new"
                if instance['InstanceCreateTime'] > newest_allowed_date:
                    return True  # instance was created too recently

        else:
            click.echo('No managed instances found under name {!r}.'.format(managed_name))

        return False
