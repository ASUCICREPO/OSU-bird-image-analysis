import { defineBackend } from '@aws-amplify/backend';
import { PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
import { EventType } from 'aws-cdk-lib/aws-s3';
import { LambdaDestination } from 'aws-cdk-lib/aws-s3-notifications';
import { auth } from './auth/resource';
import { storage } from './storage/resource';
import { birdProcessor } from './functions/bird-processor/resource';
import { createSageMakerNotebook } from './custom/sagemaker-notebook';
import { config } from 'dotenv';

// Load environment variables from .env file
config();

/**
 * Reverted to simple sequential processing
 * @see https://docs.amplify.aws/react/build-a-backend/
 */
const backend = defineBackend({
  auth,
  storage,
  birdProcessor
});

// Grant the Lambda function permissions to access S3 and Bedrock
backend.birdProcessor.resources.lambda.addToRolePolicy(
  new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      's3:GetObject',
      's3:PutObject',
      's3:DeleteObject',
      's3:ListBucket',
      's3:CopyObject'
    ],
    resources: [
      backend.storage.resources.bucket.bucketArn,
      `${backend.storage.resources.bucket.bucketArn}/*`
    ]
  })
);

backend.birdProcessor.resources.lambda.addToRolePolicy(
  new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      'bedrock:InvokeModel'
    ],
    resources: [
      'arn:aws:bedrock:*::foundation-model/*',
      'arn:aws:bedrock:*:*:inference-profile/*'
    ]
  })
);

// Add SageMaker permissions to Lambda
backend.birdProcessor.resources.lambda.addToRolePolicy(
  new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      'sagemaker:DescribeNotebookInstance',
      'sagemaker:StartNotebookInstance',
      'sagemaker:StopNotebookInstance',
      'sagemaker:CreateEndpoint',
      'sagemaker:DeleteEndpoint',
      'sagemaker:DescribeEndpoint'
    ],
    resources: ['*']
  })
);

// Configure S3 event notifications to trigger Lambda function
backend.storage.resources.bucket.addEventNotification(
  EventType.OBJECT_CREATED,
  new LambdaDestination(backend.birdProcessor.resources.lambda),
  {
    prefix: 'uploads/',
    suffix: '.zip'
  }
);

backend.storage.resources.bucket.addEventNotification(
  EventType.OBJECT_CREATED,
  new LambdaDestination(backend.birdProcessor.resources.lambda),
  {
    prefix: 'public/uploads/',
    suffix: '.zip'
  }
);

// Also trigger on individual image uploads
const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp'];

for (const ext of imageExtensions) {
  backend.storage.resources.bucket.addEventNotification(
    EventType.OBJECT_CREATED,
    new LambdaDestination(backend.birdProcessor.resources.lambda),
    {
      prefix: 'uploads/',
      suffix: ext
    }
  );
  
  backend.storage.resources.bucket.addEventNotification(
    EventType.OBJECT_CREATED,
    new LambdaDestination(backend.birdProcessor.resources.lambda),
    {
      prefix: 'public/uploads/',
      suffix: ext
    }
  );
}

// Create SageMaker notebook for species classification
const sagemakerResources = createSageMakerNotebook(
  backend.createStack('SageMakerStack'),
  backend.storage.resources.bucket
);

export default backend;
