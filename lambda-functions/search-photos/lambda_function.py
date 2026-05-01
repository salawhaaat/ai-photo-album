import boto3
import json
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

REGION          = 'us-east-1'
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']
INDEX_NAME      = 'photos'
BOT_ID          = os.environ['LEX_BOT_ID']
BOT_ALIAS_ID    = os.environ['LEX_BOT_ALIAS_ID']

lex = boto3.client('lexv2-runtime', region_name=REGION)


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


def lex_keywords(query):
    """Send query to Lex and extract slot values as keywords."""
    import uuid
    resp = lex.recognize_text(
        botId=BOT_ID,
        botAliasId=BOT_ALIAS_ID,
        localeId='en_US',
        sessionId=f'photo-search-{uuid.uuid4()}',  # unique session per request
        text=query,
    )
    slots = (resp.get('sessionState', {})
                 .get('intent', {})
                 .get('slots', {}))
    keywords = []
    for slot_val in slots.values():
        if slot_val and slot_val.get('value', {}).get('interpretedValue'):
            keywords.append(slot_val['value']['interpretedValue'].lower())
    return keywords


def search_photos(keywords):
    """Query OpenSearch for photos matching any of the keywords.
    Uses fuzzy matching to handle plural/singular variations (e.g. dogs→dog).
    """
    client = get_os_client()
    should = []
    for kw in keywords:
        should.append({'match': {'labels': {'query': kw, 'fuzziness': 'AUTO'}}})
        # Also try exact match on the stemmed form (strip trailing 's')
        if kw.endswith('s') and len(kw) > 3:
            should.append({'match': {'labels': kw[:-1]}})
    body = {
        'query': {
            'bool': {'should': should, 'minimum_should_match': 1}
        }
    }
    hits = client.search(index=INDEX_NAME, body=body)['hits']['hits']
    return [
        {
            'url': f"https://{h['_source']['bucket']}.s3.amazonaws.com/{h['_source']['objectKey']}",
            'labels': h['_source']['labels'],
        }
        for h in hits
    ]


def lambda_handler(event, context):
    q = (event.get('queryStringParameters') or {}).get('q', '').strip()
    if not q:
        return _resp(200, {'results': []})

    keywords = lex_keywords(q)
    print(f"Query: '{q}' → keywords: {keywords}")
    if not keywords:
        return _resp(200, {'results': []})

    results = search_photos(keywords)
    return _resp(200, {'results': results})


def _resp(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,x-amz-meta-customLabels,x-api-key',
        },
        'body': json.dumps(body),
    }
