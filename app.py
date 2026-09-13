#!/usr/bin/env python3
import os

import aws_cdk as cdk
from smart_campus.smart_campus_stack import SmartCampusStack

app = cdk.App()
SmartCampusStack(app, "SmartCampusStack",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.
    # env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)

app.synth()
