import os

from rest_framework import serializers
from django.contrib.auth import get_user_model

from .weight_class import competitive_weight_class_label, normalize_bodyweight_for_storage

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    coach_signup_code = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'user_type', 'coach_signup_code']

    def validate(self, attrs):
        user_type = attrs.get('user_type')
        if user_type == 'head_coach':
            raise serializers.ValidationError({
                'user_type': 'Head coach accounts cannot be created through public registration.',
            })
        submitted_code = (attrs.get('coach_signup_code') or '').strip()
        if user_type == 'coach':
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
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password'],
            user_type=validated_data['user_type'],
        )
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
