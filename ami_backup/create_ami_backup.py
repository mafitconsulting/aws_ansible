# This lambda function will back up ec2 instances
# which are filtered by build infra. In a nutshell,
# it will loop around those instances, create an ami
# of the instance including all ebs block mappings
# and tag the ami for a deletion date. So when we
# run out ami clean up function, we know which amis are
# tagged for deletion on that day.
# Retention period is currently hardcoded at 2 days

from __future__ import print_function
import boto3
import datetime
import collections
import logging


# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def ec2_ami_backup(event, context):

    # Lets connect to the low level boto client.
    ec2_instances = boto3.client('ec2')

    # Describe our build instances based around
    # the following :- jmp, bldapi, bldjob, pup etc
    res = ec2_instances.describe_instances(
        Filters=[
            {'Name': 'tag:Name', 'Values': ['am1*', 'ansible']},
        ]
    ).get('Reservations', [])

    # Flatten the list of instances returned
    instances = sum(
        [
            [i for i in r['Instances']]  # list comprehension, its the future
            for r in res
        ], [])

    print ("Found %d instances that need backing up" % len(instances))

    # Using a defaultdict on the collection to prevent keyerror!
    # This means that if a key is not found in the dictionary, then instead of 
    # a KeyError being thrown, a new entry is created. The type of this new 
    # entry is given by the argument of defaultdict
    to_tag = collections.defaultdict(list)

    # retention period, we can have this as a config 
    # setting but hardcoding for timebeing
    keep_for = 2
    # initialise completion list
    complete = []
    # loop through instances
    for instance in instances:
        # cos we're using low level client wrapper and not the OO resource api
        # We need a nice little list comprehension to obtain instance name from tag
        instance_name = [x['Value'] for x in instance['Tags'] if x['Key'] == 'Name'][0]
        instance_id = instance['InstanceId']
        print ("\n" + instance_name + " (" + instance_id + ")")
        # Get current time
        current_datetime = datetime.datetime.now()
        # Convert to str
        date_stamp = current_datetime.strftime('%H-%M-%S(UTC)--on--%Y-%m-%d')
        print ("\n" + date_stamp)
        # Avoid duplicating ami creation, we insert instance id to complete list
        if str(instance_id) not in complete:
            # Create ami
            AMIid = ec2_instances.create_image(InstanceId=instance_id, 
                                  Name="Lambda - " + instance_id + " on " + date_stamp,
                                  Description="Lambda created AMI of instance " +
                                  instance_name + " from " + date_stamp, NoReboot=True, 
                                  DryRun=False)
            # insert instance_id into completed list
            complete.insert(0, str(instance_id))
            print ("Created AMI %s of instance %s " % (AMIid['ImageId'], instance_id))
        else:
            print ("We already got an AMI of instance %s " % instance_id)

        print ("AMI creation started")
        print ("AMI name: " + instance_name)

        # Set up ami tagging
        to_tag[keep_for].append(AMIid['ImageId'])
        ec2 = boto3.resource('ec2')
       
        print ("Creating AMI %s of instance %s and retaining for %d days" % (
            AMIid['ImageId'],
            instance_id,
            keep_for,
        ))
         
        tag_image = ec2.Image(AMIid['ImageId'])
        tag_image.create_tags(
            Tags=[
                {'Key': 'InstanceID', 'Value': instance_id},
            ]
        )

    print (to_tag.keys())

    for keep_for in to_tag.keys():
        delete_date = datetime.date.today() + datetime.timedelta(days=keep_for)
        delete_fmt = delete_date.strftime('%m-%d-%Y')
        print ("Will delete %d AMIs on %s" % (len(to_tag[keep_for]), delete_fmt))

        ec2_instances.create_tags(
            Resources=to_tag[keep_for],
            Tags=[
                {'Key': 'DeleteOn', 'Value': delete_fmt},
            ]
        )
