#!/usr/bin/env python3
import os
import sys
import json
import logging
import boto3
import pandas as pd
from datetime import datetime
import io
from PIL import Image

log_messages = []

class LogCapture(logging.Handler):
    def emit(self, record):
        log_messages.append(self.format(record))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

capture_handler = LogCapture()
capture_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(capture_handler)

class BirdSpeciesClassifier:
    def __init__(self):
        # Load configuration from file
        config_path = '/home/ec2-user/SageMaker/config.json'
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.bucket_name = config['bucket_name']
            self.model_name = config['model_name']
            self.notebook_name = config['notebook_name']
            self.s3_region = config['s3_region']
            self.sagemaker_region = config['sagemaker_region']
            
            logger.info(f"Loaded config: bucket={self.bucket_name}, model={self.model_name}, region={self.sagemaker_region}")
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {str(e)}")
            raise
        
        self.s3_client = boto3.client('s3', region_name=self.s3_region)
        self.sagemaker_client = boto3.client('sagemaker', region_name=self.sagemaker_region)
        self.sagemaker_runtime = boto3.client('sagemaker-runtime', region_name=self.sagemaker_region)
        
        self.endpoint_name = None
        self.species_names = ['pigeon', 'dove', 'starling', 'sparrow', 'blackbird', 'crow']
        logger.info(f"Initialized BirdSpeciesClassifier")
    
    def create_serverless_endpoint(self):
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            endpoint_config_name = f'bird-endpoint-config-{timestamp}'
            self.endpoint_name = f'bird-endpoint-{timestamp}'
            
            logger.info(f"Using model: {self.model_name}")
            
            self.sagemaker_client.create_endpoint_config(
                EndpointConfigName=endpoint_config_name,
                ProductionVariants=[{
                    'VariantName': 'AllTraffic',
                    'ModelName': self.model_name,
                    'ServerlessConfig': {
                        'MemorySizeInMB': 2048,
                        'MaxConcurrency': 1
                    }
                }]
            )
            
            self.sagemaker_client.create_endpoint(
                EndpointName=self.endpoint_name,
                EndpointConfigName=endpoint_config_name
            )
            
            logger.info("Waiting for endpoint...")
            waiter = self.sagemaker_client.get_waiter('endpoint_in_service')
            waiter.wait(EndpointName=self.endpoint_name, WaiterConfig={'Delay': 30, 'MaxAttempts': 20})
            
            logger.info(f"Endpoint {self.endpoint_name} ready")
            return True
        except Exception as e:
            logger.error(f"Error creating endpoint: {str(e)}")
            return False
    
    def classify_image(self, image_path):
        try:
            with Image.open(image_path) as img:
                img = img.convert('RGB')
                img = img.resize((224, 224))
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='JPEG')
                img_data = img_bytes.getvalue()
            
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=self.endpoint_name,
                ContentType='application/x-image',
                Body=img_data
            )
            
            result = json.loads(response['Body'].read().decode())
            detections = result.get('prediction', [])
            
            # Aggregate detections by class_id
            # Format: [class_id, confidence, x1, y1, x2, y2]
            species_confidences = [0.0] * 6
            species_counts = [0] * 6
            
            for detection in detections:
                class_id = int(detection[0])
                confidence = float(detection[1])
                
                if 0 <= class_id < 6 and confidence > 0.3:
                    species_confidences[class_id] = max(species_confidences[class_id], confidence)
                    species_counts[class_id] += 1
            
            logger.info(f"Processed {len(detections)} detections -> Confidences: {species_confidences}")
            
            species_data = {}
            for i, species in enumerate(self.species_names):
                confidence = species_confidences[i] * 100
                conf_level = 'high' if confidence >= 70 else 'medium' if confidence >= 50 else 'low'
                
                species_data[f'{species}_confidence'] = round(confidence, 2)
                species_data[f'{species}_confidence_level'] = conf_level
                species_data[f'{species}_count'] = species_counts[i]
            
            return species_data
        except Exception as e:
            logger.error(f"Error classifying {image_path}: {str(e)}")
            return {f'{s}_{k}': 0.0 if k == 'confidence' else 'low' if k == 'confidence_level' else 0 
                    for s in self.species_names for k in ['confidence', 'confidence_level', 'count']}
    
    def cleanup_endpoint(self):
        try:
            if self.endpoint_name:
                logger.info(f"Deleting endpoint {self.endpoint_name}...")
                self.sagemaker_client.delete_endpoint(EndpointName=self.endpoint_name)
                logger.info("Endpoint deleted")
        except Exception as e:
            logger.warning(f"Error deleting endpoint: {str(e)}")
    
    def discover_latest_csv_file(self):
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='public/results/',
                Delimiter='/'
            )
            
            if 'Contents' not in response:
                return None
            
            csv_files = [{'key': obj['Key'], 'last_modified': obj['LastModified']}
                        for obj in response['Contents']
                        if obj['Key'].endswith('.csv') and 'bird-results' in obj['Key']]
            
            if not csv_files:
                return None
            
            latest_csv = sorted(csv_files, key=lambda x: x['last_modified'], reverse=True)[0]
            logger.info(f"Found CSV: {latest_csv['key']}")
            return latest_csv['key']
        except Exception as e:
            logger.error(f"Error discovering CSV: {str(e)}")
            return None
    
    def process_csv_with_species(self, csv_key):
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=csv_key)
            df = pd.read_csv(io.StringIO(response['Body'].read().decode('utf-8')))
            logger.info(f"Processing {len(df)} rows")
            
            for idx, row in df.iterrows():
                image_key = f"public/{row['extraction_folder']}/{row['filename']}"
                temp_image = f'/tmp/temp_image_{idx}.jpg'
                
                try:
                    self.s3_client.download_file(self.bucket_name, image_key, temp_image)
                    species_data = self.classify_image(temp_image)
                    
                    for key, value in species_data.items():
                        df.at[idx, key] = value
                    
                    os.remove(temp_image)
                except Exception as e:
                    logger.warning(f"Error processing {image_key}: {str(e)}")
            
            for species in self.species_names:
                df[f'total_{species}_count'] = df[f'{species}_count'].sum()
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            enhanced_csv = f'public/results/enhanced_bird_results_{timestamp}.csv'
            
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=enhanced_csv,
                Body=csv_buffer.getvalue(),
                ContentType='text/csv'
            )
            
            logger.info(f"Created: {enhanced_csv}")
            return enhanced_csv
        except Exception as e:
            logger.error(f"Error processing CSV: {str(e)}")
            return None
    
    def run_pipeline(self):
        logger.info("Starting pipeline")
        
        try:
            if not self.create_serverless_endpoint():
                return False
            
            csv_key = self.discover_latest_csv_file()
            if not csv_key:
                return False
            
            enhanced_csv = self.process_csv_with_species(csv_key)
            return enhanced_csv is not None
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}")
            return False
        finally:
            self.cleanup_endpoint()

def main():
    logger.info("Bird Species Classification Started")
    
    try:
        classifier = BirdSpeciesClassifier()
        success = classifier.run_pipeline()
        logger.info(f"Completed. Success: {success}")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        success = False
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_client = boto3.client('s3', region_name=classifier.s3_region)
        log_content = f"Completed at {timestamp}\nSuccess: {success}\n\n{'\n'.join(log_messages)}"
        
        s3_client.put_object(
            Bucket=classifier.bucket_name,
            Key=f'logs/bird_classification_{timestamp}.log',
            Body=log_content,
            ContentType='text/plain'
        )
    except Exception as e:
        logger.warning(f"Could not upload log: {str(e)}")
    
    try:
        sagemaker = boto3.client('sagemaker', region_name=classifier.s3_region)
        
        # Wait for notebook to be InService before stopping
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                response = sagemaker.describe_notebook_instance(NotebookInstanceName=classifier.notebook_name)
                status = response['NotebookInstanceStatus']
                
                if status == 'InService':
                    logger.info(f"Notebook is InService, stopping now...")
                    sagemaker.stop_notebook_instance(NotebookInstanceName=classifier.notebook_name)
                    logger.info("Notebook stop initiated successfully")
                    break
                else:
                    logger.info(f"Notebook status: {status}, waiting... (attempt {attempt+1}/{max_attempts})")
                    import time
                    time.sleep(30)
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed: {str(e)}")
                if attempt < max_attempts - 1:
                    import time
                    time.sleep(30)
                else:
                    raise
    except Exception as e:
        logger.warning(f"Could not shutdown notebook: {str(e)}")
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
