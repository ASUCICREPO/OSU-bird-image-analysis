import { defineFunction } from '@aws-amplify/backend';
import { Function, Runtime, Code } from 'aws-cdk-lib/aws-lambda';
import { Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const birdProcessor = defineFunction((scope: Construct) => {
  return new Function(scope, 'BirdProcessorFunction', {
    runtime: Runtime.PYTHON_3_12,
    handler: 'handler.lambda_handler',
    code: Code.fromAsset(__dirname),
    timeout: Duration.minutes(15),
    memorySize: 1024,
    environment: {
      BEDROCK_REGION: process.env.BEDROCK_REGION || 'us-west-2',
      CLAUDE_MODEL_ID: process.env.CLAUDE_MODEL_ID || 'global.anthropic.claude-sonnet-4-20250514-v1:0',
      CONTAINER_IMAGE: process.env.CONTAINER_IMAGE || ''
    }
  });
}, {
  resourceGroupName: 'storage'
});
