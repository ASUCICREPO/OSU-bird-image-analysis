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
# IMPORTANT: Create model in the SAME region as your deployment (us-west-2)
aws sagemaker create-model \
  --model-name bird-species-detection-model-i107-fr-1l \
  --primary-container Image=$CONTAINER_IMAGE,ModelDataUrl=s3://$MODEL_BUCKET/models/bird-species-model.tar.gz \
  --execution-role-arn $ROLE_ARN \
  --profile test-account \
  --region us-west-2

# Verify model was created
aws sagemaker describe-model \
  --model-name bird-species-detection-model-i107-fr-1l \
  --profile test-account \
  --region us-west-2
```

**Note:** The model name and region will be used in Step 5 (.env configuration).

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

Edit `.env` file with YOUR model details from Step 2.6:
```bash
BEDROCK_REGION=us-west-2
CLAUDE_MODEL_ID=global.anthropic.claude-sonnet-4-20250514-v1:0

# Use the SAME model name and region from Step 2.6
SAGEMAKER_MODEL_NAME=bird-species-detection-model-i107-fr-1l
SAGEMAKER_REGION=us-west-2
```

**CRITICAL:** Make sure SAGEMAKER_REGION matches where you created the model in Step 2.6!

---

## Step 6: Enable Bedrock Access

1. Login to AWS Console (your new account)
2. Go to **Bedrock** → **Model access**
3. Click **"Manage model access"**
4. Enable **"Claude Sonnet 4"**
5. Click **"Save changes"**
6. Wait for approval (usually instant)

---

## Step 7: Deploy Backend to Cloud

```bash
npx ampx sandbox --profile test-account --outputs-out-dir ./
```

**What happens:**
- Creates S3 bucket for storage
- Deploys Lambda function for image processing
- Creates SageMaker notebook instance
- Configures all IAM roles and permissions

**Deployment time:** 5-10 minutes

**Important:** Keep this terminal open or run `npx ampx sandbox --once` to deploy and exit.

---

## Step 8: Commit amplify_outputs.json

```bash
# Add amplify_outputs.json to git for version control
git add amplify_outputs.json
git commit -m "Add amplify outputs"
git push origin main
```

---

## Step 9: Upload SageMaker Script

```bash
# Get bucket name from deployment output
BUCKET_NAME=$(cat amplify_outputs.json | grep -o '"bucket_name":"[^"]*' | cut -d'"' -f4)

# Upload processing script
aws s3 cp sagemaker/bird_species_counter_production.py s3://$BUCKET_NAME/scripts/bird_species_counter_production.py --profile test-account
```

---

## Step 10: Deploy Frontend to S3 (Public URL)

### 10.1: Login to AWS SSO (if using SSO profile)
```bash
aws sso login --profile test-account
```

### 10.2: Build the Frontend
```bash
npm run build
```

This creates a `dist/` folder with your production-ready frontend.

### 10.3: Create S3 Bucket for Website Hosting
```bash
# Create bucket with unique name
export BUCKET_NAME="bird-app-$(date +%s)"
aws s3 mb s3://$BUCKET_NAME --region us-west-2 --profile test-account

# Save bucket name for later use
echo $BUCKET_NAME > bucket_name.txt
```

### 10.4: Enable Static Website Hosting
```bash
aws s3 website s3://$BUCKET_NAME \
  --index-document index.html \
  --error-document index.html \
  --profile test-account
```

### 10.5: Remove Public Access Block
```bash
aws s3api put-public-access-block \
  --bucket $BUCKET_NAME \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" \
  --profile test-account
```

### 10.6: Make Bucket Public
```bash
aws s3api put-bucket-policy \
  --bucket $BUCKET_NAME \
  --policy "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Sid\": \"PublicReadGetObject\",
      \"Effect\": \"Allow\",
      \"Principal\": \"*\",
      \"Action\": \"s3:GetObject\",
      \"Resource\": \"arn:aws:s3:::$BUCKET_NAME/*\"
    }]
  }" \
  --profile test-account
```

### 10.7: Upload Frontend Files
```bash
aws s3 sync dist/ s3://$BUCKET_NAME/ --profile test-account
```

### 10.8: Get Your Public URL
```bash
echo "Your app is live at: http://$BUCKET_NAME.s3-website-us-west-2.amazonaws.com"
```

**Your public URL format:**
```
http://bird-app-TIMESTAMP.s3-website-us-west-2.amazonaws.com
```

**To update the frontend later:**
```bash
export BUCKET_NAME=$(cat bucket_name.txt)
npm run build
aws s3 sync dist/ s3://$BUCKET_NAME/ --delete --profile test-account
```

---

## Step 11: Test the System

1. Open your S3 website URL from Step 10
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

## Step 12 (Optional): Add Custom Domain with HTTPS

If you want HTTPS and a custom domain:

### Using CloudFront
```bash
# Create CloudFront distribution pointing to your S3 bucket
aws cloudfront create-distribution \
  --origin-domain-name $BUCKET_NAME.s3-website-us-west-2.amazonaws.com \
  --default-root-object index.html \
  --profile test-account
```

Then configure your domain's DNS to point to the CloudFront URL.

**Note:** The S3 website URL (HTTP) works perfectly for testing and internal use.

---

## Step 13 (Optional): Test Locally Before Deploying

If you want to test locally first:

```bash
npm run dev
```

Open http://localhost:5173 in your browser, then proceed to Step 10 when ready.

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

### Issue: AWS SSO Token Expired
**Symptom:** `Error when retrieving token from sso: Token has expired`

**Solution:**
```bash
aws sso login --profile test-account
```

### Issue: S3 Website URL Not Accessible
**Symptom:** 403 Forbidden or Access Denied

**Solution:**
1. Verify public access block is disabled:
   ```bash
   aws s3api get-public-access-block --bucket $BUCKET_NAME --profile test-account
   ```
2. Verify bucket policy is public:
   ```bash
   aws s3api get-bucket-policy --bucket $BUCKET_NAME --profile test-account
   ```
3. Verify website hosting is enabled:
   ```bash
   aws s3api get-bucket-website --bucket $BUCKET_NAME --profile test-account
   ```
4. Verify files were uploaded:
   ```bash
   aws s3 ls s3://$BUCKET_NAME/ --profile test-account
   ```

### Issue: Cannot Set Public Bucket Policy
**Symptom:** `AccessDenied: public policies are prevented by BlockPublicPolicy`

**Solution:**
Run Step 10.5 to remove public access block before setting the bucket policy.

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
- S3 Website Hosting: $0.00 (negligible)
- **Total**: ~$0.20 - $0.70 per 100 images

**Monthly costs (1000 images/month):**
- ~$2 - $7/month

---

## Cleanup

To delete all resources:

```bash
# 1. Delete sandbox backend
npx ampx sandbox delete --profile test-account

# 2. Delete frontend S3 bucket
export BUCKET_NAME=$(cat bucket_name.txt)
aws s3 rm s3://$BUCKET_NAME --recursive --profile test-account
aws s3 rb s3://$BUCKET_NAME --profile test-account

# 3. Delete storage S3 bucket (from amplify_outputs.json)
STORAGE_BUCKET=$(cat amplify_outputs.json | grep -o '"bucket_name":"[^"]*' | cut -d'"' -f4)
aws s3 rm s3://$STORAGE_BUCKET --recursive --profile test-account
aws s3 rb s3://$STORAGE_BUCKET --profile test-account

# 4. Delete SageMaker model
aws sagemaker delete-model --model-name bird-species-detection-model-i107-fr-1l --profile test-account --region us-west-2

# 5. Delete IAM role
aws iam detach-role-policy --role-name SageMakerExecutionRole --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess --profile test-account
aws iam delete-role --role-name SageMakerExecutionRole --profile test-account
```

---

## Architecture Summary

**Backend (Sandbox):**
- Lambda function (bird processing)
- S3 bucket (storage)
- SageMaker notebook (species classification)
- Cognito (authentication)

**Frontend (Amplify Hosting):**
- React app hosted on CloudFront CDN
- Public URL: `https://main.xxxxx.amplifyapp.com`
- Connects to sandbox backend via `amplify_outputs.json`

**Why this approach?**
- Backend via sandbox: Easy local development and testing
- Frontend via Amplify Hosting: Public URL for client access
- Best of both worlds: Development flexibility + Production accessibility

---

## Support & Documentation

- **AWS Amplify Docs**: https://docs.amplify.aws/
- **Bedrock Docs**: https://docs.aws.amazon.com/bedrock/
- **SageMaker Docs**: https://docs.aws.amazon.com/sagemaker/
- **GitHub Issues**: https://github.com/ASUCICREPO/OSU-bird-image-analysis/issues

---

**Deployment Complete!** 🎉

Your bird processing system is now fully deployed in AWS cloud with a public URL.
