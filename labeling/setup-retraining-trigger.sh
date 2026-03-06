#!/bin/bash
# Deploys two Lambda functions and two EventBridge rules:
#   1. retrain-on-labeling-complete  — fires when a Ground Truth job finishes
#   2. update-model-on-training-complete — fires when the training job finishes
#
# Run once after deploying the sandbox backend.

set -e

PROFILE="--profile test-account"
REGION="us-west-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text $PROFILE)
BUCKET=$(cat ../amplify_outputs.json | grep -o '"bucket_name":"[^"]*' | cut -d'"' -f4)
ROLE_ARN=$(aws iam get-role --role-name SageMakerExecutionRole --query 'Role.Arn' --output text $PROFILE)
MODEL_BUCKET="bird-model-TIMESTAMP"           # <-- update to your model bucket from DEPLOYMENT.md Step 2.3
MODEL_S3_KEY="models/bird-species-model.tar.gz"
MODEL_NAME="bird-species-detection-model-i107-fr-1l"
ENDPOINT_NAME=""                              # <-- set if you have a live endpoint, otherwise leave blank
ENDPOINT_CONFIG_NAME="bird-species-endpoint-config"  # keep this fixed — it gets reused every retrain

# ---- Package the Lambda ----
echo "Packaging Lambda..."
zip -j retrain-lambda.zip retrain-lambda.py

# ---- IAM role for Lambda ----
LAMBDA_ROLE_NAME="BirdRetrainLambdaRole"

# Create role if it doesn't exist
aws iam get-role --role-name $LAMBDA_ROLE_NAME $PROFILE 2>/dev/null || \
aws iam create-role \
  --role-name $LAMBDA_ROLE_NAME \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' $PROFILE

aws iam attach-role-policy --role-name $LAMBDA_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess $PROFILE
aws iam attach-role-policy --role-name $LAMBDA_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess $PROFILE

LAMBDA_ROLE_ARN=$(aws iam get-role --role-name $LAMBDA_ROLE_NAME \
  --query 'Role.Arn' --output text $PROFILE)

echo "Lambda role: $LAMBDA_ROLE_ARN"
sleep 10  # wait for role propagation

# ---- Lambda 1: retrain when labeling completes ----
RETRAIN_LAMBDA_NAME="bird-retrain-on-labeling-complete"

aws lambda get-function --function-name $RETRAIN_LAMBDA_NAME $PROFILE --region $REGION 2>/dev/null && \
  aws lambda update-function-code \
    --function-name $RETRAIN_LAMBDA_NAME \
    --zip-file fileb://retrain-lambda.zip \
    $PROFILE --region $REGION || \
  aws lambda create-function \
    --function-name $RETRAIN_LAMBDA_NAME \
    --runtime python3.12 \
    --role $LAMBDA_ROLE_ARN \
    --handler retrain-lambda.handler \
    --zip-file fileb://retrain-lambda.zip \
    --timeout 60 \
    --environment "Variables={
      MODEL_BUCKET=$MODEL_BUCKET,
      SAGEMAKER_ROLE_ARN=$ROLE_ARN,
      SAGEMAKER_MODEL_NAME=$MODEL_NAME,
      SAGEMAKER_ENDPOINT_NAME=$ENDPOINT_NAME,
      SAGEMAKER_ENDPOINT_CONFIG_NAME=$ENDPOINT_CONFIG_NAME,
      REGION=$REGION
    }" \
    $PROFILE --region $REGION

RETRAIN_LAMBDA_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$RETRAIN_LAMBDA_NAME"

# ---- Lambda 2: update model when training completes ----
UPDATE_LAMBDA_NAME="bird-update-model-on-training-complete"

aws lambda get-function --function-name $UPDATE_LAMBDA_NAME $PROFILE --region $REGION 2>/dev/null && \
  aws lambda update-function-code \
    --function-name $UPDATE_LAMBDA_NAME \
    --zip-file fileb://retrain-lambda.zip \
    $PROFILE --region $REGION || \
  aws lambda create-function \
    --function-name $UPDATE_LAMBDA_NAME \
    --runtime python3.12 \
    --role $LAMBDA_ROLE_ARN \
    --handler retrain-lambda.update_model_after_training \
    --zip-file fileb://retrain-lambda.zip \
    --timeout 60 \
    --environment "Variables={
      MODEL_BUCKET=$MODEL_BUCKET,
      SAGEMAKER_ROLE_ARN=$ROLE_ARN,
      SAGEMAKER_MODEL_NAME=$MODEL_NAME,
      SAGEMAKER_ENDPOINT_NAME=$ENDPOINT_NAME,
      SAGEMAKER_ENDPOINT_CONFIG_NAME=$ENDPOINT_CONFIG_NAME,
      REGION=$REGION
    }" \
    $PROFILE --region $REGION

UPDATE_LAMBDA_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$UPDATE_LAMBDA_NAME"

# ---- EventBridge Rule 1: labeling job completed ----
echo "Creating EventBridge rule for labeling job completion..."

aws events put-rule \
  --name "bird-labeling-job-completed" \
  --event-pattern '{
    "source": ["aws.sagemaker"],
    "detail-type": ["SageMaker Ground Truth Labeling Job State Change"],
    "detail": {
      "LabelingJobStatus": ["Completed"]
    }
  }' \
  --state ENABLED \
  $PROFILE --region $REGION

aws events put-targets \
  --rule "bird-labeling-job-completed" \
  --targets "[{\"Id\": \"RetrainLambda\", \"Arn\": \"$RETRAIN_LAMBDA_ARN\"}]" \
  $PROFILE --region $REGION

aws lambda add-permission \
  --function-name $RETRAIN_LAMBDA_NAME \
  --statement-id "AllowEventBridgeLabelingJob" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:$REGION:$ACCOUNT_ID:rule/bird-labeling-job-completed" \
  $PROFILE --region $REGION 2>/dev/null || true

# ---- EventBridge Rule 2: training job completed ----
echo "Creating EventBridge rule for training job completion..."

aws events put-rule \
  --name "bird-training-job-completed" \
  --event-pattern '{
    "source": ["aws.sagemaker"],
    "detail-type": ["SageMaker Training Job State Change"],
    "detail": {
      "TrainingJobStatus": ["Completed"],
      "TrainingJobName": [{"prefix": "bird-retrain-"}]
    }
  }' \
  --state ENABLED \
  $PROFILE --region $REGION

aws events put-targets \
  --rule "bird-training-job-completed" \
  --targets "[{\"Id\": \"UpdateModelLambda\", \"Arn\": \"$UPDATE_LAMBDA_ARN\"}]" \
  $PROFILE --region $REGION

aws lambda add-permission \
  --function-name $UPDATE_LAMBDA_NAME \
  --statement-id "AllowEventBridgeTrainingJob" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:$REGION:$ACCOUNT_ID:rule/bird-training-job-completed" \
  $PROFILE --region $REGION 2>/dev/null || true

echo ""
echo "Done. Full pipeline active:"
echo "  Labeling job completes → $RETRAIN_LAMBDA_NAME → SageMaker training job"
echo "  Training job completes → $UPDATE_LAMBDA_NAME → model + endpoint updated"
echo ""
echo "To monitor:"
echo "  aws logs tail /aws/lambda/$RETRAIN_LAMBDA_NAME --follow $PROFILE --region $REGION"
echo "  aws logs tail /aws/lambda/$UPDATE_LAMBDA_NAME --follow $PROFILE --region $REGION"

# Cleanup
rm -f retrain-lambda.zip
