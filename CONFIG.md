# Configuration Guide

## Environment Variables

This project uses environment variables for configuration to avoid hardcoding sensitive values.

### Required Configuration

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Configure AWS Bedrock (Required):**
   ```bash
   BEDROCK_REGION=us-west-2
   CLAUDE_MODEL_ID=global.anthropic.claude-sonnet-4-20250514-v1:0
   ```

### Optional Configuration

3. **If using custom ECR image for SageMaker:**
   ```bash
   CONTAINER_IMAGE=YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/object-detection:1
   ```

4. **If using external model bucket:**
   ```bash
   MODEL_BUCKET_NAME=your-model-bucket
   ```

5. **If using external ECR repository:**
   ```bash
   ECR_REPO_ARN=arn:aws:ecr:REGION:ACCOUNT:repository/your-repo
   ```

## Deployment

### Local Testing
```bash
npm install
npx ampx sandbox
```

### Production Deployment
```bash
npx ampx pipeline-deploy --branch main
```

## Notes

- Never commit `.env` files to git
- Each deployment environment should have its own configuration
- The `.env.example` file shows all available options
