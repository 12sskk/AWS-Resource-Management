from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_cognito as cognito,
    aws_iam as iam,
    custom_resources as cr,
    triggers,
    RemovalPolicy,
    CfnOutput,
    Aws
)
from constructs import Construct
import os

class SmartCampusStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. S3 Bucket for Frontend Hosting (Created first so we can use its URL for Cognito)
        frontend_bucket = s3.Bucket(
            self, "FrontendBucket",
            website_index_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                block_public_policy=False,
                ignore_public_acls=False,
                restrict_public_buckets=False
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Use the regional domain name (HTTPS) instead of the static website URL (HTTP) 
        # because Cognito strictly requires HTTPS for callback URLs.
        frontend_url = f"https://{frontend_bucket.bucket_regional_domain_name}/index.html"

        # 2. Cognito User Pool for Authentication
        user_pool = cognito.UserPool(
            self, "SmartCampusUserPool",
            user_pool_name="SmartCampusUsers",
            self_sign_up_enabled=True,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            sign_in_aliases=cognito.SignInAliases(email=True),
            removal_policy=RemovalPolicy.DESTROY
        )

        # Unique Cognito Domain
        cognito_domain = user_pool.add_domain(
            "CognitoDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"smartcampus-{Aws.ACCOUNT_ID}-{Aws.REGION}"
            )
        )

        # App Client for the Frontend
        user_pool_client = user_pool.add_client(
            "FrontendAppClient",
            user_pool_client_name="SmartCampusFrontend",
            generate_secret=False,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(implicit_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
                callback_urls=[frontend_url, "http://localhost:8000/"] # allowing localhost for dev
            ),
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO]
        )

        # 3. DynamoDB Tables
        users_table = dynamodb.Table(self, "UsersTable", partition_key=dynamodb.Attribute(name="UserId", type=dynamodb.AttributeType.STRING), billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.DESTROY)
        resources_table = dynamodb.Table(self, "ResourcesTable", partition_key=dynamodb.Attribute(name="ResourceId", type=dynamodb.AttributeType.STRING), billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.DESTROY)
        bookings_table = dynamodb.Table(self, "BookingsTable", partition_key=dynamodb.Attribute(name="BookingId", type=dynamodb.AttributeType.STRING), billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.DESTROY)
        bookings_table.add_global_secondary_index(index_name="ResourceIdIndex", partition_key=dynamodb.Attribute(name="ResourceId", type=dynamodb.AttributeType.STRING), sort_key=dynamodb.Attribute(name="StartTime", type=dynamodb.AttributeType.STRING), projection_type=dynamodb.ProjectionType.ALL)

        # 4. SNS Topic
        booking_notifications_topic = sns.Topic(self, "BookingNotificationsTopic", display_name="Smart Campus Booking Notifications")

        # 5. Lambda Functions
        lambda_env = {
            "USERS_TABLE": users_table.table_name,
            "RESOURCES_TABLE": resources_table.table_name,
            "BOOKINGS_TABLE": bookings_table.table_name,
            "SNS_TOPIC_ARN": booking_notifications_topic.topic_arn
        }

        resources_lambda = _lambda.Function(self, "ResourcesLambda", runtime=_lambda.Runtime.PYTHON_3_9, code=_lambda.Code.from_asset("lambda"), handler="resources.handler", environment=lambda_env)
        users_table.grant_read_write_data(resources_lambda)
        resources_table.grant_read_write_data(resources_lambda)

        bookings_lambda = _lambda.Function(self, "BookingsLambda", runtime=_lambda.Runtime.PYTHON_3_9, code=_lambda.Code.from_asset("lambda"), handler="bookings.handler", environment=lambda_env)
        users_table.grant_read_data(bookings_lambda)
        resources_table.grant_read_data(bookings_lambda)
        bookings_table.grant_read_write_data(bookings_lambda)
        booking_notifications_topic.grant_publish(bookings_lambda)

        # 6. API Gateway with Cognito Authorizer
        api = apigw.RestApi(
            self, "SmartCampusApi",
            rest_api_name="Smart Campus Booking Service",
            default_cors_preflight_options={
                "allow_origins": apigw.Cors.ALL_ORIGINS,
                "allow_methods": apigw.Cors.ALL_METHODS,
                "allow_headers": ["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"]
            }
        )

        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "CampusCognitoAuthorizer",
            cognito_user_pools=[user_pool]
        )

        resources_resource = api.root.add_resource("resources")
        resources_integration = apigw.LambdaIntegration(resources_lambda)
        resources_resource.add_method("GET", resources_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        resources_resource.add_method("POST", resources_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        bookings_resource = api.root.add_resource("bookings")
        bookings_integration = apigw.LambdaIntegration(bookings_lambda)
        bookings_resource.add_method("GET", bookings_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        bookings_resource.add_method("POST", bookings_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        
        booking_item_resource = bookings_resource.add_resource("{bookingId}")
        booking_item_resource.add_method("PUT", bookings_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        # 7. Frontend Deployment & Config
        frontend_deployment = s3deploy.BucketDeployment(
            self, "DeployFrontend",
            sources=[s3deploy.Source.asset("frontend")],
            destination_bucket=frontend_bucket,
            prune=False  # Do not delete config.json!
        )

        # Write config.json to S3 dynamically
        config_content = f'{{"apiUrl": "{api.url}", "cognitoDomain": "{cognito_domain.base_url()}", "clientId": "{user_pool_client.user_pool_client_id}", "frontendUrl": "{frontend_url}"}}'
        
        write_config = cr.AwsCustomResource(
            self, "WriteFrontendConfig",
            on_update=cr.AwsSdkCall(
                service="S3",
                action="putObject",
                parameters={
                    "Bucket": frontend_bucket.bucket_name,
                    "Key": "config.json",
                    "Body": config_content,
                    "ContentType": "application/json"
                },
                physical_resource_id=cr.PhysicalResourceId.of(f"config-{api.url}-v3")
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=[frontend_bucket.arn_for_objects("config.json")]
            )
        )
        write_config.node.add_dependency(frontend_deployment)

        from aws_cdk import Duration
        
        # 8. Setup Pre-defined Users via Triggered Lambda
        setup_users_lambda = _lambda.Function(
            self, "SetupUsersLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("lambda"),
            handler="setup_users.handler",
            timeout=Duration.seconds(60),
            environment={
                "USER_POOL_ID": user_pool.user_pool_id
            }
        )
        
        # Grant permissions to create users
        setup_users_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword"],
            resources=[user_pool.user_pool_arn]
        ))
        
        # Trigger it during deployment
        triggers.Trigger(
            self, "SetupUsersTrigger",
            handler=setup_users_lambda,
            execute_on_handler_change=True
        )

        # Outputs
        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "FrontendUrl", value=frontend_url)
        CfnOutput(self, "CognitoDomain", value=cognito_domain.base_url())
        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
