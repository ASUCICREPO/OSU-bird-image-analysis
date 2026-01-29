import { Construct } from 'constructs';
import { 
  CfnNotebookInstance, 
  CfnNotebookInstanceLifecycleConfig 
} from 'aws-cdk-lib/aws-sagemaker';
import { 
  Role, 
  ServicePrincipal, 
  PolicyStatement, 
  Effect,
  ManagedPolicy 
} from 'aws-cdk-lib/aws-iam';
import { IBucket } from 'aws-cdk-lib/aws-s3';
import { Fn, Stack } from 'aws-cdk-lib';
import { readFileSync } from 'fs';
import { join } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = join(__filename, '..');
const projectRoot = join(__dirname, '../..');

export function createSageMakerNotebook(scope: Construct, bucket: IBucket) {
  // Create a new SageMaker execution role dynamically
  const sagemakerRole = new Role(scope, 'SageMakerNotebookRole', {
    assumedBy: new ServicePrincipal('sagemaker.amazonaws.com'),
    managedPolicies: [
      ManagedPolicy.fromAwsManagedPolicyName('AmazonSageMakerFullAccess')
    ]
  });

  // Add cross-region permissions for us-east-1 model access
  sagemakerRole.addToPrincipalPolicy(new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      'sagemaker:CreateModel',
      'sagemaker:CreateEndpointConfig', 
      'sagemaker:CreateEndpoint',
      'sagemaker:DeleteModel',
      'sagemaker:DeleteEndpointConfig',
      'sagemaker:DeleteEndpoint',
      'sagemaker:DescribeEndpoint',
      'sagemaker:InvokeEndpoint',
      'sagemaker:DescribeModel',
      'sagemaker:DescribeEndpointConfig'
    ],
    resources: ['*'],
    conditions: {
      StringEquals: {
        'aws:RequestedRegion': ['us-east-1', 'us-west-2']
      }
    }
  }));

  // Add ECR permissions for model images (configurable via environment)
  const ecrRepoArn = process.env.ECR_REPO_ARN || '*';
  sagemakerRole.addToPrincipalPolicy(new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      'ecr:GetDownloadUrlForLayer',
      'ecr:BatchGetImage',
      'ecr:BatchCheckLayerAvailability',
      'ecr:GetAuthorizationToken'
    ],
    resources: [ecrRepoArn]
  }));

  // Add IAM pass role permission for SageMaker (self-reference)
  sagemakerRole.addToPrincipalPolicy(new PolicyStatement({
    effect: Effect.ALLOW,
    actions: ['iam:PassRole'],
    resources: [sagemakerRole.roleArn]
  }));

  // Add S3 permissions for model data access (configurable via environment)
  const modelBucketName = process.env.MODEL_BUCKET_NAME;
  if (modelBucketName) {
    sagemakerRole.addToPrincipalPolicy(new PolicyStatement({
      effect: Effect.ALLOW,
      actions: [
        's3:GetObject',
        's3:ListBucket'
      ],
      resources: [
        `arn:aws:s3:::${modelBucketName}`,
        `arn:aws:s3:::${modelBucketName}/*`
      ]
    }));
  }

  // Add S3 write permissions for current bucket
  sagemakerRole.addToPrincipalPolicy(new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      's3:GetObject',
      's3:PutObject',
      's3:ListBucket',
      's3:DeleteObject'
    ],
    resources: [
      bucket.bucketArn,
      `${bucket.bucketArn}/*`
    ]
  }));

  // Get configuration from environment variables
  const sagemakerModelName = process.env.SAGEMAKER_MODEL_NAME || 'bird-species-detection-model';
  const sagemakerRegion = process.env.SAGEMAKER_REGION || 'us-east-1';
  const stackRegion = Stack.of(scope).region;
  const notebookName = 'bird-species-classifier-notebook-v4';

  // Read lifecycle configuration script from sagemaker folder
  const rawLifecycleScript = readFileSync(
    join(projectRoot, 'sagemaker/lifecycle_config_production.sh'),
    'utf8'
  );
  
  // Create config JSON with all parameters
  const config = {
    bucket_name: bucket.bucketName,
    model_name: sagemakerModelName,
    notebook_name: notebookName,
    s3_region: stackRegion,
    sagemaker_region: sagemakerRegion
  };
  
  // Replace placeholders in lifecycle script
  let lifecycleScript = rawLifecycleScript
    .replace(/BUCKET_NAME_PLACEHOLDER/g, bucket.bucketName)
    .replace(/CONFIG_JSON_PLACEHOLDER/g, JSON.stringify(config));

  // Note: Python script will be uploaded manually or via lifecycle script

  // Create lifecycle configuration with unique name
  const lifecycleConfig = new CfnNotebookInstanceLifecycleConfig(scope, 'BirdSpeciesLifecycleConfigV5', {
    notebookInstanceLifecycleConfigName: 'bird-species-lifecycle-config-v5',
    onStart: [{
      content: Fn.base64(lifecycleScript)
    }]
  });

  // Create minimal SageMaker notebook instance
  const notebookInstance = new CfnNotebookInstance(scope, 'BirdSpeciesNotebookV4', {
    instanceType: 'ml.t3.medium',
    roleArn: sagemakerRole.roleArn,
    notebookInstanceName: notebookName,
    lifecycleConfigName: lifecycleConfig.notebookInstanceLifecycleConfigName,
  });

  notebookInstance.addDependency(lifecycleConfig);

  return {
    notebookInstance,
    lifecycleConfig,
    sagemakerRole
  };
}
