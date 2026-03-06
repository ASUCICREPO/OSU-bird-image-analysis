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
# Use standard Claude model (not marketplace version)
CLAUDE_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# Use the SAME model name and region from Step 2.6
SAGEMAKER_MODEL_NAME=bird-species-detection-model-i107-fr-1l
SAGEMAKER_REGION=us-west-2
```

**CRITICAL:** 
- Use `anthropic.claude-3-5-sonnet-20241022-v2:0` (standard Bedrock model)
- Do NOT use `global.anthropic.claude-sonnet-4-*` (requires AWS Marketplace subscription)
- Make sure SAGEMAKER_REGION matches where you created the model in Step 2.6!

---

## Step 6: Enable Bedrock Access

**CRITICAL:** This step must be completed BEFORE testing the system, or you'll get AccessDeniedException.

1. Login to AWS Console with your account
2. Go to **Amazon Bedrock** service (search for "Bedrock" in the top search bar)
3. In the left sidebar, click **Model access**
4. Click **"Manage model access"** or **"Modify model access"** button
5. Find **"Claude 3.5 Sonnet v2"** in the Anthropic section
6. Check the box next to **"Claude 3.5 Sonnet v2"**
7. Click **"Save changes"** at the bottom
8. Wait for status to change to **"Access granted"** (usually instant, max 2 minutes)

**Important:** Enable "Claude 3.5 Sonnet v2", NOT "Claude Sonnet 4" (which requires AWS Marketplace subscription).

**Verify access:**
```bash
aws bedrock list-foundation-models --region us-west-2 --profile test-account --query 'modelSummaries[?contains(modelId, `claude-3-5-sonnet`)].modelId'
```

You should see `anthropic.claude-3-5-sonnet-20241022-v2:0` in the output.

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

**IMPORTANT: If you redeploy the sandbox backend:**
```bash
# 1. Redeploy sandbox (creates new amplify_outputs.json)
npx ampx sandbox delete --profile test-account
npx ampx sandbox --profile test-account --outputs-out-dir ./

# 2. Upload SageMaker script to NEW bucket
BUCKET_NAME=$(cat amplify_outputs.json | grep -o '"bucket_name":"[^"]*' | cut -d'"' -f4)
aws s3 cp sagemaker/bird_species_counter_production.py s3://$BUCKET_NAME/scripts/bird_species_counter_production.py --profile test-account

# 3. Rebuild and redeploy frontend (REQUIRED - new backend config)
export FRONTEND_BUCKET=$(cat bucket_name.txt)
npm run build
aws s3 sync dist/ s3://$FRONTEND_BUCKET/ --delete --profile test-account

# Frontend URL stays the same, but now points to new backend!
```

---

## Step 11: Test the System

1. Open your S3 website URL from Step 10
2. Upload a ZIP file with 5-10 bird images
3. Wait for processing (1-2 minutes)
4. Download the results CSV

### Monitor Processing
```bash
# Watch Lambda logs (real-time)
aws logs tail /aws/lambda/amplify-birdprocessingsys-BirdProcessorFunction \
  --follow \
  --profile test-account \
  --region us-west-2

# Check SageMaker notebook status
aws sagemaker describe-notebook-instance \
  --notebook-instance-name bird-species-classifier-notebook-v4 \
  --profile test-account \
  --region us-west-2

# Watch SageMaker notebook logs (if notebook is running)
aws logs tail /aws/sagemaker/NotebookInstances/bird-species-classifier-notebook-v4 \
  --follow \
  --profile test-account \
  --region us-west-2
```

**Quick Debug Scripts:**
```bash
# Debug SageMaker notebook issues
chmod +x debug-sagemaker.sh
./debug-sagemaker.sh --profile test-account

# Verify Bedrock access
chmod +x verify-bedrock-access.sh
./verify-bedrock-access.sh --profile test-account
```

---

## Step 12: Labeling and Model Retraining

This section sets up SageMaker Ground Truth labeling jobs so that labelers can annotate bird images, and the model automatically retrains and improves after each labeling round.

All scripts referenced below are in the `labeling/` folder of this repository.

---

### 12.1: Deploy the Retraining Pipeline (One-Time Setup)

This deploys two Lambda functions and two EventBridge rules that watch for labeling job completion and automatically trigger retraining.

**Find the model bucket name** (the one created in Step 2.3):
```bash
aws s3 ls --profile test-account | grep bird-model
```

**Edit `labeling/setup-retraining-trigger.sh`** — update line 15:
```bash
MODEL_BUCKET="bird-model-ACTUALTIMESTAMP"   # your real model bucket name
# Leave ENDPOINT_NAME="" — the processing script creates serverless endpoints dynamically
```

**Run the setup:**
```bash
cd labeling
chmod +x setup-retraining-trigger.sh
./setup-retraining-trigger.sh
```

This creates:
- `bird-retrain-on-labeling-complete` Lambda — starts a training job when a labeling job finishes
- `bird-update-model-on-training-complete` Lambda — replaces the model with retrained weights
- EventBridge rules wiring them together automatically

---

### 12.2: Create a Private Workforce for Labelers (One-Time Setup)

Labelers need an AWS-hosted portal to do their work. Set this up in the AWS Console:

1. Go to **SageMaker Console** → **Ground Truth** → **Labeling workforces** → **Private**
2. Click **Create private team**
3. Give it a name (e.g., `bird-labelers`)
4. Under **Add workers**, enter the email addresses of your labelers
5. They will receive an email invitation with a link to the labeling portal
6. Copy the **Workteam ARN** shown on the team detail page — you will need it in the next step

---

### 12.3: Create a Labeling Job

Run this whenever you want to start a new round of labeling (e.g., after users have uploaded a fresh batch of images).

**Generate the image manifest** from images already in S3:
```bash
cd labeling
chmod +x create-input-manifest.sh
./create-input-manifest.sh
```

**Edit `labeling/create-labeling-job.sh`** — update line 20 with the workteam ARN from Step 12.2:
```bash
WORKTEAM_ARN="arn:aws:sagemaker:us-west-2:YOUR_ACCOUNT_ID:workteam/private-crowd/bird-labelers"
```

**Create the labeling job:**
```bash
chmod +x create-labeling-job.sh
./create-labeling-job.sh
```

The script prints the labeler portal URL at the end. Share this URL with your labelers.

**Monitor the labeling job:**
```bash
aws sagemaker list-labeling-jobs \
  --profile test-account \
  --region us-west-2 \
  --query 'LabelingJobSummaryList[*].{Name:LabelingJobName,Status:LabelingJobStatus,Labeled:LabelCounters.HumanLabeled}' \
  --output table
```

---

### 12.4: What Happens After Labeling Completes

No manual action needed. The pipeline runs automatically:

1. Labeling job completes → EventBridge triggers `bird-retrain-on-labeling-complete`
2. Lambda starts a SageMaker Training Job using the labeled images (`ml.p3.2xlarge`, ~1 hour)
3. Training completes → EventBridge triggers `bird-update-model-on-training-complete`
4. Lambda deletes the existing model and recreates `bird-species-detection-model-i107-fr-1l` with the new weights
5. Next time a user uploads images, the processing notebook automatically uses the improved model

**Monitor retraining:**
```bash
# Watch training job progress
aws sagemaker list-training-jobs \
  --profile test-account \
  --region us-west-2 \
  --name-contains bird-retrain \
  --query 'TrainingJobSummaries[*].{Name:TrainingJobName,Status:TrainingJobStatus}' \
  --output table

# Watch Lambda logs
aws logs tail /aws/lambda/bird-retrain-on-labeling-complete \
  --follow --profile test-account --region us-west-2

aws logs tail /aws/lambda/bird-update-model-on-training-complete \
  --follow --profile test-account --region us-west-2
```

---

### 12.5: Labeler Instructions

Share these instructions with anyone who will be labeling images.

---

#### How to Upload Images

Images are uploaded through the bird processing app (the S3 website URL from Step 10).

1. Open the app URL in your browser
2. In the **Upload ZIP or Images** panel on the left, click the upload zone or drag files in
3. Supported formats: ZIP files containing images, or individual JPG/PNG files
4. Click **Upload to S3 & Process** — the app uploads your images and processes them automatically
5. Results appear in the **Bucket Contents** panel on the right as a downloadable CSV

---

#### How to Label Images in the Labeling Job

When a labeling job is created, you will receive an **email from AWS** with the subject "You have been invited to work on a labeling project." It contains a link to your labeling portal and login credentials.

**Step 1 — Log in**
Click the link in the email. You will be taken to the AWS Ground Truth Worker Portal. Log in with the credentials in the email (you will be prompted to set a new password on first login).

**Step 2 — Start a task**
On the portal home page, click **Start working** next to the active labeling job titled "Bird Species - Draw Bounding Boxes."

**Step 3 — Draw bounding boxes**
For each image:
1. Look at the image carefully — there may be one or more birds
2. Select the species from the **Label** dropdown on the left: `pigeon`, `dove`, `starling`, `sparrow`, `blackbird`, or `crow`
3. Click and drag on the image to draw a box tightly around the bird
4. Repeat for every bird visible in the image — each bird gets its own box with its own species label
5. If you are unsure of the species, use your best judgment or skip the image using the **Can't complete** option

**Step 4 — Submit**
Click **Submit** when you are done with each image. The portal automatically loads the next one.

**Tips:**
- Draw boxes as tight as possible around each bird, not around the whole image
- If a bird is partially cut off at the edge, still draw a box around the visible portion
- One image can have multiple boxes if multiple birds are present
- If there are no birds in the image, click **Can't complete** and select "No birds visible"

---

## Step 13 (Optional): Add Custom Domain with HTTPS


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

## Step 14 (Optional): Test Locally Before Deploying

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

### Issue: AccessDeniedException when calling Bedrock
**Symptom:** `AccessDeniedException: Could not access the model` or `Model access is denied due to IAM user or service role is not authorized`

**Root Cause:** Either model access not enabled OR using marketplace model that requires subscription.

**Solution:**
1. **Update .env to use standard Bedrock model:**
   ```bash
   CLAUDE_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
   ```
   Do NOT use: `global.anthropic.claude-sonnet-4-*` (requires AWS Marketplace)

2. **Enable Bedrock model access** (Step 6 is REQUIRED):
   - Go to AWS Console → Bedrock → Model access
   - Click "Manage model access"
   - Enable "Claude 3.5 Sonnet v2" (NOT Claude Sonnet 4)
   - Wait for "Access granted" status

3. **Redeploy backend with updated .env:**
   ```bash
   npx ampx sandbox delete --profile test-account
   npx ampx sandbox --profile test-account --outputs-out-dir ./
   ```

4. **Verify model access:**
   ```bash
   aws bedrock list-foundation-models --region us-west-2 --profile test-account --query 'modelSummaries[?contains(modelId, `claude-3-5-sonnet`)].modelId'
   ```

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

### Issue: SageMaker Endpoint Creation Failed
**Symptom:** Logs show "Waiter EndpointInService failed" or "EndpointStatus: Failed"

**Root Cause:** Model configuration issue, IAM permissions, or resource unavailability.

**Debug Steps:**

1. **Check if model exists:**
   ```bash
   aws sagemaker describe-model \
     --model-name bird-species-detection-model-i107-fr-1l \
     --profile test-account \
     --region us-west-2
   ```
   
   If model doesn't exist, go back to Step 2.6 and create it.

2. **Verify model configuration:**
   ```bash
   aws sagemaker describe-model \
     --model-name bird-species-detection-model-i107-fr-1l \
     --profile test-account \
     --region us-west-2 \
     --query '{Image:PrimaryContainer.Image,ModelData:PrimaryContainer.ModelDataUrl,Role:ExecutionRoleArn}'
   ```
   
   Check:
   - Image URL is valid ECR image
   - ModelDataUrl points to existing S3 object (model.tar.gz)
   - Role ARN exists and has permissions

3. **Test model data accessibility:**
   ```bash
   # Extract S3 path from model
   MODEL_DATA=$(aws sagemaker describe-model \
     --model-name bird-species-detection-model-i107-fr-1l \
     --profile test-account \
     --region us-west-2 \
     --query 'PrimaryContainer.ModelDataUrl' \
     --output text)
   
   # Check if file exists
   aws s3 ls $MODEL_DATA --profile test-account
   ```

4. **Check CloudWatch logs for endpoint failure reason:**
   ```bash
   aws logs tail /aws/sagemaker/Endpoints/bird-endpoint-TIMESTAMP \
     --profile test-account \
     --region us-west-2 \
     --since 1h
   ```

5. **Verify IAM role has S3 access:**
   ```bash
   # Get role ARN
   ROLE_ARN=$(aws sagemaker describe-model \
     --model-name bird-species-detection-model-i107-fr-1l \
     --profile test-account \
     --region us-west-2 \
     --query 'ExecutionRoleArn' \
     --output text)
   
   # Check role policies
   aws iam list-attached-role-policies \
     --role-name $(echo $ROLE_ARN | cut -d'/' -f2) \
     --profile test-account
   ```

**Common Issues:**

1. **Model doesn't exist in us-west-2:**
   - Solution: Create model in Step 2.6 with `--region us-west-2`

2. **Model data (model.tar.gz) not found in S3:**
   - Solution: Re-upload model to S3 (Step 2.3)
   - Verify: `aws s3 ls s3://bird-model-TIMESTAMP/models/`

3. **Wrong container image:**
   - Solution: Use correct image for us-west-2:
   - Object detection: `433757028032.dkr.ecr.us-west-2.amazonaws.com/object-detection:1`
   - PyTorch: `763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-inference:2.0-cpu-py310`

4. **IAM role missing S3 permissions:**
   - Solution: Add S3 read policy to SageMakerExecutionRole
   ```bash
   aws iam attach-role-policy \
     --role-name SageMakerExecutionRole \
     --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess \
     --profile test-account
   ```

5. **Instance type not available:**
   - Default: `ml.m5.xlarge` (used by Python script)
   - Solution: Edit `sagemaker/bird_species_counter_production.py`
   - Change instance type to `ml.t2.medium` or `ml.m4.xlarge`

6. **Service quotas exceeded:**
   ```bash
   aws service-quotas get-service-quota \
     --service-code sagemaker \
     --quota-code L-93F07B8C \
     --profile test-account \
     --region us-west-2
   ```

**Quick Fix - Recreate Model:**
```bash
# Delete old model
aws sagemaker delete-model \
  --model-name bird-species-detection-model-i107-fr-1l \
  --profile test-account \
  --region us-west-2

# Recreate with correct configuration (Step 2.6)
export MODEL_BUCKET=bird-model-TIMESTAMP
export CONTAINER_IMAGE="433757028032.dkr.ecr.us-west-2.amazonaws.com/object-detection:1"
export ROLE_ARN=$(aws iam get-role --role-name SageMakerExecutionRole --query 'Role.Arn' --output text --profile test-account)

aws sagemaker create-model \
  --model-name bird-species-detection-model-i107-fr-1l \
  --primary-container Image=$CONTAINER_IMAGE,ModelDataUrl=s3://$MODEL_BUCKET/models/bird-species-model.tar.gz \
  --execution-role-arn $ROLE_ARN \
  --profile test-account \
  --region us-west-2
```

### Issue: SageMaker Model Not Found
**Symptom:** `ModelNotFoundException`

**Solution:**
1. Verify model was created: `aws sagemaker describe-model --model-name bird-species-detection-model-i107-fr-1l --profile test-account`
2. Check SAGEMAKER_MODEL_NAME in .env matches deployed model
3. Verify model is in correct region (us-west-2)

### Issue: SageMaker Notebook Creation Timeout During Deployment
**Symptom:** `npx ampx sandbox` fails with "Resource creation took longer than 5 minutes" or CloudFormation timeout

**This is a CloudFormation deployment issue, not a runtime issue.**

**Find Logs:**

1. **Check CloudFormation stack events:**
   ```bash
   # List all stacks
   aws cloudformation list-stacks \
     --profile test-account \
     --region us-west-2 \
     --query 'StackSummaries[?contains(StackName, `SageMaker`) || contains(StackName, `amplify`)].{Name:StackName,Status:StackStatus}' \
     --output table
   
   # Get detailed events for specific stack
   aws cloudformation describe-stack-events \
     --stack-name amplify-birdprocessingsys-YOURSTACK-SageMakerStack \
     --profile test-account \
     --region us-west-2 \
     --query 'StackEvents[?contains(ResourceType, `SageMaker`)]' \
     --output table
   ```

2. **Check if notebook was actually created despite timeout:**
   ```bash
   aws sagemaker list-notebook-instances \
     --profile test-account \
     --region us-west-2
   ```

3. **Check notebook status if it exists:**
   ```bash
   aws sagemaker describe-notebook-instance \
     --notebook-instance-name bird-species-classifier-notebook-v4 \
     --profile test-account \
     --region us-west-2 \
     --query '{Status:NotebookInstanceStatus,FailureReason:FailureReason}'
   ```

4. **View CloudFormation logs in AWS Console:**
   - Go to CloudFormation console
   - Find stack: `amplify-birdprocessingsys-*-SageMakerStack`
   - Click "Events" tab
   - Look for CREATE_FAILED or timeout messages

**Common Causes:**

1. **Service Quotas:** SageMaker notebook instance limit reached
   ```bash
   aws service-quotas get-service-quota \
     --service-code sagemaker \
     --quota-code L-7C4B8E3F \
     --profile test-account \
     --region us-west-2
   ```

2. **Instance Type Unavailable:** `ml.t3.medium` not available in region
   - Solution: Edit `amplify/custom/sagemaker-notebook.ts`
   - Change `instanceType: 'ml.t3.medium'` to `'ml.t2.medium'`
   - Redeploy

3. **IAM Role Creation Delay:** Role not ready when notebook tries to use it
   - This usually resolves on retry

4. **VPC/Subnet Issues:** If using custom VPC configuration

**Solutions:**

**Option 1: Retry deployment (often works):**
```bash
npx ampx sandbox delete --profile test-account
npx ampx sandbox --profile test-account --outputs-out-dir ./
```

**Option 2: Check if notebook exists and continue:**
```bash
# If notebook was created despite timeout
aws sagemaker describe-notebook-instance \
  --notebook-instance-name bird-species-classifier-notebook-v4 \
  --profile test-account \
  --region us-west-2

# If status is "InService", you can continue with Step 9
```

**Option 3: Change instance type:**
```bash
# Edit amplify/custom/sagemaker-notebook.ts
# Line ~155: instanceType: 'ml.t2.medium'  // or ml.t3.small
# Then redeploy
```

**Option 4: Deploy without SageMaker (bird counting only):**
```bash
# Comment out SageMaker creation in amplify/backend.ts
# Lines ~115-118:
# const sagemakerResources = createSageMakerNotebook(
#   backend.createStack('SageMakerStack'),
#   backend.storage.resources.bucket
# );

# Redeploy - system will work for bird counting (no species classification)
```

### Issue: SageMaker Notebook "couldn't locate runnable browser" Error
**Symptom:** CloudWatch logs show "couldn't locate runnable browser" error

**Root Cause:** Jupyter Notebook trying to open a browser in headless environment.

**Solution:** **This is a harmless warning - IGNORE IT.**

The notebook doesn't need a browser to function. The lifecycle script runs Python scripts directly, not through Jupyter UI.

**Verify notebook is working:**
```bash
# Check if notebook is running
aws sagemaker describe-notebook-instance \
  --notebook-instance-name bird-species-classifier-notebook-v4 \
  --profile test-account \
  --region us-west-2 \
  --query 'NotebookInstanceStatus'

# Should return: "InService" or "Pending"
```

**The notebook will still process images correctly despite this warning.**

### Issue: SageMaker Notebook Start Failed
**Symptom:** Notebook fails to start or Lambda can't trigger notebook

**Debug Steps:**

1. **Find the notebook instance name:**
   ```bash
   aws sagemaker list-notebook-instances --profile test-account --region us-west-2
   ```

2. **Check notebook status:**
   ```bash
   aws sagemaker describe-notebook-instance \
     --notebook-instance-name YOUR_NOTEBOOK_NAME \
     --profile test-account \
     --region us-west-2
   ```
   Look for `NotebookInstanceStatus` field (should be: InService, Pending, Stopped, Failed)

3. **Check CloudWatch logs for notebook:**
   ```bash
   # List log streams
   aws logs describe-log-streams \
     --log-group-name /aws/sagemaker/NotebookInstances \
     --profile test-account \
     --region us-west-2
   
   # View specific log stream
   aws logs tail /aws/sagemaker/NotebookInstances/YOUR_NOTEBOOK_NAME \
     --follow \
     --profile test-account \
     --region us-west-2
   ```

4. **Check Lambda logs for SageMaker errors:**
   ```bash
   aws logs tail /aws/lambda/amplify-birdprocessingsys-BirdProcessorFunction \
     --follow \
     --profile test-account \
     --region us-west-2 \
     --filter-pattern "sagemaker"
   ```

5. **Common issues:**
   - **Notebook doesn't exist:** Check if it was created during sandbox deployment
   - **IAM role issues:** Lambda needs `sagemaker:StartNotebookInstance` permission
   - **Region mismatch:** Notebook must be in same region as Lambda (us-west-2)
   - **Instance type unavailable:** Try different instance type in custom/sagemaker-notebook.ts

6. **Manually start notebook:**
   ```bash
   aws sagemaker start-notebook-instance \
     --notebook-instance-name YOUR_NOTEBOOK_NAME \
     --profile test-account \
     --region us-west-2
   ```

7. **Check if script exists in S3:**
   ```bash
   BUCKET_NAME=$(cat amplify_outputs.json | grep -o '"bucket_name":"[^"]*' | cut -d'"' -f4)
   aws s3 ls s3://$BUCKET_NAME/scripts/ --profile test-account
   ```
   Should show: `bird_species_counter_production.py`

8. **View notebook execution logs:**
   ```bash
   # Check if notebook created any output
   aws s3 ls s3://$BUCKET_NAME/results/ --profile test-account
   ```

**If notebook still fails, check:**
- AWS Service Quotas for SageMaker notebook instances
- VPC/subnet configuration (if using custom VPC)
- SageMaker service availability in us-west-2

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
