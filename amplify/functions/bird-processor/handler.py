import boto3
import base64
import json
import csv
import io
import zipfile
import time
import re
import hashlib
import logging
import os
from datetime import datetime
from urllib.parse import unquote_plus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("BEDROCK_REGION", "us-west-2"))
MODEL_ID = os.environ.get("CLAUDE_MODEL_ID", "global.anthropic.claude-sonnet-4-20250514-v1:0")

BATCH_SIZE = 50  # Process 50 images at a time

# Security configurations
MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB
MAX_ZIP_ENTRIES = 10000  # Maximum number of files in a ZIP
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
MALICIOUS_PATTERNS = [
    r'\.\./',  # Path traversal
    r'<script',  # XSS attempts
    r'javascript:',  # JavaScript injection
    r'vbscript:',  # VBScript injection
    r'\.exe$',  # Executable files
    r'\.bat$',  # Batch files
    r'\.cmd$',  # Command files
    r'\.scr$',  # Screen saver files
    r'\.pif$',  # Program information files
]

def validate_filename_security(filename):
    """Validate filename for security issues"""
    # Check for malicious patterns
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            logger.warning(f"Malicious pattern detected in filename: {filename} - pattern: {pattern}")
            return False
    
    # Check filename length
    if len(filename) > 255:
        logger.warning(f"Filename too long: {filename}")
        return False
    
    # Check for null bytes
    if '\x00' in filename:
        logger.warning(f"Null byte detected in filename: {filename}")
        return False
    
    return True

def sanitize_filename(filename):
    """Sanitize filename by removing dangerous characters"""
    # Remove path components
    filename = filename.split('/')[-1]
    
    # Replace dangerous characters with underscores
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Ensure it doesn't start with a dot (hidden file)
    if sanitized.startswith('.'):
        sanitized = 'file_' + sanitized[1:]
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        max_name_len = 255 - len(ext) - 1 if ext else 255
        sanitized = name[:max_name_len] + ('.' + ext if ext else '')
    
    return sanitized

def validate_zip_security(zip_file):
    """Validate ZIP file for security issues"""
    file_count = 0
    total_uncompressed_size = 0
    
    for file_info in zip_file.filelist:
        file_count += 1
        
        # Check for zip bomb (too many files)
        if file_count > MAX_ZIP_ENTRIES:
            logger.error(f"ZIP file contains too many entries: {file_count}")
            return False, "ZIP file contains too many entries"
        
        # Check for zip bomb (excessive uncompressed size)
        total_uncompressed_size += file_info.file_size
        if total_uncompressed_size > MAX_FILE_SIZE * 10:  # Allow 10x expansion
            logger.error(f"ZIP file uncompressed size too large: {total_uncompressed_size}")
            return False, "ZIP file uncompressed size too large"
        
        # Check compression ratio for potential zip bomb
        if file_info.compress_size > 0:
            ratio = file_info.file_size / file_info.compress_size
            if ratio > 100:  # Suspicious compression ratio
                logger.warning(f"Suspicious compression ratio for {file_info.filename}: {ratio}")
        
        # Validate filename
        if not validate_filename_security(file_info.filename):
            return False, f"Malicious filename detected: {file_info.filename}"
    
    return True, "ZIP file validation passed"

def is_image_file(filename):
    """Check if file is an image based on extension with security validation"""
    if not validate_filename_security(filename):
        return False
    
    extension = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
    return extension in ALLOWED_IMAGE_EXTENSIONS

def is_mac_metadata_file(filename):
    """Check if file is Mac metadata that should be skipped"""
    filename = filename.lower()
    return (
        filename.startswith('__macosx/') or
        filename.startswith('.ds_store') or
        filename.endswith('.ds_store') or
        filename.startswith('._') or
        '/._' in filename or
        filename == 'thumbs.db'
    )

def process_image_with_claude(image_bytes, filename):
    """Process single image with Claude and return bird count with retry logic"""
    max_retries = 3
    base_delay = 1  # Start with 1 second delay
    
    print(f"🔍 Processing image {filename}")
    import sys
    sys.stdout.flush()
    
    for attempt in range(max_retries):
        try:
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": "Count the number of birds in this image. Respond with ONLY a number, nothing else."
                            }
                        ]
                    }
                ],
                "max_tokens": 10
            }

            print(f"🤖 Calling Claude AI for bird counting: {filename}...")
            sys.stdout.flush()
            
            response = bedrock.invoke_model(
                modelId=MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body)
            )
            
            print(f"✅ Claude AI response received for {filename}")
            sys.stdout.flush()

            result = json.loads(response["body"].read())
            response_text = result["content"][0]["text"].strip()
            
            # Try to extract just the number
            import re
            numbers = re.findall(r'\d+', response_text)
            if numbers:
                bird_count = int(numbers[0])
            else:
                raise ValueError(f"No number found in response: {response_text}")
            
            print(f"🐦 {filename}: {bird_count} birds detected by Claude AI")
            sys.stdout.flush()
            return bird_count
            
        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1} failed for {filename}: {str(e)}")
            sys.stdout.flush()
            
            # If this was the last attempt, return 0
            if attempt == max_retries - 1:
                print(f"❌ All {max_retries} attempts failed for {filename}, returning 0")
                sys.stdout.flush()
                return 0
            
            # Exponential backoff: wait 1s, then 2s, then 4s
            delay = base_delay * (2 ** attempt)
            print(f"⏳ Retrying in {delay} seconds...")
            sys.stdout.flush()
            time.sleep(delay)
    
    return 0

def save_results_to_s3_csv(bucket, results, extraction_folder):
    """Save bird count results to public/results/ folder - NO MOCK DATA"""
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    csv_key = f"public/results/bird-results-{timestamp}.csv"
    
    # Simple header with only real data from Claude AI
    header = ["filename", "bird_count", "extraction_folder"]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    
    for filename, bird_count in results:
        row = [filename, bird_count, extraction_folder]
        writer.writerow(row)
    
    # Add server-side encryption
    s3.put_object(
        Bucket=bucket,
        Key=csv_key,
        Body=output.getvalue().encode("utf-8"),
        ContentType="text/csv",
        ServerSideEncryption='AES256'
    )
    
    print(f"📁 Created CSV with REAL Claude AI results: {csv_key} with {len(results)} results")
    import sys
    sys.stdout.flush()
    
    # Log real summary
    total_birds = sum(bird_count for _, bird_count in results)
    images_with_birds = sum(1 for _, bird_count in results if bird_count > 0)
    print(f"📊 REAL Claude AI Summary: {len(results)} images processed, {total_birds} total birds detected, {images_with_birds} images contain birds")
    sys.stdout.flush()
    
    # Trigger SageMaker processing for enhanced species classification
    print("🚀 About to trigger SageMaker processing...")
    sys.stdout.flush()
    trigger_sagemaker_processing(bucket, csv_key, extraction_folder)
    print("✅ SageMaker trigger attempt completed")
    sys.stdout.flush()

def trigger_sagemaker_processing(bucket, csv_key, extraction_folder):
    """Trigger SageMaker notebook for species classification with improved reliability"""
    try:
        # Get current region from environment - FIXED to us-west-2
        current_region = os.environ.get('AWS_REGION', 'us-west-2')
        
        # Create SageMaker client
        sagemaker = boto3.client('sagemaker', region_name=current_region)
        
        # Create parameter file for SageMaker with dynamic paths
        params = {
            "bucket_name": bucket,
            "csv_key": csv_key,
            "extraction_folder": extraction_folder,
            "timestamp": datetime.utcnow().isoformat(),
            "model_s3_path": f"s3://{bucket}/models/bird-species-model.tar.gz",
            "model_metadata_path": f"s3://{bucket}/models/model-metadata.json",
            "current_region": current_region,
            "container_image": os.environ.get("CONTAINER_IMAGE", "")
        }
        
        params_key = "sagemaker/processing_params.json"
        s3.put_object(
            Bucket=bucket,
            Key=params_key,
            Body=json.dumps(params),
            ContentType="application/json",
            ServerSideEncryption='AES256'
        )
        logger.info(f"💾 Saved SageMaker parameters: {params_key}")
        print(f"💾 Saved SageMaker parameters: {params_key}")
        import sys
        sys.stdout.flush()
        
        # Create trigger file for daemon
        trigger_data = {
            "csv_key": csv_key,
            "extraction_folder": extraction_folder,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        trigger_key = "triggers/run_classification"
        s3.put_object(
            Bucket=bucket,
            Key=trigger_key,
            Body=json.dumps(trigger_data),
            ContentType="application/json",
            ServerSideEncryption='AES256'
        )
        print(f"🎯 Created daemon trigger: {trigger_key}")
        sys.stdout.flush()
        
        # Start SageMaker notebook instance with improved status handling
        notebook_name = "bird-species-classifier-notebook-v4"
        print(f"🔍 Checking SageMaker notebook: {notebook_name}")
        sys.stdout.flush()
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Check notebook status
                response = sagemaker.describe_notebook_instance(NotebookInstanceName=notebook_name)
                status = response['NotebookInstanceStatus']
                print(f"📊 Current notebook status: {status} (attempt {retry_count + 1}/{max_retries})")
                sys.stdout.flush()
                
                if status == 'Stopped':
                    print("🚀 Starting stopped notebook...")
                    sagemaker.start_notebook_instance(NotebookInstanceName=notebook_name)
                    print(f"✅ Notebook start initiated: {notebook_name}")
                    print("📝 Lifecycle script will run automatically and stop notebook when done")
                    break
                    
                elif status == 'InService':
                    print(f"⚠️ Notebook already running: {notebook_name}")
                    print("🔄 Stopping and restarting to trigger fresh processing...")
                    
                    # Stop the notebook
                    sagemaker.stop_notebook_instance(NotebookInstanceName=notebook_name)
                    print("⏳ Waiting for notebook to stop...")
                    
                    # Wait for it to stop with timeout
                    waiter = sagemaker.get_waiter('notebook_instance_stopped')
                    waiter.wait(
                        NotebookInstanceName=notebook_name, 
                        WaiterConfig={'Delay': 30, 'MaxAttempts': 15}  # 7.5 minutes max
                    )
                    print("✅ Notebook stopped")
                    
                    # Start it again
                    print("🚀 Starting notebook to trigger processing...")
                    sagemaker.start_notebook_instance(NotebookInstanceName=notebook_name)
                    print("✅ Notebook restart initiated - improved lifecycle script will auto-stop")
                    break
                    
                elif status in ['Starting', 'Stopping']:
                    print(f"⏳ Notebook in transition state: {status}")
                    if retry_count < max_retries - 1:
                        print(f"⏳ Waiting 60 seconds before retry...")
                        time.sleep(60)
                        retry_count += 1
                        continue
                    else:
                        print("⚠️ Max retries reached, creating delayed trigger")
                        retry_key = f"sagemaker/delayed_trigger_{int(time.time())}.json"
                        retry_data = {
                            "action": "delayed_processing",
                            "csv_key": csv_key,
                            "extraction_folder": extraction_folder,
                            "current_status": status,
                            "timestamp": datetime.utcnow().isoformat(),
                            "note": "Notebook was in transition state, manual intervention may be needed"
                        }
                        s3.put_object(
                            Bucket=bucket,
                            Key=retry_key,
                            Body=json.dumps(retry_data),
                            ContentType="application/json",
                            ServerSideEncryption='AES256'
                        )
                        print(f"📝 Created delayed trigger: {retry_key}")
                        break
                        
                else:
                    print(f"❌ Unexpected notebook status: {status}")
                    if retry_count < max_retries - 1:
                        print("🔄 Attempting to start notebook anyway...")
                        try:
                            sagemaker.start_notebook_instance(NotebookInstanceName=notebook_name)
                            print("🚀 Start command sent")
                            break
                        except Exception as start_error:
                            print(f"⚠️ Start failed: {str(start_error)}")
                            retry_count += 1
                            if retry_count < max_retries:
                                time.sleep(30)
                    else:
                        print("❌ All retry attempts failed")
                        break
                        
            except Exception as status_error:
                print(f"❌ Error checking notebook status: {str(status_error)}")
                retry_count += 1
                if retry_count < max_retries:
                    print(f"⏳ Retrying in 30 seconds... ({retry_count}/{max_retries})")
                    time.sleep(30)
                else:
                    raise status_error
                    
        import sys
        sys.stdout.flush()
                
    except sagemaker.exceptions.ClientError as e:
            if 'does not exist' in str(e):
                print(f"❌ SageMaker notebook {notebook_name} does not exist")
                print("🛠️ Notebook needs to be created manually or deployment is incomplete")
                
                # Create error report
                error_key = f"sagemaker/notebook_missing_{int(time.time())}.json"
                error_data = {
                    "error": "notebook_not_found",
                    "notebook_name": notebook_name,
                    "message": "SageMaker notebook instance does not exist",
                    "timestamp": datetime.utcnow().isoformat()
                }
                s3.put_object(
                    Bucket=bucket,
                    Key=error_key,
                    Body=json.dumps(error_data),
                    ContentType="application/json",
                    ServerSideEncryption='AES256'
                )
                print(f"📄 Created error report: {error_key}")
            else:
                print(f"❌ SageMaker ClientError: {str(e)}")
                import traceback
                print(f"🔍 Error traceback: {traceback.format_exc()}")
                raise e
            import sys
            sys.stdout.flush()
                
    except Exception as e:
        logger.error(f"❌ Failed to trigger SageMaker processing: {str(e)}")
        print(f"❌ Failed to trigger SageMaker processing: {str(e)}")
        import traceback
        print(f"🔍 SageMaker error traceback: {traceback.format_exc()}")
        import sys
        sys.stdout.flush()
        # Don't fail the main processing if SageMaker trigger fails

def process_zip_file(bucket, key):
    """Process ZIP file with security validations"""
    logger.info(f"📦 Processing ZIP file: {key}")
    
    # Download ZIP file from S3
    s3_obj = s3.get_object(Bucket=bucket, Key=key)
    zip_bytes = s3_obj["Body"].read()
    
    # Validate ZIP file security
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
        is_valid, validation_message = validate_zip_security(zip_file)
        if not is_valid:
            logger.error(f"Security validation failed for {key}: {validation_message}")
            raise ValueError(f"ZIP security validation failed: {validation_message}")
        
        # Extract and filter image files
        image_files = []
        for file_info in zip_file.filelist:
            if file_info.is_dir():
                continue
                
            filename = file_info.filename
            
            # Skip Mac metadata files
            if is_mac_metadata_file(filename):
                logger.info(f"🗑️ Skipping Mac metadata: {filename}")
                continue
                
            # Skip non-image files
            if not is_image_file(filename):
                logger.info(f"⏭️ Skipping non-image: {filename}")
                continue
            
            try:
                image_data = zip_file.read(filename)
                clean_filename = sanitize_filename(filename.split('/')[-1])
                
                image_files.append({
                    'filename': clean_filename,
                    'data': image_data
                })
                
                logger.info(f"💾 Extracted: {clean_filename}")
            except Exception as e:
                logger.error(f"❌ Error extracting {filename}: {str(e)}")
    
    logger.info(f"📊 Found {len(image_files)} image files to process")
    
    # Process images in batches
    results = []
    
    for i in range(0, len(image_files), BATCH_SIZE):
        batch = image_files[i:i + BATCH_SIZE]
        logger.info(f"🔄 Processing batch {i // BATCH_SIZE + 1}/{(len(image_files) + BATCH_SIZE - 1) // BATCH_SIZE}")
        
        for file_data in batch:
            try:
                bird_count = process_image_with_claude(file_data['data'], file_data['filename'])
                results.append((file_data['filename'], bird_count))
            except Exception as e:
                logger.error(f"Error processing {file_data['filename']}: {str(e)}")
                results.append((file_data['filename'], 0))
    
    # Save extracted images to S3
    zip_name = key.split('/')[-1].replace('.zip', '').replace('.ZIP', '')
    extraction_folder = f"extracted/{sanitize_filename(zip_name)}-{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"
    
    print(f"📤 Uploading {len(image_files)} images to S3: {extraction_folder}")
    import sys
    sys.stdout.flush()
    
    # Upload each image to S3
    for file_data in image_files:
        image_key = f"public/{extraction_folder}/{file_data['filename']}"
        try:
            s3.put_object(
                Bucket=bucket,
                Key=image_key,
                Body=file_data['data'],
                ContentType='image/jpeg',
                ServerSideEncryption='AES256'
            )
            print(f"✅ Uploaded: {image_key}")
        except Exception as upload_error:
            print(f"❌ Failed to upload {image_key}: {str(upload_error)}")
    
    sys.stdout.flush()
    
    # Save results to CSV
    save_results_to_s3_csv(bucket, results, extraction_folder)
    
    logger.info(f"✅ ZIP processing complete: {len(results)} images processed")

def process_single_image(bucket, key):
    """Process single image file"""
    logger.info(f"🕊️ Processing single image: {key}")
    
    # Download image from S3
    s3_obj = s3.get_object(Bucket=bucket, Key=key)
    image_bytes = s3_obj["Body"].read()
    
    # Process with Claude
    filename = sanitize_filename(key.split('/')[-1])
    bird_count = process_image_with_claude(image_bytes, filename)
    
    # Save result
    results = [(filename, bird_count)]
    save_results_to_s3_csv(bucket, results, 'uploads')
    
    logger.info(f"✅ Single image processing complete: {bird_count} birds found")

def lambda_handler(event, context):
    """Main Lambda handler - UPDATED VERSION 4 - FIXED NOTEBOOK NAME"""
    import sys
    
    # Use print and flush immediately
    print("🚀🚀🚀 UPDATED Lambda function started - VERSION 4 - FIXED NOTEBOOK NAME")
    sys.stdout.flush()
    print(f"🪶 S3 Event Received with {len(event.get('Records', []))} records")
    sys.stdout.flush()
    
    # Also try logger
    try:
        logger.info("🚀 Logger test")
    except Exception as log_error:
        print(f"❌ Logger error: {log_error}")
        sys.stdout.flush()
    
    try:
        print(f"📊 Processing {len(event['Records'])} records")
        
        for i, record in enumerate(event["Records"]):
            print(f"🔄 Processing record {i+1}")
            
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
            
            print(f"📁 Processing file {i+1}: {key} in bucket: {bucket}")
            
            try:
                if key.lower().endswith('.zip'):
                    print("📦 Processing ZIP file")
                    process_zip_file(bucket, key)
                elif is_image_file(key):
                    print("🖼️ Processing single image")
                    process_single_image(bucket, key)
                else:
                    print(f"⏭️ Skipping unsupported file: {key}")
                    
                print(f"✅ Successfully processed file {i+1}")
                    
            except Exception as file_error:
                print(f"❌ Error processing {key}: {str(file_error)}")
                import traceback
                print(f"🔍 Traceback: {traceback.format_exc()}")
                # Continue processing other files even if one fails
        
        print("🎉 All files processed successfully")
        return {
            "statusCode": 200,
            "body": json.dumps("✅ Processing complete")
        }
        
    except Exception as handler_error:
        print(f"❌ Critical handler error: {str(handler_error)}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        raise handler_error
