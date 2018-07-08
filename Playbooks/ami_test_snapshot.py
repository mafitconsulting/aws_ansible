import boto3
import datetime
import collections


    
# Lets connect to the low level boto client
ec2_instances = boto3.client('ec2')

# Describe out build instances based around
# the follow :- jmp, bldapi, bldjob, pup etc
res = ec2_instances.describe_instances(
      Filters=[
         {'Name': 'tag:Name', 'Values': ['Jenkins*','ansible']},
      ]
).get('Reservations',[])
    
# Flatten the list of instances returned
    
instances = sum(
  [
      [i for i in r['Instances']]  # list comprehension, its the future
      for r in res
  ], [])
 
print "Found %d instances that need backing up" % len(instances)

# Using defaultdict on the collection to to prevent keyerror
#  means that if a key is not found in the dictionary, then instead of a KeyError being thrown, a new entry is created. The type of this new entry is given by the argument of defaultdic
to_tag = collections.defaultdict(list)
keep_for = 2
# initialise completion list
complete = []

#loop through instances
for instance in instances:
  # cos we're using low level client wrapper and not object-orientanted boto resource
  # We need a nice little list comprehension to obtain instance name from tag
  instance_name = [ x['Value'] for x in instance['Tags'] if x['Key'] == 'Name' ][0]
  instance_id = instance['InstanceId']
  print "\n" + instance_name + " (" + instance_id + ")"
  current_datetime = datetime.datetime.now()
  date_stamp = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
  ami_name = instance_name + date_stamp
  if str(instance_id) not in complete:
    AMIid = ec2_instances.create_image(InstanceId=instance_id, Name="Lambda - " + instance_id + " from " + ami_name, Description="Lambda created AMI of instance " + instance_id + " from " + ami_name, NoReboot=True, DryRun=False)
    complete.insert(0,str(instance_id))
    print "Created AMI %s of instance %s " % (AMIid['ImageId'], instance_id)
  else:
    print "We already got an AMI of instance %s " % (instance_id)

  print "AMI creation started"
  print "AMI name: " + ami_name

  to_tag[keep_for].append(AMIid['ImageId'])
  print "Retaining AMI %s of instance %s for %d days" % (
                AMIid['ImageId'],
                instance_id,
                keep_for
            )

print to_tag.keys()
for keep_for in to_tag.keys():
   delete_date = datetime.date.today() + datetime.timedelta(days=keep_for)
   delete_fmt = delete_date.strftime('%m-%d-%Y')
   print "Will delete %d AMIs on %s" % (len(to_tag[keep_for]), delete_fmt)
        
   #break
    
   ec2_instances.create_tags(
      Resources=to_tag[keep_for],
      Tags=[
          {'Key': 'DeleteOn', 'Value': delete_fmt},
      ]
   )
