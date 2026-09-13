import json
import os
import uuid
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
RESOURCES_TABLE = os.environ.get('RESOURCES_TABLE')

def generate_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True,
        },
        'body': json.dumps(body, cls=DecimalEncoder)
    }

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj)
        return super(DecimalEncoder, self).default(obj)

def handler(event, context):
    table = dynamodb.Table(RESOURCES_TABLE)
    http_method = event.get('httpMethod')

    try:
        if http_method == 'GET':
            # List all resources
            response = table.scan()
            items = response.get('Items', [])
            return generate_response(200, items)
            
        elif http_method == 'POST':
            # Create a new resource
            body = json.loads(event.get('body', '{}'))
            resource_id = str(uuid.uuid4())
            item = {
                'ResourceId': resource_id,
                'Name': body.get('name', 'Unknown Resource'),
                'Type': body.get('type', 'Classroom'),
                'Capacity': body.get('capacity', 0),
                'Status': 'Available'
            }
            table.put_item(Item=item)
            return generate_response(201, {'message': 'Resource created', 'ResourceId': resource_id})
            
        else:
            return generate_response(405, {'message': 'Method Not Allowed'})
            
    except Exception as e:
        print(f"Error: {e}")
        return generate_response(500, {'message': 'Internal server error'})
