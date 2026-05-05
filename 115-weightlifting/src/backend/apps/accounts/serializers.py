import os
import re

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from .org_labels import NORMAL_MEMBER_PREFIXES, PREFIX_RE, RESERVED_ORG_PREFIXES
from .weight_class import competitive_weight_class_label, normalize_bodyweight_for_storage

User = get_user_model()

ATHLETE_BASE_USERNAME_RE = re.compile(r'^[A-Za-z0-9.@+-]+$')
ATHLETE_PREFIXED_USERNAME_RE = PREFIX_RE


def _username_prefix(username):
    match = ATHLETE_PREFIXED_USERNAME_RE.match(username or '')
    return match.group(1) if match else None


def _prefix_in_use(prefix):
    return User.objects.filter(username__iregex=rf'^{re.escape(prefix)}_').exists()


def _next_athlete_username(base_username):
    used_prefixes = set()
    for username in User.objects.values_list('username', flat=True):
        prefix = _username_prefix(username)
        if prefix:
            used_prefixes.add(prefix)
    for prefix in sorted(NORMAL_MEMBER_PREFIXES):
        if prefix in used_prefixes:
            continue
        candidate = f'{prefix}_{base_username}'
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
    raise serializers.ValidationError({
        'username': 'No normal coach/athlete numeric prefixes are available.',
    })


class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    coach_signup_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'user_type', 'coach_signup_code']

    def validate_email(self, value):
        email = str(value or '').strip().lower()
        if not email:
            raise serializers.ValidationError('Email is required.')
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return email

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        user_type = attrs.get('user_type')
        username = str(attrs.get('username') or '').strip()
        if not username:
            raise serializers.ValidationError({'username': 'Username is required.'})
        if user_type == 'head_coach':
            raise serializers.ValidationError({
                'user_type': 'Head coach accounts cannot be created through public registration.',
            })
        if user_type == 'athlete':
            if '_' in username:
                raise serializers.ValidationError({
                    'username': 'Enter the base athlete username without underscores; the system assigns the numeric prefix.',
                })
            if len(username) > 146:
                raise serializers.ValidationError({
                    'username': 'Athlete base username must be 146 characters or fewer.',
                })
            if not ATHLETE_BASE_USERNAME_RE.fullmatch(username):
                raise serializers.ValidationError({
                    'username': 'Use letters, numbers, and . @ + - only.',
                })
            attrs['username'] = username
        submitted_code = (attrs.get('coach_signup_code') or '').strip()
        if user_type == 'coach':
            prefix = _username_prefix(username)
            if prefix in RESERVED_ORG_PREFIXES:
                raise serializers.ValidationError({
                    'username': 'That numeric prefix is reserved for GM/AGM head-coach organization labels.',
                })
            if prefix not in NORMAL_MEMBER_PREFIXES:
                raise serializers.ValidationError({
                    'username': 'Line coach usernames must start with an available 000_ or 005_ through 099_ prefix.',
                })
            if _prefix_in_use(prefix):
                raise serializers.ValidationError({
                    'username': 'That numeric prefix is already assigned to another coach or athlete.',
                })
            if User.objects.filter(username__iexact=username).exists():
                raise serializers.ValidationError({
                    'username': 'A user with this username already exists.',
                })
            expected = (os.getenv('COACH_SIGNUP_CODE') or '').strip()
            if not expected:
                raise serializers.ValidationError({
                    'user_type': 'Coach registration is disabled until COACH_SIGNUP_CODE is configured.'
                })
            if submitted_code != expected:
                raise serializers.ValidationError({
                    'coach_signup_code': 'Invalid coach signup code.'
                })
        return attrs

    def create(self, validated_data):
        validated_data.pop('coach_signup_code', None)
        with transaction.atomic():
            username = validated_data['username']
            if validated_data['user_type'] == 'athlete':
                username = _next_athlete_username(username)
            user = User.objects.create_user(
                username=username,
                email=validated_data['email'],
                password=validated_data['password'],
                user_type=validated_data['user_type'],
            )
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return str(value or '').strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({'token': 'Invalid or expired password reset link.'})

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({'token': 'Invalid or expired password reset link.'})

        attrs['user'] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data['user']
        user.set_password(self.validated_data['password'])
        user.save(update_fields=['password'])
        return user


class CurrentUserSerializer(serializers.ModelSerializer):
    competitive_weight_class = serializers.SerializerMethodField()
    reports_to_id = serializers.IntegerField(read_only=True, allow_null=True)
    reports_to_username = serializers.SerializerMethodField()
    primary_coach_id = serializers.IntegerField(read_only=True, allow_null=True)
    primary_coach_username = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'user_type',
            'bodyweight_kg',
            'gender',
            'competitive_weight_class',
            'reports_to_id',
            'reports_to_username',
            'primary_coach_id',
            'primary_coach_username',
        ]

    def get_competitive_weight_class(self, obj):
        return competitive_weight_class_label(obj.bodyweight_kg, obj.gender)

    def get_reports_to_username(self, obj):
        r = obj.reports_to
        return r.username if r else None

    def get_primary_coach_username(self, obj):
        c = obj.primary_coach
        return c.username if c else None


class AthleteProfileUpdateSerializer(serializers.ModelSerializer):
    """Partial update for athletes: body mass + gender (drives weight-class label)."""

    class Meta:
        model = User
        fields = ['bodyweight_kg', 'gender']

    def validate_gender(self, value):
        if value in (None, ''):
            return None
        v = str(value).strip().upper()
        if v not in ('M', 'F'):
            raise serializers.ValidationError('Use M or F.')
        return v

    def validate_bodyweight_kg(self, value):
        normalized = normalize_bodyweight_for_storage(value)
        if normalized is None and value not in (None, ''):
            raise serializers.ValidationError('Invalid bodyweight.')
        if normalized is not None and (normalized > 250 or normalized < 25):
            raise serializers.ValidationError('Bodyweight must be between 25 and 250 kg.')
        return normalized

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        return instance
