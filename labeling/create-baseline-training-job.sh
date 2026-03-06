#!/bin/bash
# Creates a baseline training job in the customer's AWS account using the existing
# model.tar.gz and the exact hyperparameters your seniors used.
#
# Purpose:
#   - Establishes a clean training job record in their account
#   - setup-retraining-trigger.sh can then reference this job via ORIGINAL_TRAINING_JOB_NAME
#   - All future retrains will copy hyperparameters from this baseline job
#
# Prerequisites:
#   1. Fill in the HYPERPARAMETERS section below (get from your seniors)
#   2. Have at least a small labeled dataset in S3 (Ground Truth output manifest, or
#      an existing augmented manifest). SageMaker requires training data even for fine-tuning.
#
# To get hyperparameters from your seniors' account:
#   aws sagemaker describe-training-job \
#     --training-job-name SENIORS_JOB_NAME \
#     --query 'HyperParameters' \
#     --output json

set -e

PROFILE="--profile test-account"
REGION="us-west-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text $PROFILE)
MODEL_BUCKET="bird-model-TIMESTAMP"          # <-- same bucket from DEPLOYMENT.md Step 2.3
MODEL_S3_KEY="models/bird-species-model.tar.gz"
ROLE_ARN=$(aws iam get-role --role-name SageMakerExecutionRole --query 'Role.Arn' --output text $PROFILE)
JOB_NAME="bird-species-baseline-$(date +%s)"
OUTPUT_PATH="s3://$MODEL_BUCKET/baseline-training-output/"

# The S3 URI of your labeled training data (augmented manifest from Ground Truth, or
# an existing manifest your seniors used). Must contain bounding box annotations.
TRAINING_DATA_S3_URI="s3://$MODEL_BUCKET/labeling/output/YOUR_LABELING_JOB/manifests/output/output.manifest"

# ---------------------------------------------------------------
# HYPERPARAMETERS — fill these in from your seniors.
# Run this in their account to get the values:
#   aws sagemaker describe-training-job --training-job-name JOB --query HyperParameters
# ---------------------------------------------------------------
NUM_CLASSES="6"
NUM_TRAINING_SAMPLES=""    # <-- fill in (number of labeled images seniors used)
EPOCHS=""                  # <-- fill in
LEARNING_RATE=""           # <-- fill in
MINI_BATCH_SIZE=""         # <-- fill in
BASE_NETWORK=""            # <-- fill in (e.g. resnet-50, vgg-16)
IMAGE_SHAPE=""             # <-- fill in (e.g. 300, 512)
LABEL_WIDTH=""             # <-- fill in (e.g. 350)
# Add any other hyperparameters your seniors used below

if [ -z "$NUM_TRAINING_SAMPLES" ] || [ -z "$EPOCHS" ] || [ -z "$LEARNING_RATE" ]; then
  echo "ERROR: Fill in the HYPERPARAMETERS section before running this script."
  echo "Ask your seniors to run:"
  echo "  aws sagemaker describe-training-job --training-job-name THEIR_JOB --query HyperParameters --output json"
  exit 1
fi

if [[ "$TRAINING_DATA_S3_URI" == *"YOUR_LABELING_JOB"* ]]; then
  echo "ERROR: Set TRAINING_DATA_S3_URI to your labeled data manifest path."
  exit 1
fi

echo "Creating baseline training job: $JOB_NAME"
echo "Model input:    s3://$MODEL_BUCKET/$MODEL_S3_KEY"
echo "Training data:  $TRAINING_DATA_S3_URI"
echo "Output:         $OUTPUT_PATH"
echo ""

aws sagemaker create-training-job \
  --training-job-name "$JOB_NAME" \
  --algorithm-specification '{
    "TrainingImage": "433757028032.dkr.ecr.'$REGION'.amazonaws.com/object-detection:1",
    "TrainingInputMode": "Pipe"
  }' \
  --role-arn "$ROLE_ARN" \
  --input-data-config '[
    {
      "ChannelName": "train",
      "DataSource": {
        "S3DataSource": {
          "S3DataType": "AugmentedManifestFile",
          "S3Uri": "'"$TRAINING_DATA_S3_URI"'",
          "S3DataDistributionType": "FullyReplicated",
          "AttributeNames": ["source-ref", "bird-species"]
        }
      },
      "ContentType": "application/x-recordio",
      "CompressionType": "None"
    },
    {
      "ChannelName": "model",
      "DataSource": {
        "S3DataSource": {
          "S3DataType": "S3Prefix",
          "S3Uri": "s3://'"$MODEL_BUCKET"'/'"$MODEL_S3_KEY"'",
          "S3DataDistributionType": "FullyReplicated"
        }
      },
      "ContentType": "application/x-sagemaker-model",
      "CompressionType": "None"
    }
  ]' \
  --output-data-config "{\"S3OutputPath\": \"$OUTPUT_PATH\"}" \
  --resource-config '{
    "InstanceType": "ml.m5.xlarge",
    "InstanceCount": 1,
    "VolumeSizeInGB": 50
  }' \
  --stopping-condition '{"MaxRuntimeInSeconds": 3600}' \
  --hyper-parameters '{
    "num_classes": "'"$NUM_CLASSES"'",
    "num_training_samples": "'"$NUM_TRAINING_SAMPLES"'",
    "epochs": "'"$EPOCHS"'",
    "learning_rate": "'"$LEARNING_RATE"'",
    "mini_batch_size": "'"$MINI_BATCH_SIZE"'",
    "base_network": "'"$BASE_NETWORK"'",
    "image_shape": "'"$IMAGE_SHAPE"'",
    "label_width": "'"$LABEL_WIDTH"'",
    "use_pretrained_model": "1"
  }' \
  --tags '[
    {"Key": "Project", "Value": "bird-species-detection"},
    {"Key": "Type", "Value": "baseline"}
  ]' \
  $PROFILE --region $REGION

echo ""
echo "Baseline training job '$JOB_NAME' started."
echo "This takes ~15-30 minutes. Monitor it:"
echo "  aws sagemaker describe-training-job --training-job-name $JOB_NAME $PROFILE --region $REGION --query TrainingJobStatus"
echo ""
echo "Once it completes, set this in setup-retraining-trigger.sh:"
echo "  ORIGINAL_TRAINING_JOB_NAME=$JOB_NAME"
