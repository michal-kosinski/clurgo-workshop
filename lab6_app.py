import os
import boto3
import json
import logging
from flask import Flask, request, jsonify, render_template_string
from werkzeug.utils import secure_filename
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# AWS Configuration
S3_BUCKET = os.getenv('S3_BUCKET', 'mikosins4-workshop')
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:eu-central-1:416655267863:AmazonTextract-mikosins-workshop')
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL', 'https://sqs.eu-central-1.amazonaws.com/416655267863/mikosins-workshop')
ROLE_ARN = os.getenv('ROLE_ARN', 'arn:aws:iam::416655267863:role/mikosins-workshop')

session = boto3.Session()

s3 = session.client('s3', region_name='eu-central-1')
textract = session.client('textract', region_name='eu-central-1')
sqs = session.client('sqs', region_name='eu-central-1')

# HTML template for the upload form
UPLOAD_FORM = '''
<!doctype html>
<html>
<head>
    <title>File Upload</title>
</head>
<body>
    <h1>Upload a file</h1>
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <input type="submit" value="Upload">
    </form>
    {% if result %}
    <h2>Extracted Text:</h2>
    <pre>{{ result }}</pre>
    {% endif %}
</body>
</html>
'''

@app.route('/')
def hello_world():
    return '<p>Hello, World!</p><a href="/upload">file upload</a>'

@app.route('/health')
def health_check():
    return '', 200

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return render_template_string(UPLOAD_FORM)

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join('/tmp', filename)
        file.save(file_path)

        # Upload to S3
        try:
            s3.upload_file(file_path, S3_BUCKET, filename)
            logger.info(f"File uploaded to S3: {S3_BUCKET}/{filename}")
        except Exception as e:
            logger.error(f"Error uploading file to S3: {str(e)}")
            return jsonify({'error': 'Failed to upload file to S3'}), 500

        # Start Textract job
        try:
            response = textract.start_document_analysis(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': S3_BUCKET,
                        'Name': filename
                    }
                },
                FeatureTypes=['FORMS', 'TABLES'],
                NotificationChannel={
                    'SNSTopicArn': SNS_TOPIC_ARN,
                    'RoleArn': ROLE_ARN
                }
            )
            job_id = response['JobId']
            logger.info(f"Textract job started. Job ID: {job_id}")
        except Exception as e:
            logger.error(f"Error starting Textract job: {str(e)}")
            return jsonify({'error': 'Failed to start Textract job'}), 500

        # Wait for Textract job to complete
        max_attempts = 30  # Adjust as needed
        attempts = 0
        while attempts < max_attempts:
            try:
                logger.info(f"Checking SQS queue. Attempt {attempts + 1}/{max_attempts}")
                response = sqs.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20
                )

                logger.debug(f"SQS response: {json.dumps(response, default=str)}")

                if 'Messages' in response:
                    message = response['Messages'][0]
                    receipt_handle = message['ReceiptHandle']
                    body = json.loads(message['Body'])

                    logger.info(f"Received message: {json.dumps(body, indent=2)}")

                    # Check if the message is for our job
                    if 'JobId' in body and body['JobId'] == job_id:
                        # Delete the message from the queue
                        sqs.delete_message(
                            QueueUrl=SQS_QUEUE_URL,
                            ReceiptHandle=receipt_handle
                        )
                        logger.info("Job completion message received and deleted from queue")
                        break
                else:
                    logger.info("No messages in queue")

            except Exception as e:
                logger.error(f"Error checking SQS queue: {str(e)}")

            attempts += 1
            time.sleep(10)

        if attempts >= max_attempts:
            logger.error("Max attempts reached. Job may not have completed.")
            return jsonify({'error': 'Textract job timed out'}), 500

        # Get Textract results
        try:
            response = textract.get_document_analysis(JobId=job_id)
            logger.info("Retrieved Textract results")
        except Exception as e:
            logger.error(f"Error getting Textract results: {str(e)}")
            return jsonify({'error': 'Failed to get Textract results'}), 500

        # Extract text from the response
        extracted_text = ""
        for item in response['Blocks']:
            if item['BlockType'] == 'LINE':
                extracted_text += item['Text'] + "\n"

        logger.info("Text extraction completed")
        return render_template_string(UPLOAD_FORM, result=extracted_text)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)