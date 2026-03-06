#!/bin/bash
# Generates the input manifest file for Ground Truth from images already in S3.
# Each line is a JSON object pointing to one image.
# Run this before create-labeling-job.sh.

set -e

PROFILE="${1:---profile test-account}"
BUCKET="${2:-$(cat ../amplify_outputs.json | grep -o '"bucket_name":"[^"]*' | cut -d'"' -f4)}"
REGION="us-west-2"
MANIFEST_FILE="input-manifest.jsonl"

if [ -z "$BUCKET" ]; then
  echo "ERROR: Could not detect bucket name. Pass it as the second argument:"
  echo "  ./create-input-manifest.sh --profile test-account YOUR_BUCKET_NAME"
  exit 1
fi

echo "Scanning s3://$BUCKET/uploads/ for images..."

# Clear existing manifest
> "$MANIFEST_FILE"

# List all image files in the uploads prefix and write one JSON line per image
aws s3 ls "s3://$BUCKET/uploads/" --recursive $PROFILE --region $REGION \
  | grep -E '\.(jpg|jpeg|png|JPG|JPEG|PNG)$' \
  | awk '{print $4}' \
  | while read KEY; do
      echo "{\"source-ref\": \"s3://$BUCKET/$KEY\"}" >> "$MANIFEST_FILE"
    done

COUNT=$(wc -l < "$MANIFEST_FILE" | tr -d ' ')
echo "Found $COUNT images. Manifest written to $MANIFEST_FILE"

if [ "$COUNT" -eq 0 ]; then
  echo "ERROR: No images found in s3://$BUCKET/uploads/"
  echo "Make sure users have uploaded images before creating the labeling job."
  exit 1
fi

# Upload manifest to S3 so Ground Truth can read it
aws s3 cp "$MANIFEST_FILE" "s3://$BUCKET/labeling/input-manifest.jsonl" \
  $PROFILE --region $REGION

echo "Manifest uploaded to s3://$BUCKET/labeling/input-manifest.jsonl"
echo ""
echo "Next step: run ./create-labeling-job.sh"
