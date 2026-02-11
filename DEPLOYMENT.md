# Deployment Guide - Bird Processing System v2

Complete step-by-step guide to deploy this system in a new AWS account with full cloud hosting.

---

## Prerequisites

- AWS Account with admin access
- AWS CLI installed and configured
- Node.js 18+ installed
- Git installed
- SageMaker model in ZIP format

---

## Step 1: Configure AWS CLI

```bash
aws configure --profile test-account
```

Enter:
- AWS Access Key ID: `<your-key>`
- AWS Secret Access Key: `<your-secret>`
- Default region: `us-west-2`
- Default output format: `json`

Verify:
```bash
aws sts get-caller-identity --profile test-account
```

---

## Step 2: Prepare and Upload SageMaker Model

### 2.1: Extract Model Files
```bash
# Unzip your model
unzip your-model.zip -d model-files/
cd model-files/
```

### 2.2: Create model.tar.gz (SageMaker format)
```bash
# SageMaker requires .tar.gz format
tar -czf model.tar.gz *
cd ..
```

### 2.3: Upload Model to S3
```bash
# Create S3 bucket for model
aws s3 mb s3://bird-model-$(date +%s) --profile test-account --region us-west-2

# Upload model (replace TIMESTAMP with your bucket name)
aws s3 cp model-files/model.tar.gz s3://bird-model-TIMESTAMP/models/bird-species-model.tar.gz --profile test-account --region us-west-2

# Save bucket name for later
export MODEL_BUCKET=bird-model-TIMESTAMP
```

### 2.4: Get SageMaker Container Image (This is the container image specifically for us-west-2 region)
```bash
# For object detection models, use AWS pre-built container
# Replace with your model's framework (pytorch, tensorflow, etc.)
export CONTAINER_IMAGE="433757028032.dkr.ecr.us-west-2.amazonaws.com/object-detection:1"
```

### 2.5: Create SageMaker Execution Role
```bash
# Create role
aws iam create-role \
  --role-name SageMakerExecutionRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "sagemaker.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' \
  --profile test-account

# Attach policies
aws iam attach-role-policy \
  --role-name SageMakerExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess \
  --profile test-account

# Get role ARN
export ROLE_ARN=$(aws iam get-role --role-name SageMakerExecutionRole --query 'Role.Arn' --output text --profile test-account)
```

### 2.6: Create SageMaker Model
```bash
aws sagemaker create-model \
  --model-name bird-species-detection-model-i107-fr-1l \
  --primary-container Image=$CONTAINER_IMAGE,ModelDataUrl=s3://$MODEL_BUCKET/models/bird-species-model.tar.gz \
  --execution-role-arn $ROLE_ARN \
  --profile test-account \
  --region us-west-2
```

---

## Step 3: Clone Repository

```bash
git clone https://github.com/ASUCICREPO/OSU-bird-image-analysis.git
cd OSU-bird-image-analysis
```

---

## Step 4: Install Dependencies

```bash
npm install
cd amplify && npm install && cd ..
```

---

## Step 5: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` file:
```bash
BEDROCK_REGION=us-west-2
CLAUDE_MODEL_ID=global.anthropic.claude-sonnet-4-20250514-v1:0
SAGEMAKER_MODEL_NAME=bird-species-detection-model-i107-fr-1l
SAGEMAKER_REGION=us-west-2
```

---

## Step 6: Enable Bedrock Access

1. Login to AWS Console (your new account)
2. Go to **Bedrock** → **Model access**
3. Click **"Manage model access"**
4. Enable **"Claude Sonnet 4"**
5. Click **"Save changes"**
6. Wait for approval (usually instant)

---

## Step 7: Deploy Everything to Cloud

```bash
npx ampx sandbox --profile test-account --outputs-out-dir ./
```

**What happens:**
- Creates S3 bucket for storage
- Deploys Lambda function for image processing
- Creates SageMaker notebook instance
- Deploys frontend to Amplify Hosting
- Configures all IAM roles and permissions

**Deployment time:** 5-10 minutes

**Output:** You'll get a **public URL** at the end (e.g., `https://xxxxx.amplifyapp.com`)

---

## Step 8: Upload SageMaker Script

```bash
# Get bucket name from deployment output
BUCKET_NAME=$(cat amplify_outputs.json | grep -o '"bucket_name":"[^"]*' | cut -d'"' -f4)

# Upload processing script
aws s3 cp sagemaker/bird_species_counter_production.py s3://$BUCKET_NAME/scripts/bird_species_counter_production.py --profile test-account
```

---

## Step 9: Test the System

1. Open the public URL from Step 7
2. Upload a ZIP file with 5-10 bird images
3. Wait for processing (1-2 minutes)
4. Download the results CSV

### Monitor Processing
```bash
# Watch Lambda logs
aws logs tail /aws/lambda/amplify-birdprocessingsys-BirdProcessorFunction --follow --profile test-account

# Check SageMaker notebook status
aws sagemaker describe-notebook-instance --notebook-instance-name bird-species-classifier-notebook-v4 --profile test-account
```

---

## Important Limitations

### Lambda Timeout
- **Max timeout**: 15 minutes
- **Safe limit**: ~300-400 images per ZIP
- **For larger batches**: Split into multiple ZIPs

### Bedrock Quotas
- **Default**: Very low (may throttle after 50-100 images)
- **Recommended**: Request quota increase to 50,000+ tokens/minute
- **How to request**: AWS Console → Service Quotas → Amazon Bedrock

### SageMaker Costs
- **Notebook instance**: Runs only during processing, auto-stops
- **Endpoint**: Created on-demand, deleted after use
- **Estimated cost**: $0.05-0.10 per processing run

---

## Troubleshooting

### Issue: Bedrock Throttling Errors
**Symptom:** `ThrottlingException: Too many tokens`

**Solution:**
1. Request quota increase (AWS Console → Service Quotas → Amazon Bedrock)
2. Process smaller batches (50-100 images)
3. Wait 24 hours for quota to reset

### Issue: Lambda Timeout
**Symptom:** Lambda times out after 15 minutes

**Solution:**
1. Process smaller batches (max 300-400 images)
2. Split large ZIPs into smaller ones

### Issue: SageMaker Model Not Found
**Symptom:** `ModelNotFoundException`

**Solution:**
1. Verify model was created: `aws sagemaker describe-model --model-name bird-species-detection-model-i107-fr-1l --profile test-account`
2. Check SAGEMAKER_MODEL_NAME in .env matches deployed model
3. Verify model is in correct region (us-west-2)

### Issue: No Enhanced CSV Created
**Symptom:** Only basic CSV, no species classification

**Solution:**
1. Check SageMaker notebook logs in CloudWatch
2. Verify script was uploaded to S3 (Step 8)
3. Manually start notebook if it's stopped

---

## Cost Estimation

**Per 100 images processed:**
- Lambda: $0.01 - $0.05
- Bedrock (Claude): $0.10 - $0.50
- SageMaker: $0.05 - $0.10
- S3 Storage: $0.01
- Amplify Hosting: $0.01
- **Total**: ~$0.20 - $0.70 per 100 images

**Monthly costs (1000 images/month):**
- ~$2 - $7/month

---

## Cleanup

To delete all resources:

```bash
# Delete Amplify app
npx ampx sandbox delete --profile test-account

# Delete S3 buckets
aws s3 rm s3://YOUR-BUCKET-NAME --recursive --profile test-account
aws s3 rb s3://YOUR-BUCKET-NAME --profile test-account

# Delete SageMaker model
aws sagemaker delete-model --model-name bird-species-detection-model-i107-fr-1l --profile test-account

# Delete IAM role
aws iam detach-role-policy --role-name SageMakerExecutionRole --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess --profile test-account
aws iam delete-role --role-name SageMakerExecutionRole --profile test-account
```

---

## Support & Documentation

- **AWS Amplify Docs**: https://docs.amplify.aws/
- **Bedrock Docs**: https://docs.aws.amazon.com/bedrock/
- **SageMaker Docs**: https://docs.aws.amazon.com/sagemaker/
- **GitHub Issues**: https://github.com/ASUCICREPO/OSU-bird-image-analysis/issues

---

**Deployment Complete!** 🎉

Your bird processing system is now fully deployed in AWS cloud with a public URL.
