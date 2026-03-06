#!/bin/bash
# Recreates the bird species bounding box labeling job in SageMaker Ground Truth.
# Prerequisites:
#   1. Run create-input-manifest.sh first
#   2. Create a private workforce in the SageMaker console and get the workteam ARN
#      Console: SageMaker > Ground Truth > Labeling workforces > Private > Create private team
#      Then invite labelers by email from the same page.

set -e

PROFILE="--profile test-account"
REGION="us-west-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text $PROFILE)
BUCKET=$(cat ../amplify_outputs.json | grep -o '"bucket_name":"[^"]*' | cut -d'"' -f4)
ROLE_ARN=$(aws iam get-role --role-name SageMakerExecutionRole --query 'Role.Arn' --output text $PROFILE)
JOB_NAME="bird-species-labeling-$(date +%s)"

# ---------------------------------------------------------------
# REQUIRED: paste the workteam ARN from the SageMaker console here
# SageMaker Console > Ground Truth > Labeling workforces > Private
# ---------------------------------------------------------------
WORKTEAM_ARN="arn:aws:sagemaker:$REGION:$ACCOUNT_ID:workteam/private-crowd/YOUR_TEAM_NAME"

if [[ "$WORKTEAM_ARN" == *"YOUR_TEAM_NAME"* ]]; then
  echo "ERROR: Set WORKTEAM_ARN at the top of this script."
  echo "Create a private workforce in the SageMaker console first."
  exit 1
fi

echo "Using bucket:    $BUCKET"
echo "Using role:      $ROLE_ARN"
echo "Using workteam:  $WORKTEAM_ARN"
echo "Job name:        $JOB_NAME"
echo ""

# Upload label categories to S3
aws s3 cp label-categories.json "s3://$BUCKET/labeling/label-categories.json" \
  $PROFILE --region $REGION
echo "Label categories uploaded."

# AWS built-in Lambda ARNs for bounding box (us-west-2)
PRE_LAMBDA="arn:aws:lambda:$REGION:081040173940:function:PRE-BoundingBox"
POST_LAMBDA="arn:aws:lambda:$REGION:081040173940:function:ACS-BoundingBox"

# Create the labeling job
aws sagemaker create-labeling-job \
  --labeling-job-name "$JOB_NAME" \
  --label-attribute-name "osu-bird-data-labelling-v1" \
  --input-config "{
    \"DataSource\": {
      \"S3DataSource\": {
        \"ManifestS3Uri\": \"s3://$BUCKET/labeling/input-manifest.jsonl\"
      }
    }
  }" \
  --output-config "{
    \"S3OutputPath\": \"s3://$BUCKET/labeling/output/\",
    \"KmsKeyId\": \"\"
  }" \
  --role-arn "$ROLE_ARN" \
  --label-category-config-s3-uri "s3://$BUCKET/labeling/label-categories.json" \
  --human-task-config "{
    \"WorkteamArn\": \"$WORKTEAM_ARN\",
    \"UiConfig\": {
      \"UiTemplateS3Uri\": \"s3://labeling-tool-$REGION/templates/groundtruth/1/bounding-box.html\"
    },
    \"PreHumanTaskLambdaArn\": \"$PRE_LAMBDA\",
    \"TaskTitle\": \"Bird Species - Draw Bounding Boxes\",
    \"TaskDescription\": \"Draw a bounding box around each bird in the image and select its species: pigeon, dove, starling, sparrow, blackbird, or crow.\",
    \"NumberOfHumanWorkersPerDataObject\": 1,
    \"TaskTimeLimitInSeconds\": 3600,
    \"TaskAvailabilityLifetimeInSeconds\": 864000,
    \"AnnotationConsolidationConfig\": {
      \"AnnotationConsolidationLambdaArn\": \"$POST_LAMBDA\"
    }
  }" \
  $PROFILE \
  --region $REGION

echo ""
echo "Labeling job '$JOB_NAME' created successfully."
echo ""
echo "Labelers will receive an email invitation to:"
echo "  https://$(echo $WORKTEAM_ARN | cut -d'/' -f3).labeling.$REGION.sagemaker.aws"
echo ""
echo "Monitor job status:"
echo "  aws sagemaker describe-labeling-job --labeling-job-name $JOB_NAME $PROFILE --region $REGION"
echo ""
echo "Save this job name for the retraining trigger:"
echo "  export LABELING_JOB_NAME=$JOB_NAME"
