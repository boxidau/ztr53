#
# adapted from github.com/Red5d/ztadmin
#

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import boto3
import botocore
import click
import json
import logging
import os
import sys
import zerotier


log_handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter('%(asctime)s[%(name)s][%(levelname)s] %(message)s')
log_handler.setFormatter(formatter)

logger = logging.getLogger('ztr53')
logger.setLevel(logging.INFO)
if os.getenv('DEBUG', None):
    logger.setLevel(logging.DEBUG)
logger.addHandler(log_handler)


@click.group()
def cli():
    pass

@cli.command()
@click.argument('network_id')
@click.argument('hosted_zone_id')
@click.option('--subdomain', default=None, help="DNS names will be name.subdomain.fqdn")
@click.option('--zt-api-token', envvar='ZT_API_TOKEN', default=None)
@click.option('--dry-run', default=False, is_flag=True)
def sync(network_id, hosted_zone_id, subdomain, zt_api_token, dry_run):
    if dry_run:
        logger.info('dry run mode is active')

    if not zt_api_token:
        try:
            with open(os.path.expanduser('~/.zerotier/api_token')) as token_fp:
                zt_api_token = token_fp.read().strip()
        except FileNotFoundError:
            logger.error('ZT api token could not be found in ~/.zerotier/api_token or envvar or CLI flags')
            exit(1)

    zt_client = zerotier.ZT(zt_api_token)
    logger.debug('Getting network: {}'.format(network_id))

    try:
        network = zt_client.network(network_id)
    except zerotier.NetworkNotFoundException:
        logger.error('Network {} not found'.format(network_id))
        exit(1)

    aws_client = boto3.client('route53')
    try:
        hosted_zone = aws_client.get_hosted_zone(Id=hosted_zone_id)
    except botocore.exceptions.ClientError as e:
        logger.error('No hosted zone found with ID: {}'.format(hosted_zone_id))
        logger.debug(e)
        exit(2)

    changes = []
    logger.info('Network {}'.format(network))
    for member in network.activeMembers:
        if member.authorized and member.name:
            record_name = '.'.join(filter(None, [
                member.name,
                subdomain,
                hosted_zone['HostedZone']['Name']
            ]))


            logger.info('{}\tA\t\t{}'.format(
                record_name,
                ' '. join(member.ipAssignments)))

            #IPv4
            changes.append({
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': record_name,
                    'Type': 'A',
                    'TTL': 60,
                    'ResourceRecords': [{'Value': ip} for ip in member.ipAssignments]
                }
            })

            # IPv6
            logger.info('{}\tAAAA\t{}'.format(record_name, member.rfc4193))
            changes.append({
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': record_name,
                    'Type': 'AAAA',
                    'TTL': 60,
                    'ResourceRecords': [
                        {
                            'Value': "{}".format(member.rfc4193)
                        },
                    ]
                }
            })

    logger.debug('Sending changeset: {}'.format(json.dumps(changes)))
    logger.info('Sending DNS changeset to route 53')

    if dry_run:
        logger.info('dry run mode - no changes made')
        return

    response = aws_client.change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={'Changes': changes}
    )
    logger.debug(response)
    logger.info('Changeset {} status: {}'.format(
        response['ChangeInfo']['Id'], response['ChangeInfo']['Status']))

cli()
