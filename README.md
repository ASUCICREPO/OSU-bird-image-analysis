# Bird Processing System v2

A client-ready bird counting and species classification system built with AWS Amplify.

## Disclaimers
Customers are responsible for making their own independent assessment of the information in this document.

This document:

(a) is for informational purposes only,

(b) references AWS product offerings and practices, which are subject to change without notice,

(c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided "as is" without warranties, representations, or conditions of any kind, whether express or implied. The responsibilities and liabilities of AWS to its customers are controlled by AWS agreements, and this document is not part of, nor does it modify, any agreement between AWS and its customers, and

(d) is not to be considered a recommendation or viewpoint of AWS.

Additionally, you are solely responsible for testing, security and optimizing all code and assets on GitHub repo, and all such code and assets should be considered:

(a) as-is and without warranties or representations of any kind,

(b) not suitable for production environments, or on production or other critical data, and

(c) to include shortcuts in order to support rapid prototyping such as, but not limited to, relaxed authentication and authorization and a lack of strict adherence to security best practices.

All work produced is open source. More information can be found in the GitHub repo.

## Project Overview

This system allows users to upload bird images and receive automated counting and species classification results.

## Development Iterations

### Iteration 1: Basic Setup & Authentication 
- Project scaffolding
- AWS Amplify configuration
- Clean React UI without authentication
- Professional interface design

### Iteration 2: File Upload & Storage 
- S3 bucket configuration with guest access
- Real S3 file upload with progress tracking
- Support for ZIP files and images
- File validation and error handling

### Iteration 3: Bird Counting with AI 
- Lambda function for image processing
- Claude AI integration for bird counting
- CSV result generation

### Iteration 4: Species Classification 
- SageMaker integration
- Species identification model
- Enhanced CSV results

### Iteration 5: Production Ready 
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
