import json
import os
import uuid
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

BOOKINGS_TABLE = os.environ.get('BOOKINGS_TABLE')
RESOURCES_TABLE = os.environ.get('RESOURCES_TABLE')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj)
        return super(DecimalEncoder, self).default(obj)

def generate_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

def check_conflict(resource_id, start_time, end_time, requested_capacity):
    # 1. Get the resource's total capacity
    res_table = dynamodb.Table(RESOURCES_TABLE)
    res_response = res_table.get_item(Key={'ResourceId': resource_id})
    if 'Item' not in res_response:
        return True, "Resource not found"
        
    total_capacity = int(res_response['Item'].get('Capacity', 1))
    
    # 2. Query all bookings for this resource
    table = dynamodb.Table(BOOKINGS_TABLE)
    response = table.query(
        IndexName="ResourceIdIndex",
        KeyConditionExpression=Key('ResourceId').eq(resource_id)
    )
    items = response.get('Items', [])
    
    # 3. Calculate concurrent usage
    # For a simple check, we check if at ANY point during the requested interval, 
    # the capacity is exceeded.
    # To do this accurately, we can sum capacity of all bookings that overlap.
    # (Note: A rigorous interval tree is better, but summing all overlaps is safe and conservative)
    used_capacity = 0
    for item in items:
        if item.get('Status') in ['Rejected', 'Cancelled']:
            continue
            
        b_start = item['StartTime']
        b_end = item['EndTime']
        
        # Overlap condition: start < b_end AND end > b_start
        if start_time < b_end and end_time > b_start:
            used_capacity += int(item.get('RequiredCapacity', 1))
            
    if used_capacity + requested_capacity > total_capacity:
        return True, f"Capacity exceeded. Available: {total_capacity - used_capacity}"
        
    return False, ""

def notify_user(message):
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject="Smart Campus Booking Notification"
        )
    except Exception as e:
        print(f"Failed to send SNS: {e}")

def get_role(email):
    if email == 'admin@smartcampus.com':
        return 'Admin'
    elif email.startswith('faculty') and email.endswith('@smartcampus.com'):
        return 'Faculty'
    return 'Student'

def handler(event, context):
    table = dynamodb.Table(BOOKINGS_TABLE)
    http_method = event.get('httpMethod')

    try:
        if http_method == 'GET':
            # List all bookings
            response = table.scan()
            return generate_response(200, response.get('Items', []))
            
        elif http_method == 'POST':
            # Extract user info from Cognito Authorizer
            claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
            user_id = claims.get('email', 'Unknown User')
            role = get_role(user_id)
            
            body = json.loads(event.get('body', '{}'))
            resource_id = body.get('resourceId')
            start_time = body.get('startTime')
            end_time = body.get('endTime')
            purpose = body.get('purpose', '')
            requested_capacity = int(body.get('requiredCapacity', 1))
            
            if not all([resource_id, start_time, end_time]):
                return generate_response(400, {'message': 'Missing required fields'})
            
            # Conflict Detection based on capacity
            is_conflict, msg = check_conflict(resource_id, start_time, end_time, requested_capacity)
            if is_conflict:
                return generate_response(409, {'message': msg})
            
            # Approval Workflow Rule: Faculty auto-approved, Students need approval
            status = 'Approved' if role == 'Faculty' else 'Pending'
            
            booking_id = str(uuid.uuid4())
            item = {
                'BookingId': booking_id,
                'ResourceId': resource_id,
                'UserId': user_id,
                'Role': role,
                'StartTime': start_time,
                'EndTime': end_time,
                'Purpose': purpose,
                'RequiredCapacity': requested_capacity,
                'Status': status,
                'CreatedAt': datetime.utcnow().isoformat()
            }
            table.put_item(Item=item)
            
            # Notification
            msg = f"New booking {booking_id} created by {user_id}. Status: {status}."
            notify_user(msg)
            
            return generate_response(201, {'message': 'Booking request submitted', 'BookingId': booking_id, 'Status': status})
            
        elif http_method == 'PUT':
            # Approve/Reject/Cancel a booking
            booking_id = event['pathParameters']['bookingId']
            body = json.loads(event.get('body', '{}'))
            new_status = body.get('status')
            
            if new_status not in ['Approved', 'Rejected', 'Cancelled']:
                return generate_response(400, {'message': 'Invalid status update'})
                
            response = table.update_item(
                Key={'BookingId': booking_id},
                UpdateExpression="set #st = :s",
                ExpressionAttributeNames={'#st': 'Status'},
                ExpressionAttributeValues={':s': new_status},
                ReturnValues="UPDATED_NEW"
            )
            
            msg = f"Booking {booking_id} has been {new_status}."
            notify_user(msg)
            
            return generate_response(200, {'message': 'Booking updated successfully', 'Updated': response})
            
        else:
            return generate_response(405, {'message': 'Method Not Allowed'})
            
    except Exception as e:
        print(f"Error: {e}")
        return generate_response(500, {'message': str(e)})
