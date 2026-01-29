#!/bin/bash
# Production Lifecycle Script with Species Classification

exec > /tmp/lifecycle.log 2>&1

echo "=== PRODUCTION LIFECYCLE STARTED at $(date) ==="

# Copy the production script to SageMaker directory
sudo -u ec2-user bash << 'EOF'
cd /home/ec2-user/SageMaker
source /home/ec2-user/anaconda3/bin/activate

echo "Installing packages..."
pip install --quiet boto3 pandas pillow

# Write configuration file
cat > /home/ec2-user/SageMaker/config.json << 'CONFIG_EOF'
CONFIG_JSON_PLACEHOLDER
CONFIG_EOF

chmod 644 /home/ec2-user/SageMaker/config.json
echo "Configuration written: $(cat /home/ec2-user/SageMaker/config.json)"

echo "Copying production script from S3..."
aws s3 cp s3://BUCKET_NAME_PLACEHOLDER/scripts/bird_species_counter_production.py bird_species_counter_production.py

if [ ! -f bird_species_counter_production.py ]; then
    echo "ERROR: Failed to download script from S3"
    exit 1
fi

chmod +x bird_species_counter_production.py

echo "Running production script..."
python3 bird_species_counter_production.py

EOF

echo "=== PRODUCTION LIFECYCLE COMPLETED at $(date) ==="