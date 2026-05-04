from __future__ import annotations

from collections import Counter

from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from .artifacts import save_model_bundle
from .labels import response_label


def train_recommender_model(rows):
    if not rows:
        raise ValueError('No training rows available.')
    records = []
    labels = []
    for row in rows:
        records.append({
            'style_tag': row['style_tag'],
            'gender': row['gender'],
            'bodyweight_bucket': row['bodyweight_bucket'],
            'weight_class': row['weight_class'],
            'completion_ratio': row['completion_ratio'] or 0.0,
            'exercise_count': row['exercise_count'] or 0.0,
            'total_sets': row['total_sets'] or 0.0,
            'total_reps': row['total_reps'] or 0.0,
        })
        labels.append(response_label(row.get('completion_ratio'), row.get('pr_delta')))

    distribution = Counter(labels)
    if len(distribution.keys()) < 2:
        raise ValueError('Training requires at least two label classes.')

    vectorizer = DictVectorizer(sparse=False)
    matrix = vectorizer.fit_transform(records)
    x_train, x_test, y_train, y_test = train_test_split(
        matrix,
        labels,
        test_size=0.3,
        random_state=42,
        stratify=labels,
    )
    model = LogisticRegression(max_iter=800, class_weight='balanced')
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]

    metrics = {
        'rows': len(rows),
        'label_distribution': dict(distribution),
        'accuracy': round(float(accuracy_score(y_test, predictions)), 4),
        'roc_auc': round(float(roc_auc_score(y_test, probabilities)), 4),
    }
    feature_names = vectorizer.get_feature_names_out().tolist()
    artifact = save_model_bundle(model, vectorizer, feature_names, metrics)
    return {'artifact': artifact, 'metrics': metrics}

