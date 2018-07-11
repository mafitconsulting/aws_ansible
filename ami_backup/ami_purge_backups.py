from __future__ import print_function
import boto3
import datetime
import collections
import logging
import time

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Lets connect to the low level boto client.
ec2_instances = boto3.client('ec2')

# and connect to the OO API resource, easier for some attributes
ec2 = boto3.resource('ec2')

# Lets filter the images on owner. Less work, increased lambda performance
images = ec2.images.filter(Owners=["self"])

def clean_amis(event, context):
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
    
    print("Found %d instances that need backing up" % len(instances))
    
    # Using a defaultdict on the collection to prevent keyerror!
    # This means that if a key is not found in the dictionary, then instead of a KeyError
    # being thrown, a new entry is created. The type of this new entry is given by the argument
    # of defaultdict
    to_tag = collections.defaultdict(list)
    
    # Initialise our image list
    imagesList = []
    
    # obtain date
    date = datetime.datetime.now()
    
    # format to string
    date_fmt = date.strftime('%Y-%m-%d')
    
    # Set to true on confirmation of today's backup
    todays_backup = False
    
    # Loop through all of our instances we obtained from out filtered list
    for instance in instances:
        # obtain instance_name with some list comprehension
        instance_name = [x['Value'] for x in instance['Tags'] if x['Key'] == 'Name'][0]
        # obtain instance id attribute
        instance_id = instance['InstanceId']
        print("\n" + instance_name + " (" + instance_id + ")")
        
        # Initialise image count
        count = 0
    
        # Loop through each image of our current instance
        for i in images:
            # Search for the backup pattern
            if i.name.startswith('Lambda - ' + instance_id):
                print("FOUND IMAGE " + i.id + " FOR INSTANCE " + instance_id)
                count += 1
                try:
                    if i.tags is not None:
                        deletion_date = [
                            t.get('Value') for t in i.tags
                            if t['Key'] == 'DeleteOn'][0]
                        delete_date = time.strptime(deletion_date, "%m-%d-%Y")
                except IndexError:
                    deletion_date = False
                    delete_date = False
    
                today_time = datetime.datetime.now().strftime('%m-%d-%Y')
                # today_fmt = today_time.strftime('%m-%d-%Y')
                today_date = time.strptime(today_time, '%m-%d-%Y')
        
                # If image's DeleteOn date is less than or equal to today,
                # add this image to our list of images to process later
                if delete_date <= today_date:
                    imagesList.append(i.id)
        
                # Make sure we have an AMI from today and mark todays as true
                if i.name.endswith(date_fmt):
                    # Our latest backup from our other Lambda Function succeeded
                    todays_backup = True
                    print("Latest backup from " + date_fmt + " was a success")

        print("instance " + instance['InstanceId'] + " has " + str(count) + " AMIs")
    
        if not imagesList:
            print("No AMIs to purge")
        else:
            print("AMIs to purge:")
            print (imagesList)
    
        if todays_backup:
            assert isinstance(boto3.client('sts').get_caller_identity, object)
            myAccount = boto3.client('sts').get_caller_identity()['Account']
            snapshots = ec2_instances.describe_snapshots(OwnerIds=[myAccount])['Snapshots']
    
            # loop through list of image IDs
            for image in imagesList:
                print("deregistering image %s" % image)
                amiResponse = ec2_instances.deregister_image(DryRun=False, ImageId=image)
    
                for snapshot in snapshots:
                    if snapshot['Description'].find(image) > 0:
                        snap = ec2_instances.delete_snapshot(SnapshotId=snapshot['SnapshotId'])
                        print("Deleting snapshot " + snapshot['SnapshotId'])
    
        else:
            print("Today's backup not found, exiting...")
