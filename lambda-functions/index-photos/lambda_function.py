import boto3
import json
import os
import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION = 'us-east-1'
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']  # hostname only, no https://
INDEX_NAME = 'photos'

rekognition = boto3.client('rekognition', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)


def get_os_client():
    creds = boto3.Session().get_credentials().get_frozen_credentials()
    auth = AWS4Auth(creds.access_key, creds.secret_key, REGION, 'es',
                    session_token=creds.token)
    return OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )


def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        # S3 event keys are URL-encoded — decode spaces and special chars
        from urllib.parse import unquote_plus
        key = unquote_plus(record['s3']['object']['key'])

        # 1. Read custom labels from S3 metadata (set via x-amz-meta-customlabels header)
        head = s3.head_object(Bucket=bucket, Key=key)
        raw  = head.get('Metadata', {}).get('customlabels', '')
        custom_labels = [l.strip().lower() for l in raw.split(',') if l.strip()]

        # 2. Auto-detect labels with Rekognition (best-effort — don't fail if image format unsupported)
        rek_labels = []
        try:
            rek = rekognition.detect_labels(
                Image={'S3Object': {'Bucket': bucket, 'Name': key}},
                MaxLabels=15,
                MinConfidence=70,
            )
            rek_labels = [lbl['Name'].lower() for lbl in rek['Labels']]
        except Exception as e:
            print(f"Rekognition failed for {key}: {e} — indexing with custom labels only")

        all_labels = rek_labels + custom_labels

        # 3. Index document into OpenSearch
        doc = {
            'objectKey':        key,
            'bucket':           bucket,
            'createdTimestamp': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
            'labels':           all_labels,
        }
        client = get_os_client()
        client.index(index=INDEX_NAME, body=doc, id=f'{bucket}/{key}')
        print(f"Indexed {key} with labels: {all_labels}")

    return {'statusCode': 200}
