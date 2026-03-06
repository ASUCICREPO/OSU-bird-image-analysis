"""
Lambda function: triggered by EventBridge when a Ground Truth labeling job completes.
It starts a SageMaker Training Job using the labeled data, then updates the
existing model and endpoint so the app immediately uses the improved model.

Environment variables (set in setup-retraining-trigger.sh):
  MODEL_BUCKET            - S3 bucket where model.tar.gz lives
  SAGEMAKER_ROLE_ARN      - SageMaker execution role ARN
  SAGEMAKER_MODEL_NAME    - e.g. bird-species-detection-model-i107-fr-1l
  SAGEMAKER_ENDPOINT_NAME - the endpoint serving the model (if deployed)
  REGION                  - us-west-2
"""

import boto3
import botocore.exceptions
import os
import json
from datetime import datetime

sagemaker = boto3.client('sagemaker', region_name=os.environ['REGION'])

CONTAINER_IMAGE = f"433757028032.dkr.ecr.{os.environ['REGION']}.amazonaws.com/object-detection:1"

# Exact hyperparameters from seniors' training job: bird-model-split-data-i107-freeze-layer1
# num_training_samples is updated at runtime with the actual labeled count from each job.
BASE_HYPERPARAMETERS = {
    'base_network':              'resnet-50',
    'early_stopping':            'false',
    'early_stopping_min_epochs': '10',
    'early_stopping_patience':   '5',
    'early_stopping_tolerance':  '0.0',
    'epochs':                    '80',
    'freeze_layer_pattern':      'resnetv10_stage1_.*',
    'learning_rate':             '0.0005',
    'lr_scheduler_factor':       '0.1',
    'mini_batch_size':           '8',
    'momentum':                  '0.9',
    'nms_threshold':             '0.45',
    'num_classes':               '6',
    'optimizer':                 'adam',
    'overlap_threshold':         '0.5',
    'use_pretrained_model':      '1',
    'weight_decay':              '0.0005',
}

# Must match --label-attribute-name used when creating Ground Truth labeling jobs
LABEL_ATTRIBUTE = 'osu-bird-data-labelling-v1'


def handler(event, context):
    print("Event received:", json.dumps(event))

    # EventBridge delivers labeling job state change events
    detail = event.get('detail', {})
    job_name = detail.get('LabelingJobName')
    status = detail.get('LabelingJobStatus')

    if status != 'Completed':
        print(f"Job {job_name} status is '{status}', not Completed. Skipping.")
        return

    print(f"Labeling job '{job_name}' completed. Starting retraining...")

    # Get the output manifest path from the completed labeling job
    job_info = sagemaker.describe_labeling_job(LabelingJobName=job_name)
    output_manifest = job_info['LabelingJobOutput']['OutputDatasetS3Uri']
    print(f"Output manifest: {output_manifest}")

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    training_job_name = f"bird-retrain-{timestamp}"
    model_bucket = os.environ['MODEL_BUCKET']
    role_arn = os.environ['SAGEMAKER_ROLE_ARN']
    output_path = f"s3://{model_bucket}/retrained-models/{training_job_name}/"

    num_labeled = job_info['LabelingJobOutput'].get('TotalLabeled', 100)
    hyperparams = {**BASE_HYPERPARAMETERS, 'num_training_samples': str(num_labeled)}

    # Ground Truth produces a single output.manifest — no automatic train/validation split.
    # We use only a train channel. early_stopping is off so validation is not required.
    sagemaker.create_training_job(
        TrainingJobName=training_job_name,
        AlgorithmSpecification={
            'TrainingImage': CONTAINER_IMAGE,
            'TrainingInputMode': 'Pipe',
        },
        RoleArn=role_arn,
        InputDataConfig=[
            {
                'ChannelName': 'train',
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'AugmentedManifestFile',
                        'S3Uri': output_manifest,
                        'S3DataDistributionType': 'FullyReplicated',
                        'AttributeNames': ['source-ref', LABEL_ATTRIBUTE],
                    }
                },
                'ContentType': 'application/x-recordio',
                'CompressionType': 'None',
                'RecordWrapperType': 'RecordIO',
            },
        ],
        OutputDataConfig={'S3OutputPath': output_path},
        ResourceConfig={
            'InstanceType': 'ml.p3.2xlarge',  # GPU — matches seniors' original training
            'InstanceCount': 1,
            'VolumeSizeInGB': 1,
        },
        StoppingCondition={'MaxRuntimeInSeconds': 3600},
        HyperParameters=hyperparams,
        Tags=[
            {'Key': 'LabelingJob', 'Value': job_name},
            {'Key': 'Project', 'Value': 'bird-species-detection'},
        ]
    )

    print(f"Training job '{training_job_name}' started. Output: {output_path}")

    # Store the training job name so the model-update Lambda can find the new artifact.
    # We tag it so EventBridge can match it when it completes.
    return {
        'statusCode': 200,
        'trainingJobName': training_job_name,
        'outputPath': output_path,
    }


def update_model_after_training(event, context):
    """
    Second Lambda — triggered when the training job above COMPLETES.
    Creates a new SageMaker model version and updates the endpoint.
    Wire this to: source=aws.sagemaker, detail-type=SageMaker Training Job State Change, status=Completed
    Filter on tag Project=bird-species-detection to avoid triggering on unrelated jobs.
    """
    print("Training complete event:", json.dumps(event))

    detail = event.get('detail', {})
    training_job_name = detail.get('TrainingJobName', '')
    status = detail.get('TrainingJobStatus')

    if status != 'Completed':
        print(f"Training job status '{status}', skipping.")
        return

    # Only act on our retraining jobs
    if not training_job_name.startswith('bird-retrain-'):
        print(f"Job '{training_job_name}' is not a bird retraining job, skipping.")
        return

    # Get the new model artifact location
    job_info = sagemaker.describe_training_job(TrainingJobName=training_job_name)
    new_model_artifact = job_info['ModelArtifacts']['S3ModelArtifacts']
    print(f"New model artifact: {new_model_artifact}")

    role_arn = os.environ['SAGEMAKER_ROLE_ARN']
    model_name = os.environ['SAGEMAKER_MODEL_NAME']
    endpoint_name = os.environ.get('SAGEMAKER_ENDPOINT_NAME', '')
    endpoint_config_name = os.environ.get('SAGEMAKER_ENDPOINT_CONFIG_NAME', 'bird-species-endpoint-config')

    # SageMaker models are immutable — delete and recreate with the same name
    # so nothing else (endpoint config, .env, app code) ever needs to change.
    try:
        sagemaker.delete_model(ModelName=model_name)
        print(f"Deleted old model: {model_name}")
    except botocore.exceptions.ClientError:
        print(f"Model '{model_name}' did not exist yet, creating fresh.")

    sagemaker.create_model(
        ModelName=model_name,
        PrimaryContainer={
            'Image': CONTAINER_IMAGE,
            'ModelDataUrl': new_model_artifact,
        },
        ExecutionRoleArn=role_arn,
    )
    print(f"Model '{model_name}' recreated with new artifact: {new_model_artifact}")

    # Update the endpoint to reload the model (endpoint config name stays the same too)
    if endpoint_name:
        try:
            sagemaker.delete_endpoint_config(EndpointConfigName=endpoint_config_name)
        except botocore.exceptions.ClientError:
            pass

        sagemaker.create_endpoint_config(
            EndpointConfigName=endpoint_config_name,
            ProductionVariants=[{
                'VariantName': 'AllTraffic',
                'ModelName': model_name,
                'InitialInstanceCount': 1,
                'InstanceType': 'ml.m5.xlarge',
                'InitialVariantWeight': 1,
            }]
        )
        sagemaker.update_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=endpoint_config_name,
        )
        print(f"Endpoint '{endpoint_name}' updated — same name, new weights.")
    else:
        print("No endpoint configured. Model is updated but not deployed to an endpoint.")

    return {
        'statusCode': 200,
        'modelName': model_name,
    }
