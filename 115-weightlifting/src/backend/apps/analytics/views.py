from collections import defaultdict
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.roles import is_head_coach, staff_coach_queryset
from apps.accounts.weight_class import competitive_weight_class_label
from apps.athletes.models import PersonalRecord, ProgramCompletion
from apps.analytics.ml.artifacts import load_latest_model_bundle
from apps.programs.models import TrainingProgram
from .robi import robi_score
from .serializers import RobiRequestSerializer, SinclairRequestSerializer
from .sinclair import calculate_sinclair_coefficient, calculate_sinclair_total

User = get_user_model()
MIN_SAMPLE_SIZE = 3


def _org_coach_ids(head):
    return [head.id, *list(staff_coach_queryset(head).values_list('pk', flat=True))]


def _bodyweight_bucket(user):
    bw = user.bodyweight_kg
    if bw is None:
        return 'unknown'
    value = float(bw)
    if user.gender == 'F':
        if value < 59:
            return 'small'
        if value <= 71:
            return 'medium'
        return 'large'
    if user.gender == 'M':
        if value < 73:
            return 'small'
        if value <= 96:
            return 'medium'
        return 'large'
    return 'unknown'


def _completion_ratio(completion_data):
    entries = (completion_data or {}).get('entries', {})
    total = 0
    done = 0
    for day_data in entries.values():
        if not isinstance(day_data, dict):
            continue
        for ex in day_data.values():
            if not isinstance(ex, dict):
                continue
            total += 1
            if ex.get('completed'):
                done += 1
    if total == 0:
        return None
    return done / total


def _pr_delta_for_program(program):
    if not program.end_date:
        return None
    baseline = (
        PersonalRecord.objects
        .filter(athlete_id=program.athlete_id, lift_type='total', date__lte=program.start_date)
        .order_by('-date')
        .values_list('weight', flat=True)
        .first()
    )
    outcome = (
        PersonalRecord.objects
        .filter(athlete_id=program.athlete_id, lift_type='total', date__gte=program.end_date)
        .order_by('-weight', '-date')
        .values_list('weight', flat=True)
        .first()
    )
    if baseline is None or outcome is None:
        return None
    return float(outcome - baseline)


def _head_program_rows(head):
    coach_ids = _org_coach_ids(head)
    programs = (
        TrainingProgram.objects
        .select_related('athlete')
        .filter(coach_id__in=coach_ids)
        .order_by('-updated_at')
    )
    completions = {
        (row.program_id, row.athlete_id): row.completion_data
        for row in ProgramCompletion.objects.filter(program__coach_id__in=coach_ids)
    }
    rows = []
    for program in programs:
        athlete = program.athlete
        completion = completions.get((program.id, athlete.id), {})
        rows.append({
            'program': program,
            'completion_ratio': _completion_ratio(completion),
            'pr_delta': _pr_delta_for_program(program),
            'segment': {
                'gender': athlete.gender or 'unknown',
                'weight_class': competitive_weight_class_label(athlete.bodyweight_kg, athlete.gender) or 'unknown',
                'bodyweight_bucket': _bodyweight_bucket(athlete),
            },
        })
    return rows


def _reduce_metrics(rows):
    count = len(rows)
    completion_values = [row['completion_ratio'] for row in rows if row['completion_ratio'] is not None]
    pr_values = [row['pr_delta'] for row in rows if row['pr_delta'] is not None]
    completion_rate = round(sum(completion_values) / len(completion_values), 3) if completion_values else None
    avg_pr_delta = round(sum(pr_values) / len(pr_values), 2) if pr_values else None
    return {
        'sample_size': count,
        'completion_rate': completion_rate,
        'avg_pr_delta_kg': avg_pr_delta,
    }


def _suppress_sparse(groups):
    return [group for group in groups if group['metrics']['sample_size'] >= MIN_SAMPLE_SIZE]


def _rule_recommendations(rows):
    grouped = defaultdict(list)
    for row in rows:
        tags = row['program'].style_tags or ['style:unclassified']
        for tag in tags:
            key = (row['segment']['gender'], row['segment']['bodyweight_bucket'], row['segment']['weight_class'], tag)
            grouped[key].append(row)

    segment_best = {}
    for (gender, bucket, weight_class, tag), items in grouped.items():
        metrics = _reduce_metrics(items)
        if metrics['sample_size'] < MIN_SAMPLE_SIZE:
            continue
        segment_key = (gender, bucket, weight_class)
        score = (
            metrics['completion_rate'] or 0,
            metrics['avg_pr_delta_kg'] or float('-inf'),
            metrics['sample_size'],
        )
        current = segment_best.get(segment_key)
        if current is None or score > current['score']:
            segment_best[segment_key] = {'style_tag': tag, 'metrics': metrics, 'score': score}

    recs = []
    for (gender, bucket, weight_class), data in segment_best.items():
        metrics = data['metrics']
        stability = 'high' if metrics['sample_size'] >= 8 else 'medium'
        recs.append({
            'segment': {
                'gender': gender,
                'bodyweight_bucket': bucket,
                'weight_class': weight_class,
            },
            'recommended_style_tag': data['style_tag'],
            'reason': 'Best observed completion/PR trend for this segment in current data.',
            'confidence': {
                'sample_size': metrics['sample_size'],
                'stability': stability,
                'effect': {
                    'completion_rate': metrics['completion_rate'],
                    'avg_pr_delta_kg': metrics['avg_pr_delta_kg'],
                },
            },
        })
    recs.sort(key=lambda item: item['confidence']['sample_size'], reverse=True)
    return recs


def _model_recommendations(rows):
    bundle = load_latest_model_bundle()
    if not bundle:
        raise ValueError('No trained model artifact is available.')
    model = bundle['model']
    vectorizer = bundle['vectorizer']
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['segment']['gender'], row['segment']['bodyweight_bucket'], row['segment']['weight_class'])].append(row)

    recommendations = []
    for (gender, bucket, weight_class), items in grouped.items():
        if len(items) < MIN_SAMPLE_SIZE:
            continue
        by_tag = defaultdict(list)
        for item in items:
            tags = item['program'].style_tags or ['style:unclassified']
            for tag in tags:
                by_tag[tag].append(item)
        best = None
        for tag, tag_items in by_tag.items():
            completion_values = [entry['completion_ratio'] for entry in tag_items if entry['completion_ratio'] is not None]
            pr_values = [entry['pr_delta'] for entry in tag_items if entry['pr_delta'] is not None]
            payload = {
                'style_tag': tag,
                'gender': gender,
                'bodyweight_bucket': bucket,
                'weight_class': weight_class,
                'completion_ratio': (sum(completion_values) / len(completion_values)) if completion_values else 0.0,
                'exercise_count': 0.0,
                'total_sets': 0.0,
                'total_reps': 0.0,
            }
            matrix = vectorizer.transform([payload])
            probability = float(model.predict_proba(matrix)[0][1])
            avg_pr_delta = round(sum(pr_values) / len(pr_values), 2) if pr_values else None
            candidate = {
                'segment': {
                    'gender': gender,
                    'bodyweight_bucket': bucket,
                    'weight_class': weight_class,
                },
                'recommended_style_tag': tag,
                'reason': 'Model-predicted response likelihood is highest for this style/segment.',
                'confidence': {
                    'sample_size': len(tag_items),
                    'stability': 'high' if len(tag_items) >= 8 else 'medium',
                    'effect': {
                        'completion_rate': round(payload['completion_ratio'], 3),
                        'avg_pr_delta_kg': avg_pr_delta,
                    },
                    'predicted_success_probability': round(probability, 3),
                },
                '_probability': probability,
            }
            if best is None or candidate['_probability'] > best['_probability']:
                best = candidate
        if best:
            best.pop('_probability', None)
            recommendations.append(best)
    recommendations.sort(key=lambda item: item['confidence']['sample_size'], reverse=True)
    return recommendations, bundle['metadata']


class SinclairView(APIView):
    def post(self, request):
        serializer = SinclairRequestSerializer(data=request.data)
        if serializer.is_valid():
            payload = serializer.validated_data
            coefficient = calculate_sinclair_coefficient(
                payload['bodyweight_kg'],
                payload['gender'],
            )
            sinclair_total = calculate_sinclair_total(
                payload['total_kg'],
                payload['bodyweight_kg'],
                payload['gender'],
            )
            return Response(
                {
                    'coefficient': round(coefficient, 4),
                    'sinclair_total': round(sinclair_total, 2),
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RobiView(APIView):
    """IWF ROBI score for one athlete's total, bracketed by current IWF WRs.

    See apps/analytics/robi.py for the formula, source citations, and the
    per-category WR table (post-2025-Worlds values).
    """

    def post(self, request):
        serializer = RobiRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        payload = serializer.validated_data
        try:
            result = robi_score(
                total_kg=payload['total_kg'],
                bodyweight_kg=payload['bodyweight_kg'],
                gender=payload['gender'],
            )
        except (ValueError, KeyError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)


class HeadProgramStyleOutcomesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_head_coach(request.user):
            return Response({'detail': 'Only head coaches can view this analytics endpoint.'}, status=status.HTTP_403_FORBIDDEN)
        rows = _head_program_rows(request.user)
        grouped = defaultdict(list)
        for row in rows:
            tags = row['program'].style_tags or ['style:unclassified']
            for tag in tags:
                key = (
                    tag,
                    row['segment']['gender'],
                    row['segment']['bodyweight_bucket'],
                    row['segment']['weight_class'],
                )
                grouped[key].append(row)
        out = []
        for (tag, gender, bucket, weight_class), items in grouped.items():
            out.append({
                'style_tag': tag,
                'segment': {
                    'gender': gender,
                    'bodyweight_bucket': bucket,
                    'weight_class': weight_class,
                },
                'metrics': _reduce_metrics(items),
            })
        out = _suppress_sparse(out)
        out.sort(key=lambda item: item['metrics']['sample_size'], reverse=True)
        return Response({'minimum_sample_size': MIN_SAMPLE_SIZE, 'groups': out}, status=status.HTTP_200_OK)


class HeadProgramNameOutcomesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_head_coach(request.user):
            return Response({'detail': 'Only head coaches can view this analytics endpoint.'}, status=status.HTTP_403_FORBIDDEN)
        rows = _head_program_rows(request.user)
        grouped = defaultdict(list)
        for row in rows:
            key = row['program'].normalized_name or 'unclassified'
            grouped[key].append(row)
        out = []
        for normalized_name, items in grouped.items():
            out.append({
                'normalized_name': normalized_name,
                'metrics': _reduce_metrics(items),
            })
        out = _suppress_sparse(out)
        out.sort(key=lambda item: item['metrics']['sample_size'], reverse=True)
        return Response({'minimum_sample_size': MIN_SAMPLE_SIZE, 'groups': out}, status=status.HTTP_200_OK)


class HeadRecommendationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_head_coach(request.user):
            return Response({'detail': 'Only head coaches can view this analytics endpoint.'}, status=status.HTTP_403_FORBIDDEN)
        rows = _head_program_rows(request.user)
        generated_at = datetime.now(timezone.utc).isoformat()
        mode = (getattr(settings, 'HEAD_RECOMMENDER_MODE', 'rule') or 'rule').lower()
        strategy = 'rule'
        model_version = None
        fallback_reason = None
        recs = _rule_recommendations(rows)

        if mode in ('shadow', 'model'):
            try:
                model_recs, metadata = _model_recommendations(rows)
                model_version = metadata.get('version')
                if mode == 'model':
                    recs = model_recs
                    strategy = 'model'
                else:
                    strategy = 'shadow'
            except Exception as exc:  # pragma: no cover - defensive runtime fallback
                fallback_reason = str(exc)
                strategy = 'rule'
        return Response({
            'minimum_sample_size': MIN_SAMPLE_SIZE,
            'recommendations': recs,
            'strategy': strategy,
            'model_version': model_version,
            'generated_at': generated_at,
            'fallback_reason': fallback_reason,
        }, status=status.HTTP_200_OK)


class HeadModelStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_head_coach(request.user):
            return Response({'detail': 'Only head coaches can view this analytics endpoint.'}, status=status.HTTP_403_FORBIDDEN)
        mode = (getattr(settings, 'HEAD_RECOMMENDER_MODE', 'rule') or 'rule').lower()
        bundle = load_latest_model_bundle()
        latest = bundle['metadata'] if bundle else None
        return Response({
            'mode': mode,
            'has_model_artifact': bool(bundle),
            'latest_model': latest,
            'generated_at': datetime.now(timezone.utc).isoformat(),
        }, status=status.HTTP_200_OK)

