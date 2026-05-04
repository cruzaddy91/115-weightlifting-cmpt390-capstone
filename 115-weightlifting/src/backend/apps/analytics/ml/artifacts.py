from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import joblib
from django.conf import settings


def artifact_dir():
    configured = getattr(settings, 'HEAD_RECOMMENDER_ARTIFACT_DIR', '')
    if configured:
        base = Path(configured)
    else:
        base = Path(settings.BASE_DIR) / 'var' / 'ml-artifacts'
    base.mkdir(parents=True, exist_ok=True)
    return base


def schema_hash(feature_names):
    joined = '|'.join(feature_names)
    return hashlib.sha256(joined.encode('utf-8')).hexdigest()[:12]


def save_model_bundle(model, vectorizer, feature_names, metrics):
    now = datetime.now(timezone.utc)
    version = f"head-recommender-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    payload = {
        'model': model,
        'vectorizer': vectorizer,
        'feature_names': feature_names,
        'metadata': {
            'version': version,
            'trained_at': now.isoformat(),
            'schema_hash': schema_hash(feature_names),
            'metrics': metrics,
        },
    }
    base = artifact_dir()
    model_path = base / f'{version}.joblib'
    meta_path = base / f'{version}.json'
    joblib.dump(payload, model_path)
    meta_path.write_text(json.dumps(payload['metadata'], indent=2), encoding='utf-8')
    return {
        'version': version,
        'trained_at': payload['metadata']['trained_at'],
        'schema_hash': payload['metadata']['schema_hash'],
        'metrics': metrics,
        'model_path': str(model_path),
        'meta_path': str(meta_path),
    }


def load_latest_model_bundle():
    base = artifact_dir()
    artifacts = sorted(base.glob('head-recommender-*.joblib'))
    if not artifacts:
        return None
    latest = artifacts[-1]
    payload = joblib.load(latest)
    payload['artifact_path'] = str(latest)
    return payload

