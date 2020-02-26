import json
import botocore
import boto3
import logging
import datetime
from helpers import *
from datetime import timezone
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
#=================================================================================
#                               ECS CLEAN
#=================================================================================
def ecs_cleaning(ecs_dict):
    try:
        deleted_ecs = []
        regions = get_regions()
        for region in regions['Regions']:
            ecs = boto3.client('ecs', region_name=region['RegionName'])
            try:
                ecs_result = ecs.list_clusters()
                logger.info('REGION >> ------------- '+str(region['RegionName'])+" | status: "+str(region['OptInStatus']))
                ###############################
                reg = {region['RegionName']:[]}
                terminated = {'terminated':[]}
                running = {'running':[]}
                errors = {'errors':[]}
                reg[region['RegionName']].append(terminated)
                reg[region['RegionName']].append(running)
                reg[region['RegionName']].append(errors)
                flag = False
                ###############################
                cl = ecs.describe_clusters(clusters=ecs_result['clusterArns'], include=['TAGS'])
                for cluster in cl['clusters']:
                    flag = True
                    if len(cluster['tags'])>0:
                        check_terminate_ecs(ecs, cluster, cluster['tags'], False, deleted_ecs, region['RegionName'], reg)
                    else:
                        check_terminate_ecs(ecs, cluster, None, True, deleted_ecs, region['RegionName'], reg)
                logger.info('REGION >> ------------ END')
                ###############################
                if flag:
                    ecs_dict['Regions'].append(reg)
            except botocore.exceptions.ClientError as e:
                logger.info('CleanUp >> ECS '+str(e.response['Error']['Message']))
        return get_ecs_report(deleted_ecs)
    except botocore.exceptions.ClientError as e:
        logger.info('CleanUp >> Error listing ECS '+str(e.response['Error']['Message']))
        return []

def check_terminate_ecs(ecs_client, cluster, tags, terminate_now, deleted_ecs, region_name, reg):
    try:
        if terminate_now:
            logger.info('CleanUp >> Terminating Now, has no tags (Stopping for now): '+cluster['clusterName'])
            #delete_cluster(ecs_client, cluster['clusterArn'])
            deleted_ecs.append(cluster['clusterName']+' on Region '+str(region_name))
            reg[region_name][0]['terminated'].append(cluster['clusterName'])
        else:
            if check_tags_exist(tags, get_mandatory_tags(), 3):
                logger.info('CleanUp >> ECS cluster '+cluster['clusterName']+' | has mandatory tags...')
                #delete_cluster(ecs_client, cluster['clusterArn'])
                reg[region_name][1]['running'].append(cluster['clusterName'])
            else:
                logger.info('CleanUp >> ECS cluster '+cluster['clusterName']+' missing mandatory tags, will be terminated')
                #delete_cluster(ecs_client, cluster['clusterArn'])
                deleted_ecs.append(cluster['clusterName']+' on Region '+str(region_name))
                reg[region_name][0]['terminated'].append(cluster['clusterName'])
    except botocore.exceptions.ClientError as e:
        logger.info('CleanUp >> Error terminating ECS Cluster: '+cluster['clusterName']+': '+str(e.response['Error']['Message']))
        reg[region_name][2]['errors'].append(cluster['clusterName'])

def delete_cluster(ecs_client, cluster_arn):
    try:
        instances = ecs_client.list_container_instances(cluster=cluster_arn)
        for i in instances['containerInstanceArns']:
            ecs_client.deregister_container_instance(cluster=cluster_arn,containerInstance=i,force=True)
            logger.info('CleanUp >> deregistering container instance: '+str(i))
        ecs_client.delete_cluster(cluster=cluster_arn)
    except botocore.exceptions.ClientError as e:
         logger.info('CleanUp >> Error terminating ECS Cluster: '+cluster['clusterName']+': '+str(e.response['Error']['Message']))

def get_ecs_report(deleted_ecs):
    try:
        r = " ECS Clusters deleted: \n"
        for i in deleted_ecs:
            r += "  * Cluster ID: "+str(i)+" \n"
        r += "-----------------------------------------------\n"
        return r
    except Exception as e:
        logger.info('Clean Up >> File: ecsClean.py on get_ecs_report, Error: '+str(e))
#=================================================================================