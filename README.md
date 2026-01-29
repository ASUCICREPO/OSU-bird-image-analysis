# Bird Processing System v2

A client-ready bird counting and species classification system built with AWS Amplify.

## Project Overview

This system allows users to upload bird images and receive automated counting and species classification results.

## Development Iterations

### Iteration 1: Basic Setup & Authentication ✅
- Project scaffolding
- AWS Amplify configuration
- Clean React UI without authentication
- Professional interface design

### Iteration 2: File Upload & Storage ✅
- S3 bucket configuration with guest access
- Real S3 file upload with progress tracking
- Support for ZIP files and images
- File validation and error handling

### Iteration 3: Bird Counting with AI 📋
- Lambda function for image processing
- Claude AI integration for bird counting
- CSV result generation

### Iteration 4: Species Classification 📋
- SageMaker integration
- Species identification model
- Enhanced CSV results

### Iteration 5: Production Ready 📋
- Error handling & monitoring
- Performance optimization
- Deployment automation

## Quick Start

```bash
# Install dependencies
npm install

# Configure environment (first time only)
cp .env.example .env
# Edit .env with your AWS configuration

# Start development server
npm run dev

# Deploy to AWS
npx ampx sandbox
```

## Configuration

See [CONFIG.md](CONFIG.md) for detailed configuration options.

## Client Deployment

See `DEPLOYMENT.md` for step-by-step client deployment instructions.